import re
from typing import Any, Dict, List, Set

from PySide6.QtCore import QObject, QThread, Signal, Slot

from .config import remove_task_log
from .database import Database
from .models import DownloadTask
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

    def __init__(self, db: Database, max_concurrent_downloads: int = 3) -> None:
        super().__init__()
        self.db = db
        self.max_concurrent_downloads = max_concurrent_downloads

        self.workers: Dict[int, DownloadWorker] = {}
        self.threads: Dict[int, QThread] = {}

        self._waiting_queue: List[int] = []
        self._active_task_ids: Set[int] = set()
        self._pending_delete_tids: Set[int] = set()

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
        if task_id in self.threads or task_id in self._waiting_queue:
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
            self.db.update_task(task_id, {"status": "queued"})
            self._waiting_queue.append(task_id)
            self.task_status_changed.emit(task_id, "queued")

    def _run_task_thread(self, task: DownloadTask) -> None:
        """在 QThread 中实际创建并启动下载任务"""
        task_id = task.id
        assert task_id is not None
        self.db.update_task(task_id, {"status": "downloading"})
        self.task_status_changed.emit(task_id, "downloading")

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
            updates = {"status": "cancelled", "progress": 0, "speed": "--", "eta": "--"}
            self.db.update_task(task_id, updates)
            self.task_status_changed.emit(task_id, "cancelled")
        elif task_id in self.workers:
            self.workers[task_id].cancel()

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
            # 清理 ANSI 终端序列
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            cleaned_title = ansi_escape.sub("", title).strip()
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
        status = "finished" if success else ("cancelled" if "用户取消" in message else "error")
        updates = {
            "status": status,
            "progress": 100 if success else 0,
            "speed": "--",
            "eta": "--",
        }
        self.db.update_task(task_id, updates)
        self.task_status_changed.emit(task_id, status)
        self.task_finished.emit(task_id, success, message)

        if task_id in self.threads:
            self.threads[task_id].quit()

    def _cleanup_thread(self, task_id: int) -> None:
        """清理线程资源，并调度执行等待队列中的任务"""
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

        # 执行等待队列中的下一个任务
        self._schedule_next()

    def _schedule_next(self) -> None:
        """从等待队列中提取任务并启动"""
        if not self._waiting_queue:
            return
        if len(self._active_task_ids) < self.max_concurrent_downloads:
            next_task_id = self._waiting_queue.pop(0)
            task = self.db.get_task(next_task_id)
            if task:
                self._active_task_ids.add(next_task_id)
                self._run_task_thread(task)
            else:
                # 递归提取（处理已从数据库删除的任务）
                self._schedule_next()

    def shutdown(self) -> None:
        """优雅关闭所有运行中的下载线程"""
        # 取消所有 Worker 运行
        for worker in list(self.workers.values()):
            worker.cancel()

        # 等待线程安全退出（最多 3 秒/线程）
        for thread in list(self.threads.values()):
            thread.quit()
            thread.wait(3000)
