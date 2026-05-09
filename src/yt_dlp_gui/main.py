import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any, Dict

try:
    __version__ = _pkg_version("yt-dlp-qt-gui")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
import click
import qtawesome as qta
from PySide6.QtCore import QSize, Qt, QThread, QUrl, Slot
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import STYLESHEET_FILE
from .database import Database
from .dialogs import AddTaskDialog, LogDialog
from .worker import DownloadWorker


def load_stylesheet(filename: str = STYLESHEET_FILE) -> str | None:
    """加载 QSS 样式文件"""
    possible_paths = []
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            possible_paths.append(os.path.join(sys._MEIPASS, filename))
        possible_paths.append(os.path.join(os.path.dirname(sys.executable), filename))
    else:
        possible_paths.append(filename)
        possible_paths.append(os.path.join(os.path.dirname(__file__), "..", "..", filename))

    for filepath in possible_paths:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                continue
    return None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.workers: Dict[int, DownloadWorker] = {}
        self.threads: Dict[int, QThread] = {}
        self.task_logs: Dict[int, str] = {}  # 存储任务日志
        self.active_log_dialogs: Dict[int, Any] = {}  # 跟踪打开的日志窗口
        self._pending_delete_tids: set[int] = set()  # 「停止后删除」的挂起任务 ID
        # task_id → row 反向映射，使 _update_table_row 从 O(n) 降为 O(1)
        self._task_row_map: dict[int, int] = {}
        # 排序选项：显示文本 → (sort_col, sort_dir)
        self._sort_options: dict[str, tuple[str, str]] = {
            "创建时间 ↓": ("created_at", "DESC"),
            "创建时间 ↑": ("created_at", "ASC"),
            "名称 A→Z": ("title", "ASC"),
            "名称 Z→A": ("title", "DESC"),
            "状态": ("status", "ASC"),
        }

        self.setWindowTitle("Yt-dlp GUI — 现代化视频下载管理器")
        self.resize(1100, 750)

        self._setup_ui()
        self._setup_toolbar()
        self._apply_dark_theme()
        self._load_tasks_from_db()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8) # 缩小边距
        main_layout.setSpacing(0)

        # 容器面板 Panel
        self.table_panel = QFrame()
        self.table_panel.setObjectName("table_panel")
        panel_layout = QVBoxLayout(self.table_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0) # 去掉内边距，使表格填充满面板

        # 下载列表表格
        self.table = QTableWidget()
        self.table.setColumnCount(5) # 名称, 状态, 进度, 速度, 剩余时间
        self.table.setHorizontalHeaderLabels(["名称", "状态", "进度", "速度", "剩余时间"])

        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        # 允许用户手动拖动伸缩列宽
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # 默认填充满宽度
        header.setStretchLastSection(True)

        # 设置初始列宽
        self.table.setColumnWidth(0, 350)  # 名称
        self.table.setColumnWidth(1, 120)  # 状态
        self.table.setColumnWidth(2, 220)  # 进度
        self.table.setColumnWidth(3, 100)  # 速度
        self.table.setColumnWidth(4, 100)  # 剩余时间

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(36)

        # 禁用表头点击排序：改用工具栏下拉框触发 DB 层排序，避免 row 索引失效
        self.table.setSortingEnabled(False)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        panel_layout.addWidget(self.table)
        main_layout.addWidget(self.table_panel)

        # 状态栏信息
        self.status_info = QLabel(" 准备就绪")
        self.statusBar().addWidget(self.status_info)
        self.task_count_info = QLabel("0 个项目, 已选择 0 个  ")
        self.statusBar().addPermanentWidget(self.task_count_info)
        self.table.itemSelectionChanged.connect(self._update_status_counts)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(toolbar)

        add_action = QAction(qta.icon("fa5s.plus-circle", color="#FFFFFF"), "添加", self)
        add_action.triggered.connect(self._show_add_dialog)
        toolbar.addAction(add_action)

        toolbar.addSeparator()

        start_action = QAction(qta.icon("fa5s.play-circle", color="#FFFFFF"), "开始", self)
        start_action.triggered.connect(self._start_selected_task)
        toolbar.addAction(start_action)

        stop_action = QAction(qta.icon("fa5s.stop-circle", color="#FFFFFF"), "停止", self)
        stop_action.triggered.connect(self._stop_selected_task)
        toolbar.addAction(stop_action)

        toolbar.addSeparator()

        delete_action = QAction(qta.icon("fa5s.trash-alt", color="#FFFFFF"), "删除", self)
        delete_action.triggered.connect(self._delete_selected_task)
        toolbar.addAction(delete_action)

        info_action = QAction(qta.icon("fa5s.info-circle", color="#FFFFFF"), "关于", self)
        info_action.triggered.connect(lambda: QMessageBox.information(self, "关于", "Yt-dlp GUI\n现代化视频下载管理器"))
        toolbar.addAction(info_action)

        # 排序控件：弹性间隔 + QToolButton+QMenu，风格与左侧工具栏按鈕完全一致
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.sort_button = QToolButton(self)
        self.sort_button.setIcon(qta.icon("fa5s.sort-amount-down", color="#BBBBBB"))
        self.sort_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sort_button.setText(next(iter(self._sort_options)))  # 默认„创建时间 ↓“
        self.sort_button.setToolTip("排序方式")

        _sort_menu = QMenu(self)
        for _lbl in self._sort_options:
            _sort_menu.addAction(_lbl).triggered.connect(
                lambda checked=False, lbl=_lbl: self._on_sort_changed(lbl)
            )
        self.sort_button.setMenu(_sort_menu)
        toolbar.addWidget(self.sort_button)

    def _update_status_counts(self):
        total = self.table.rowCount()
        selected = len(set(index.row() for index in self.table.selectedIndexes()))
        self.task_count_info.setText(f"{total} 个项目, 已选择 {selected} 个  ")

    def _get_status_icon(self, status):
        if status == "downloading":
            return qta.icon("fa5s.download", color="#FFFFFF")
        elif status == "finished":
            return qta.icon("fa5s.check-circle", color="#4CAF50") # 绿色图标
        elif status == "error":
            return qta.icon("fa5s.exclamation-circle", color="#FFFFFF")
        elif status == "merging":
            return qta.icon("fa5s.layer-group", color="#FFFFFF")
        elif status == "cancelled":
            return qta.icon("fa5s.stop-circle", color="#FFFFFF")
        return qta.icon("fa5s.clock", color="#FFFFFF")

    def _apply_dark_theme(self):
        qss = load_stylesheet()
        if qss:
            self.setStyleSheet(qss)

    def _on_sort_changed(self, label: str) -> None:
        """排序选项变更时更新按鈕文字并重新加载"""
        self.sort_button.setText(label)
        self._load_tasks_from_db()

    def _load_tasks_from_db(self) -> None:
        """从 DB 加载所有任务并重建表格和 row 映射"""
        current = (
            self.sort_button.text()
            if hasattr(self, "sort_button")
            else next(iter(self._sort_options))
        )
        sort_col, sort_dir = self._sort_options.get(current, ("created_at", "DESC"))
        self.table.setRowCount(0)
        self._task_row_map.clear()
        tasks = self.db.get_all_tasks(sort_col=sort_col, sort_dir=sort_dir)
        for task in tasks:
            self._add_task_to_table(task)
        self._update_status_counts()

    def _add_task_to_table(self, task: dict[str, Any]) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        # 写入 task_id → row 映射
        self._task_row_map[task["id"]] = row

        # 将 ID 存在 UserRole 中
        title = task["title"] or task["url"]
        icon_color = "#4CAF50" if task["status"] == "finished" else "#FFFFFF"
        icon_name = "fa5s.file-video" if task["status"] == "finished" else "fa5s.video"
        title_item = QTableWidgetItem(qta.icon(icon_name, color=icon_color), title)
        title_item.setData(Qt.ItemDataRole.UserRole, task["id"])
        self.table.setItem(row, 0, title_item)

        status_item = QTableWidgetItem(self._get_status_icon(task["status"]), task["status"])
        self.table.setItem(row, 1, status_item)

        pbar_container = QWidget()
        pbar_container.setStyleSheet("background: transparent;")
        pbar_layout = QVBoxLayout(pbar_container)
        pbar_layout.setContentsMargins(15, 6, 15, 6)
        pbar = QProgressBar()
        pbar.setValue(task["progress"] or 0)
        pbar_layout.addWidget(pbar)
        self.table.setCellWidget(row, 2, pbar_container)

        self.table.setItem(row, 3, QTableWidgetItem(task["speed"] or "--"))
        self.table.setItem(row, 4, QTableWidgetItem(task["eta"] or "--"))

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        open_folder_action = menu.addAction(qta.icon("fa5s.folder-open", color="#FFFFFF"), "打开保存文件夹")
        view_log_action = menu.addAction(qta.icon("fa5s.file-alt", color="#FFFFFF"), "查看详细日志")
        menu.addSeparator()
        start_action = menu.addAction(qta.icon("fa5s.play", color="#FFFFFF"), "开始 / 重试")
        stop_action = menu.addAction(qta.icon("fa5s.stop", color="#FFFFFF"), "停止")
        delete_action = menu.addAction(qta.icon("fa5s.trash-alt", color="#FFFFFF"), "删除任务")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == open_folder_action:
            self._open_task_folder()
        elif action == view_log_action:
            self._view_selected_task_log()
        elif action == start_action:
            self._start_selected_task()
        elif action == stop_action:
            self._stop_selected_task()
        elif action == delete_action:
            self._delete_selected_task()

    def _open_task_folder(self):
        row = self.table.currentRow()
        if row < 0:
            return
        task_id = self._get_task_id_from_row(row)
        if not task_id:
            return

        task = self.db.get_task(task_id)
        if task and task['save_path']:
            path = task['save_path']
            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(self, "错误", f"目录不存在: {path}")

    def _view_selected_task_log(self):
        row = self.table.currentRow()
        if row < 0:
            return
        task_id = self._get_task_id_from_row(row)
        if not task_id:
            return

        item0 = self.table.item(row, 0)
        title = item0.text() if item0 else "未知任务"

        # 如果窗口已打开，则置顶
        if task_id in self.active_log_dialogs:
            self.active_log_dialogs[task_id].raise_()
            self.active_log_dialogs[task_id].activateWindow()
            return

        dialog = LogDialog(task_id, title, self)
        dialog.set_initial_logs(self.task_logs.get(task_id, "暂无日志信息...\n"))
        dialog.finished.connect(lambda: self.active_log_dialogs.pop(task_id, None))
        self.active_log_dialogs[task_id] = dialog
        dialog.show()

    @Slot()
    def _show_add_dialog(self) -> None:
        dialog = AddTaskDialog(self)
        if dialog.exec():
            task_data = dialog.get_task_data()
            if not task_data["url"]:
                return
            task_id = self.db.add_task(task_data)
            task = self.db.get_task(task_id)
            if task is None:
                return

            self._add_task_to_table(task)
            self._start_task(task_id)

    def _get_task_id_from_row(self, row):
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _start_selected_task(self):
        rows = set(index.row() for index in self.table.selectedIndexes())
        for row in rows:
            tid = self._get_task_id_from_row(row)
            if tid:
                self._start_task(tid)

    def _start_task(self, task_id):
        if task_id in self.threads:
            return
        task = self.db.get_task(task_id)
        if not task:
            return

        self.db.update_task(task_id, {"status": "downloading"})
        self._update_table_row(task_id, {"status": "downloading"})

        thread = QThread()
        worker = DownloadWorker(
            task_id=task_id,
            url=task['url'],
            download_path=task['save_path'],
            format_preset=task['format_preset'],
            proxy=task['proxy'],
            concurrent_fragments=task['concurrent_fragments'],
            write_subs=task['write_subs'],
            download_playlist=task['download_playlist'],
            playlist_items=task['playlist_items']
        )
        worker.moveToThread(thread)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.log_message.connect(self._on_log)  # 连接日志信号
        thread.started.connect(worker.run)
        # 线程退出后异步清理资源，避免在 _on_finished 中调用 thread.wait() 阻塞主线程
        thread.finished.connect(lambda tid=task_id: self._cleanup_thread(tid))

        self.threads[task_id] = thread
        self.workers[task_id] = worker
        thread.start()

    def _stop_selected_task(self):
        rows = set(index.row() for index in self.table.selectedIndexes())
        for row in rows:
            tid = self._get_task_id_from_row(row)
            if tid and tid in self.workers:
                self.workers[tid].cancel()

    def _delete_selected_task(self) -> None:
        indices = self.table.selectionModel().selectedRows()
        if not indices:
            return

        # 分类：静止任务（可直接删） vs 运行中任务（需先停止）
        idle_indices: list = []
        running_tids: list[int] = []
        for index in indices:
            tid = self._get_task_id_from_row(index.row())
            if tid is None:
                continue
            if tid in self.threads:
                running_tids.append(tid)
            else:
                idle_indices.append(index)

        if running_tids:
            # 有运行中任务：给出明确提示，提供「停止并删除」选项
            msg = (
                f"选中的 {len(indices)} 个任务中，"
                f"有 {len(running_tids)} 个正在下载。\n\n"
                f"是否立即停止并删除全部 {len(indices)} 个任务？"
            )
            confirm = QMessageBox.question(
                self,
                "确认停止并删除",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            # 取消运行中任务，实际行删除由 _cleanup_thread 中的 pending 机制处理
            for tid in running_tids:
                if tid in self.workers:
                    self.workers[tid].cancel()
            self._pending_delete_tids.update(running_tids)
        else:
            # 无运行中任务：普通确认即可
            confirm = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除选中的 {len(idle_indices)} 个任务吗？",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self._delete_idle_rows(idle_indices)
        self._update_status_counts()

    def _update_table_row(self, task_id: int, data: dict[str, Any]) -> None:
        """O(1) 行更新：通过 _task_row_map 直接定位，无需全表扫描"""
        row = self._task_row_map.get(task_id)
        if row is None:
            return
        if "status" in data:
            st = data["status"]
            item1 = self.table.item(row, 1)
            if item1:
                item1.setIcon(self._get_status_icon(st))
                item1.setText(st)
            # 如果完成，第一列的图标也变绿
            if st == "finished":
                item0 = self.table.item(row, 0)
                if item0:
                    item0.setIcon(qta.icon("fa5s.file-video", color="#4CAF50"))
        if "progress" in data:
            pcont = self.table.cellWidget(row, 2)
            if pcont:
                pbar = pcont.findChild(QProgressBar)
                if pbar:
                    pbar.setValue(data["progress"])
        if "speed" in data:
            item3 = self.table.item(row, 3)
            if item3:
                item3.setText(data["speed"])
        if "eta" in data:
            item4 = self.table.item(row, 4)
            if item4:
                item4.setText(data["eta"])
        if "title" in data:
            item0 = self.table.item(row, 0)
            if item0:
                item0.setText(data["title"])

    def _clean_ansi(self, text):
        """清除 ANSI 转义代码 (如 [0;32m)"""
        if not isinstance(text, str):
            return text
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    def _format_speed(self, speed):
        """格式化下载速度"""
        if speed is None:
            return "--"
        if isinstance(speed, str):
            return self._clean_ansi(speed)

        # 处理数值类型
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024.0:
                return f"{speed:.1f} {unit}"
            speed /= 1024.0
        return f"{speed:.1f} TB/s"

    def _format_eta(self, seconds):
        """格式化剩余时间"""
        if seconds is None:
            return "--"
        if isinstance(seconds, str):
            return self._clean_ansi(seconds)

        # 处理数值类型 (秒)
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"
        except (ValueError, TypeError):
            return "--"

    @Slot(int, dict)
    def _on_progress(self, task_id, data):
        # 尝试从 info_dict 获取标题并更新
        if 'info_dict' in data and data['info_dict'].get('title'):
            title = self._clean_ansi(data['info_dict']['title'])
            self.db.update_task(task_id, {"title": title})
            self._update_table_row(task_id, {"title": title})

        if data['status'] == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            downloaded = data.get('downloaded_bytes')

            # 计算进度百分比
            progress = 0
            if total and downloaded:
                progress = int(downloaded / total * 100)

            # 优先使用 yt-dlp 提供的字符串，否则手动格式化原始数值
            speed_str = data.get('speed_str') or data.get('_speed_str')
            if speed_str:
                speed_str = self._clean_ansi(speed_str)
            else:
                speed_str = self._format_speed(data.get('speed'))

            eta_str = data.get('eta_str') or data.get('_eta_str')
            if eta_str:
                eta_str = self._clean_ansi(eta_str)
            else:
                eta_str = self._format_eta(data.get('eta'))

            # 始终更新 UI
            self._update_table_row(task_id, {
                "progress": progress,
                "speed": speed_str,
                "eta": eta_str
            })
        elif data['status'] == 'merging':
            self._update_table_row(task_id, {"status": "merging", "speed": "Merging...", "eta": "--"})

    @Slot(int, str)
    def _on_log(self, task_id, msg):
        # 存储日志
        current_logs = self.task_logs.get(task_id, "")
        self.task_logs[task_id] = current_logs + msg + "\n"

        # 如果日志窗口打开，实时更新
        if task_id in self.active_log_dialogs:
            self.active_log_dialogs[task_id].append_log(msg)

    @Slot(int, bool, str)
    def _on_finished(self, task_id: int, success: bool, message: str) -> None:
        status = "finished" if success else ("cancelled" if "用户取消" in message else "error")
        # 完成时清空速度和剩余时间
        updates = {
            "status": status,
            "progress": 100 if success else 0,
            "speed": "--",
            "eta": "--",
        }
        self.db.update_task(task_id, updates)
        self._update_table_row(task_id, updates)

        # 只发出退出请求，实际资源清理由 thread.finished → _cleanup_thread 异步完成
        # 严禁在此处调用 thread.wait()，否则会阻塞主线程（GUI 线程）
        if task_id in self.threads:
            self.threads[task_id].quit()

    def _cleanup_thread(self, task_id: int) -> None:
        """线程退出后异步清理资源（由 thread.finished 信号触发，运行在主线程）"""
        thread = self.threads.pop(task_id, None)
        self.workers.pop(task_id, None)
        if thread is not None:
            thread.deleteLater()  # 让 Qt 事件循环负责内存回收

        # 处理「停止后删除」的挂起请求
        if task_id in self._pending_delete_tids:
            self._pending_delete_tids.discard(task_id)
            self.db.delete_task(task_id)
            self._remove_table_row_by_task_id(task_id)
            self._update_status_counts()

    def _remove_row_from_map(self, deleted_row: int, task_id: int) -> None:
        """从 _task_row_map 删除指定条目，并将该行以下所有条目的 row 值 -1"""
        self._task_row_map.pop(task_id, None)
        for tid in self._task_row_map:
            if self._task_row_map[tid] > deleted_row:
                self._task_row_map[tid] -= 1

    def _delete_idle_rows(self, indices: list) -> None:
        """删除非运行中任务的表格行和 DB 记录（逆序删除避免行号偏移）"""
        for index in reversed(sorted(indices, key=lambda x: x.row())):
            tid = self._get_task_id_from_row(index.row())
            if tid:
                self.db.delete_task(tid)
                self._remove_row_from_map(index.row(), tid)
            self.table.removeRow(index.row())

    def _remove_table_row_by_task_id(self, task_id: int) -> None:
        """O(1) 按 task_id 查找并删除表格行"""
        row = self._task_row_map.get(task_id)
        if row is not None:
            self.table.removeRow(row)
            self._remove_row_from_map(row, task_id)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """窗口关闭时优雅停止所有任务并释放资源"""
        # 取消所有运行中的下载
        for worker in list(self.workers.values()):
            worker.cancel()
        # 等待线程退出（关闭场景允许短暂阻塞，最多 3 秒/线程）
        for thread in list(self.threads.values()):
            thread.quit()
            thread.wait(3000)
        # 显式关闭持久数据库连接
        self.db.close()
        event.accept()

def run_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

@click.command()
@click.version_option(version=__version__)
def cli() -> None:
    run_gui()

if __name__ == "__main__":
    cli()
