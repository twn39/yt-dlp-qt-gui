from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from .config import remove_task_log
from .database import Database
from .models import DownloadStatus, DownloadTask
from .utils import clean_ansi
from .worker import DownloadWorker


class DownloadScheduler(QObject):
    """下载调度管理器，负责并发控制、等待队列及线程生命周期管理"""

    task_added = Signal(DownloadTask)  # 发送完整的任务实体
    task_status_changed = Signal(int, str)  # 发送 (task_id, status)
    task_progress_changed = Signal(int, dict)  # 发送 (task_id, progress_data)
    task_title_updated = Signal(int, str)  # 发送 (task_id, title)
    task_log_emitted = Signal(int, str)  # 发送 (task_id, log_msg)
    task_finished = Signal(int, bool, str)  # 发送 (task_id, success, message)
    task_deleted = Signal(int)  # 发送 task_id

    # 严格合法的生命周期状态跃迁表
    _ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        DownloadStatus.PENDING: {
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.CANCELLED,
        },
        DownloadStatus.QUEUED: {
            DownloadStatus.DOWNLOADING,
            DownloadStatus.CANCELLED,
        },
        DownloadStatus.DOWNLOADING: {
            DownloadStatus.MERGING,
            DownloadStatus.FINISHED,
            DownloadStatus.ERROR,
            DownloadStatus.CANCELLED,
        },
        DownloadStatus.MERGING: {
            DownloadStatus.FINISHED,
            DownloadStatus.ERROR,
            DownloadStatus.CANCELLED,
        },
        DownloadStatus.FINISHED: {
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
        },
        DownloadStatus.ERROR: {
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
        },
        DownloadStatus.CANCELLED: {
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
        },
    }

    def __init__(self, db: Database, max_concurrent_downloads: int = 3) -> None:
        super().__init__()
        self.db = db
        self.max_concurrent_downloads = max_concurrent_downloads

        self.workers: Dict[int, DownloadWorker] = {}
        self.threads: Dict[int, QThread] = {}

        self._waiting_queue: List[int] = []
        self._active_task_ids: Set[int] = set()
        self._pending_delete_tids: Set[int] = set()
        self._is_shutdown = False

    def is_task_running(self, task_id: int) -> bool:
        """检查任务是否正在被下载工作线程执行"""
        return task_id in self.threads

    def is_task_queued(self, task_id: int) -> bool:
        """检查任务是否正在等待队列中排队"""
        return task_id in self._waiting_queue

    def is_task_active(self, task_id: int) -> bool:
        """检查任务是否活跃（运行中或排队中）"""
        return self.is_task_running(task_id) or self.is_task_queued(task_id)

    def _transition_status(
        self, task_id: int, new_status: str, extra_updates: Optional[Dict[str, Any]] = None
    ) -> bool:
        """执行受状态机守卫保护的状态转移，原子化更新数据库并广播信号"""
        task = self.db.get_task(task_id)
        if not task:
            return False

        current_status = task.status
        allowed = self._ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status != current_status and new_status not in allowed:
            return False

        payload: Dict[str, Any] = {"status": new_status}
        if extra_updates:
            payload.update(extra_updates)

        self.db.update_task(task_id, payload)
        self.task_status_changed.emit(task_id, new_status)
        return True

    def get_all_tasks(
        self, sort_col: str = "created_at", sort_dir: str = "DESC"
    ) -> List[DownloadTask]:
        """代理获取所有任务列表（提供给 UI Facade 访问）"""
        return self.db.get_all_tasks(sort_col=sort_col, sort_dir=sort_dir)

    def get_task(self, task_id: int) -> Optional[DownloadTask]:
        """代理获取特定任务详情（提供给 UI Facade 访问）"""
        return self.db.get_task(task_id)

    def add_task(self, task: DownloadTask) -> int:
        """添加新任务到数据库，并调度启动"""
        task_id = self.db.add_task(task)
        db_task = self.db.get_task(task_id)
        if db_task:
            self.task_added.emit(db_task)
            self.start_task(task_id)
        return task_id

    def start_task(self, task_id: int) -> None:
        """启动特定任务（若达到并发上限则加入等待队列）"""
        if self.is_task_active(task_id):
            return

        task = self.db.get_task(task_id)
        if not task:
            return

        # 判断是否可以在当前执行
        if len(self._active_task_ids) < self.max_concurrent_downloads:
            self._active_task_ids.add(task_id)
            self._run_task_thread(task)
        else:
            # 达到并发上限，标记为排队中，加入等待队列
            self._waiting_queue.append(task_id)
            self._transition_status(task_id, DownloadStatus.QUEUED)

    def _run_task_thread(self, task: DownloadTask) -> None:
        """在 QThread 中实际创建并启动下载任务"""
        task_id = task.id
        assert task_id is not None
        self._transition_status(task_id, DownloadStatus.DOWNLOADING)

        thread = QThread()
        worker = DownloadWorker(
            task_id=task_id,
            url=task.url,
            download_path=task.save_path,
            format_preset=task.format_preset,
            proxy=task.proxy,
            concurrent_fragments=task.concurrent_fragments,
            write_subs=task.write_subs,
            download_playlist=task.download_playlist,
            playlist_items=task.playlist_items,
            impersonate=task.impersonate,
            no_cookies=task.no_cookies,
            cookie_browser=task.cookie_browser,
            ratelimit=task.ratelimit,
        )
        worker.moveToThread(thread)

        # 连接 Worker 内部信号
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.log_message.connect(self._on_worker_log)

        # 启动与销毁逻辑
        thread.started.connect(worker.run)
        thread.finished.connect(lambda tid=task_id: self._cleanup_thread(tid))

        self.threads[task_id] = thread
        self.workers[task_id] = worker
        thread.start()

    def stop_task(self, task_id: int) -> None:
        """停止特定下载任务（若在队列中则直接移除并标记为取消）"""
        if task_id in self._waiting_queue:
            self._waiting_queue.remove(task_id)
            updates = {"progress": 0, "speed": "--", "eta": "--"}
            self._transition_status(task_id, DownloadStatus.CANCELLED, updates)
        elif task_id in self.workers:
            self.workers[task_id].cancel()

    def start_all_tasks(self) -> None:
        """一键开始所有未完成/未在运行的任务"""
        tasks = self.get_all_tasks()
        for task in tasks:
            if task.id is not None and not self.is_task_active(task.id):
                # 排除已完成的任务，只拉起待处理、出错、取消等状态的任务
                if task.status != DownloadStatus.FINISHED:
                    self.start_task(task.id)

    def stop_all_tasks(self) -> None:
        """一键停止所有运行中或排队中的任务"""
        # 1. 停止排队队列中的任务
        for task_id in list(self._waiting_queue):
            self.stop_task(task_id)
        # 2. 停止运行中工作线程
        for task_id in list(self.workers.keys()):
            self.stop_task(task_id)

    def delete_task(self, task_id: int) -> None:
        """删除特定下载任务（若运行中则先取消，待线程退出后自动清除数据）"""
        if task_id in self.threads:
            self._pending_delete_tids.add(task_id)
            self.workers[task_id].cancel()
        elif task_id in self._waiting_queue:
            self._waiting_queue.remove(task_id)
            self.db.delete_task(task_id)
            remove_task_log(task_id)
            self.task_deleted.emit(task_id)
        else:
            self.db.delete_task(task_id)
            remove_task_log(task_id)
            self.task_deleted.emit(task_id)

    @Slot(int, dict)
    def _on_worker_progress(self, task_id: int, data: Dict[str, Any]) -> None:
        """处理任务进度信号，更新任务标题"""
        if "info_dict" in data and data["info_dict"].get("title"):
            title = data["info_dict"]["title"]
            cleaned_title = clean_ansi(title)
            self.db.update_task(task_id, {"title": cleaned_title})
            self.task_title_updated.emit(task_id, cleaned_title)

        self.task_progress_changed.emit(task_id, data)

    @Slot(int, str)
    def _on_worker_log(self, task_id: int, msg: str) -> None:
        """转发 Worker 的日志消息"""
        self.task_log_emitted.emit(task_id, msg)

    @Slot(int, bool, str)
    def _on_worker_finished(self, task_id: int, success: bool, message: str) -> None:
        """处理 Worker 执行完毕的逻辑"""
        status = (
            DownloadStatus.FINISHED
            if success
            else (DownloadStatus.CANCELLED if "用户取消" in message else DownloadStatus.ERROR)
        )
        updates = {
            "progress": 100 if success else 0,
            "speed": "--",
            "eta": "--",
        }
        self._transition_status(task_id, status, updates)
        self.task_finished.emit(task_id, success, message)

        if task_id in self.threads:
            self.threads[task_id].quit()

    def set_max_concurrent_downloads(self, limit: int) -> None:
        """动态更新最大并发下载数，并在扩容时自动唤醒排队任务"""
        if limit < 1:
            raise ValueError("最大并发数不能小于 1")
        old_limit = self.max_concurrent_downloads
        self.max_concurrent_downloads = limit
        if limit > old_limit:
            self._schedule_next()

    def _cleanup_thread(self, task_id: int) -> None:
        """清理线程资源，并通过事件循环异步调度执行等待队列中的任务"""
        thread = self.threads.pop(task_id, None)
        self.workers.pop(task_id, None)
        if thread is not None:
            thread.deleteLater()

        self._active_task_ids.discard(task_id)

        # 处理停止后删除挂起的状态
        if task_id in self._pending_delete_tids:
            self._pending_delete_tids.discard(task_id)
            self.db.delete_task(task_id)
            remove_task_log(task_id)
            self.task_deleted.emit(task_id)

        # 通过 Qt 事件循环投递下一次调度，解除深度同步调用栈与重入风险
        QTimer.singleShot(0, self._schedule_next)

    def _schedule_next(self) -> None:
        """从等待队列中提取任务并启动，直到占满所有空闲并发槽位（饱和填充）"""
        while self._waiting_queue and len(self._active_task_ids) < self.max_concurrent_downloads:
            next_task_id = self._waiting_queue.pop(0)
            task = self.db.get_task(next_task_id)
            if task:
                self._active_task_ids.add(next_task_id)
                self._run_task_thread(task)

    def shutdown(self) -> None:
        """优雅关闭所有运行中的下载线程"""
        if self._is_shutdown:
            return
        self._is_shutdown = True

        # 取消所有 Worker 运行
        for worker in list(self.workers.values()):
            worker.cancel()

        # 等待线程安全退出（最多 3 秒/线程）
        for thread in list(self.threads.values()):
            thread.quit()
            thread.wait(3000)
