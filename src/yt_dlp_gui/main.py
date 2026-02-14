import sys
import os
from typing import Any, Dict
import click
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QProgressBar, QPushButton,
    QMessageBox, QHeaderView, QAbstractItemView, QToolBar, QMenu, QLabel,
    QFrame
)
from PySide6.QtCore import Qt, QThread, Slot, QSize, QUrl
from PySide6.QtGui import QAction, QIcon, QFont, QDesktopServices

from .worker import DownloadWorker
from .config import (
    WINDOW_TITLE, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    STYLESHEET_FILE, ICON_COLOR, ICON_COLOR_ACTIVE_ACCENT,
    ICON_COLOR_ACTIVE_DELETE, ICON_COLOR_ACTIVE_CANCEL
)
from .database import Database
from .dialogs import AddTaskDialog, LogDialog

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
        self.active_log_dialogs: Dict[int, Any] = {} # 跟踪打开的日志窗口
        
        self.setWindowTitle(f"Yt-dlp GUI — 现代化视频下载管理器")
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
        
        # 启用点击表头排序
        self.table.setSortingEnabled(True)
        
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

    def _load_tasks_from_db(self):
        self.table.setSortingEnabled(False) # 临时禁用
        self.table.setRowCount(0)
        tasks = self.db.get_all_tasks()
        for task in tasks:
            self._add_task_to_table(task)
        self.table.setSortingEnabled(True) # 恢复排序
        self._update_status_counts()

    def _add_task_to_table(self, task):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 将 ID 存在 UserRole 中
        title = task['title'] or task['url']
        icon_color = "#4CAF50" if task['status'] == "finished" else "#FFFFFF"
        icon_name = "fa5s.file-video" if task['status'] == "finished" else "fa5s.video"
        title_item = QTableWidgetItem(qta.icon(icon_name, color=icon_color), title)
        title_item.setData(Qt.ItemDataRole.UserRole, task['id'])
        self.table.setItem(row, 0, title_item)
        
        status_item = QTableWidgetItem(self._get_status_icon(task['status']), task['status'])
        self.table.setItem(row, 1, status_item)
        
        pbar_container = QWidget()
        pbar_container.setStyleSheet("background: transparent;")
        pbar_layout = QVBoxLayout(pbar_container)
        pbar_layout.setContentsMargins(15, 6, 15, 6)
        pbar = QProgressBar()
        pbar.setValue(task['progress'] or 0)
        pbar_layout.addWidget(pbar)
        self.table.setCellWidget(row, 2, pbar_container)
        
        self.table.setItem(row, 3, QTableWidgetItem(task['speed'] or "--"))
        self.table.setItem(row, 4, QTableWidgetItem(task['eta'] or "--"))

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
        if row < 0: return
        task_id = self._get_task_id_from_row(row)
        if not task_id: return
        
        task = self.db.get_task(task_id)
        if task and task['save_path']:
            path = task['save_path']
            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(self, "错误", f"目录不存在: {path}")

    def _view_selected_task_log(self):
        row = self.table.currentRow()
        if row < 0: return
        task_id = self._get_task_id_from_row(row)
        if not task_id: return
        
        title = self.table.item(row, 0).text()
        
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
    def _show_add_dialog(self):
        dialog = AddTaskDialog(self)
        if dialog.exec():
            task_data = dialog.get_task_data()
            if not task_data['url']: return
            task_id = self.db.add_task(task_data)
            task = self.db.get_task(task_id)
            
            self.table.setSortingEnabled(False)
            self._add_task_to_table(task)
            self.table.setSortingEnabled(True)
            
            self._start_task(task_id)

    def _get_task_id_from_row(self, row):
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _start_selected_task(self):
        rows = set(index.row() for index in self.table.selectedIndexes())
        for row in rows:
            tid = self._get_task_id_from_row(row)
            if tid: self._start_task(tid)

    def _start_task(self, task_id):
        if task_id in self.threads: return
        task = self.db.get_task(task_id)
        if not task: return

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
        worker.log_message.connect(self._on_log) # 连接日志信号
        thread.started.connect(worker.run)
        
        self.threads[task_id] = thread
        self.workers[task_id] = worker
        thread.start()

    def _stop_selected_task(self):
        rows = set(index.row() for index in self.table.selectedIndexes())
        for row in rows:
            tid = self._get_task_id_from_row(row)
            if tid and tid in self.workers:
                self.workers[tid].cancel()

    def _delete_selected_task(self):
        indices = self.table.selectionModel().selectedRows()
        if not indices: return
        
        confirm = QMessageBox.question(self, "确认删除", f"确定要删除选中的 {len(indices)} 个任务吗？")
        if confirm == QMessageBox.StandardButton.Yes:
            for index in reversed(sorted(indices, key=lambda x: x.row())):
                tid = self._get_task_id_from_row(index.row())
                if tid and tid in self.threads: continue
                if tid: self.db.delete_task(tid)
                self.table.removeRow(index.row())
            self._update_status_counts()

    def _update_table_row(self, task_id, data):
        for row in range(self.table.rowCount()):
            if self._get_task_id_from_row(row) == task_id:
                if 'status' in data:
                    st = data['status']
                    self.table.item(row, 1).setIcon(self._get_status_icon(st))
                    self.table.item(row, 1).setText(st)
                    # 如果完成，第一列的图标也变绿
                    if st == "finished":
                        self.table.item(row, 0).setIcon(qta.icon("fa5s.file-video", color="#4CAF50"))
                if 'progress' in data:
                    pcont = self.table.cellWidget(row, 2)
                    if pcont:
                        pbar = pcont.findChild(QProgressBar)
                        if pbar: pbar.setValue(data['progress'])
                if 'speed' in data: self.table.item(row, 3).setText(data['speed'])
                if 'eta' in data: self.table.item(row, 4).setText(data['eta'])
                if 'title' in data: self.table.item(row, 0).setText(data['title'])
                break

    def _clean_ansi(self, text):
        """清除 ANSI 转义代码 (如 [0;32m)"""
        if not isinstance(text, str): return text
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    def _format_speed(self, speed):
        """格式化下载速度"""
        if speed is None: return "--"
        if isinstance(speed, str): return self._clean_ansi(speed)
        
        # 处理数值类型
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024.0:
                return f"{speed:.1f} {unit}"
            speed /= 1024.0
        return f"{speed:.1f} TB/s"

    def _format_eta(self, seconds):
        """格式化剩余时间"""
        if seconds is None: return "--"
        if isinstance(seconds, str): return self._clean_ansi(seconds)
        
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
    def _on_finished(self, task_id, success, message):
        status = "finished" if success else ("cancelled" if "用户取消" in message else "error")
        self.db.update_task(task_id, {"status": status, "progress": 100 if success else 0})
        self._update_table_row(task_id, {"status": status, "progress": 100 if success else 0})
        if task_id in self.threads:
            self.threads[task_id].quit()
            self.threads[task_id].wait()
            del self.threads[task_id]
        if task_id in self.workers: del self.workers[task_id]

def run_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

@click.command()
@click.version_option(version="0.2.0")
def cli():
    run_gui()

if __name__ == "__main__":
    cli()
