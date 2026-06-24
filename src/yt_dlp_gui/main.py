import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any, Dict, Optional

import click
import qtawesome as qta
from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QUrl,
    Slot,
)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import STYLESHEET_FILE, get_task_log_path
from .database import Database
from .dialogs import DialogManager
from .models import DownloadTask, TaskTableModel
from .scheduler import DownloadScheduler
from .utils import clean_ansi, format_eta, format_speed

try:
    __version__ = _pkg_version("yt-dlp-qt-gui")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


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


class ProgressDelegate(QStyledItemDelegate):
    """自定义进度条委托，通过 QPainter 直接在单元格内绘制进度条"""

    def initStyleOption(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        super().initStyleOption(option, index)
        if index.column() == 2:
            option.text = ""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if index.column() == 2:
            # 绘制单元格的标准背景、选中状态、交替背景和边框
            super().paint(painter, option, index)

            progress = index.data(Qt.ItemDataRole.DisplayRole)
            if progress is None:
                progress = 0

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 进度条布局尺寸
            rect = option.rect
            margin_h = 15
            bar_h = 8

            bar_w = rect.width() - 2 * margin_h
            if bar_w < 0:
                bar_w = 0
            bar_y = rect.y() + (rect.height() - bar_h) // 2
            bar_x = rect.x() + margin_h

            bg_rect = QRect(bar_x, bar_y, bar_w, bar_h)

            # 绘制背景：带 1px 边框 #080808，底色 #0D0D0D
            painter.setPen(QColor("#080808"))
            painter.setBrush(QColor("#0D0D0D"))
            painter.drawRoundedRect(bg_rect, 3, 3)

            # 绘制进度滑块（渐变色：从 #3D3D3D 到 #4A90E2）
            if progress > 0:
                chunk_w = int(bar_w * (progress / 100.0))
                if chunk_w < 4 and progress > 0:
                    chunk_w = 4
                if chunk_w > bar_w:
                    chunk_w = bar_w

                chunk_rect = QRect(bar_x, bar_y, chunk_w, bar_h)
                gradient = QLinearGradient(bar_x, bar_y, bar_x + chunk_w, bar_y)
                gradient.setColorAt(0.0, QColor("#3D3D3D"))
                gradient.setColorAt(1.0, QColor("#4A90E2"))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(gradient)
                painter.drawRoundedRect(chunk_rect, 2, 2)

            painter.restore()
        else:
            super().paint(painter, option, index)


class MainWindow(QMainWindow):
    def __init__(
        self,
        db: Database,
        scheduler: DownloadScheduler,
        dialog_manager: Optional[DialogManager] = None,
    ):
        super().__init__()
        self.db = db
        self.scheduler = scheduler
        self.dialog_manager = dialog_manager or DialogManager(self)
        self.active_log_dialogs: Dict[int, Any] = {}  # 跟踪打开的日志窗口

        # 数据模型初始化
        self.table_model = TaskTableModel()

        # 连接调度器信号
        self.scheduler.task_added.connect(self._add_task_to_table)
        self.scheduler.task_status_changed.connect(self._on_scheduler_status_changed)
        self.scheduler.task_progress_changed.connect(self._on_scheduler_progress)
        self.scheduler.task_title_updated.connect(self._on_scheduler_title_updated)
        self.scheduler.task_log_emitted.connect(self._on_log)
        self.scheduler.task_deleted.connect(self._on_scheduler_deleted)

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
        main_layout.setContentsMargins(8, 8, 8, 8)  # 缩小边距
        main_layout.setSpacing(0)

        # 容器面板 Panel
        self.table_panel = QFrame()
        self.table_panel.setObjectName("table_panel")
        panel_layout = QVBoxLayout(self.table_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)  # 去掉内边距，使表格填充满面板

        # 下载列表表格
        self.table = QTableView()

        # 创建并挂载 Proxy Model
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterKeyColumn(0)  # 第 0 列：名称列
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.table.setModel(self.proxy_model)
        self.table.setItemDelegateForColumn(2, ProgressDelegate(self))

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

        # 禁用表头点击排序：改用工具栏下拉框触发 DB 层排序
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
        self.table.selectionModel().selectionChanged.connect(self._update_status_counts)

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
        info_action.triggered.connect(self._show_about_dialog)
        toolbar.addAction(info_action)

        # 排序控件：弹性间隔 + QToolButton+QMenu，风格与左侧工具栏按鈕完全一致
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        toolbar.addWidget(spacer)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(" 搜索任务名称...")
        self.search_input.setFixedWidth(180)
        self.search_input.setClearButtonEnabled(True)

        # 搜索框内置放大镜图标
        search_action = QAction(qta.icon("fa5s.search", color="#888888"), "", self)
        self.search_input.addAction(search_action, QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self._on_search_changed)

        toolbar.addWidget(self.search_input)

        self.sort_button = QToolButton(self)
        self.sort_button.setIcon(qta.icon("fa5s.sort-amount-down", color="#BBBBBB"))
        self.sort_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.sort_button.setText(next(iter(self._sort_options)))  # 默认“创建时间 ↓”
        self.sort_button.setToolTip("排序方式")

        _sort_menu = QMenu(self)
        for _lbl in self._sort_options:
            _sort_menu.addAction(_lbl).triggered.connect(
                lambda checked=False, lbl=_lbl: self._on_sort_changed(lbl)
            )
        self.sort_button.setMenu(_sort_menu)
        toolbar.addWidget(self.sort_button)

    def _update_status_counts(self):
        total = self.table_model.rowCount()
        selected = len(self.table.selectionModel().selectedRows())
        self.task_count_info.setText(f"{total} 个项目, 已选择 {selected} 个  ")

    def _apply_dark_theme(self):
        qss = load_stylesheet()
        if qss:
            self.setStyleSheet(qss)

    def _show_about_dialog(self) -> None:
        """显示「关于」对话框"""
        self.dialog_manager.show_about(__version__)

    def _on_sort_changed(self, label: str) -> None:
        """排序选项变更时更新按鈕文字并重新加载"""
        self.sort_button.setText(label)
        self._load_tasks_from_db()

    def _load_tasks_from_db(self) -> None:
        """从 DB 加载所有任务并刷新 Model"""
        current = (
            self.sort_button.text()
            if hasattr(self, "sort_button")
            else next(iter(self._sort_options))
        )
        sort_col, sort_dir = self._sort_options.get(current, ("created_at", "DESC"))
        tasks = self.db.get_all_tasks(sort_col=sort_col, sort_dir=sort_dir)
        self.table_model.set_tasks(tasks)
        self._update_status_counts()

    def _add_task_to_table(self, task: DownloadTask) -> None:
        self.table_model.add_task(task)
        self._update_status_counts()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        open_folder_action = menu.addAction(
            qta.icon("fa5s.folder-open", color="#FFFFFF"), "打开保存文件夹"
        )
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
        index = self.table.currentIndex()
        if not index.isValid():
            return
        row = index.row()
        task_id = self._get_task_id_from_row(row)
        if not task_id:
            return

        task = self.db.get_task(task_id)
        if task and task.save_path:
            path = task.save_path
            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                QMessageBox.warning(self, "错误", f"目录不存在: {path}")

    def _view_selected_task_log(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return
        row = index.row()
        task_id = self._get_task_id_from_row(row)
        if not task_id:
            return

        title = (
            self.table_model.data(self.table_model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            or "未知任务"
        )

        # 如果窗口已打开，则置顶
        if task_id in self.active_log_dialogs:
            self.active_log_dialogs[task_id].raise_()
            self.active_log_dialogs[task_id].activateWindow()
            return

        logs = "暂无日志信息...\n"
        try:
            log_path = get_task_log_path(task_id)
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    logs = f.read()
        except Exception as e:
            logs = f"无法读取日志: {e}\n"

        dialog = self.dialog_manager.show_log(
            task_id,
            title,
            logs,
            on_finished=lambda: self.active_log_dialogs.pop(task_id, None),
        )
        self.active_log_dialogs[task_id] = dialog

    @Slot()
    def _show_add_dialog(self) -> None:
        task = self.dialog_manager.show_add_task()
        if task:
            self.scheduler.add_task(task)

    def _get_task_id_from_row(self, row):
        index = self.proxy_model.index(row, 0)
        return index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None

    def _start_selected_task(self):
        indices = self.table.selectionModel().selectedRows()
        for idx in indices:
            tid = self._get_task_id_from_row(idx.row())
            if tid:
                self.scheduler.start_task(tid)

    def _stop_selected_task(self):
        indices = self.table.selectionModel().selectedRows()
        for idx in indices:
            tid = self._get_task_id_from_row(idx.row())
            if tid:
                self.scheduler.stop_task(tid)

    def _delete_selected_task(self) -> None:
        indices = self.table.selectionModel().selectedRows()
        if not indices:
            return

        tids = [self._get_task_id_from_row(idx.row()) for idx in indices]
        tids = [tid for tid in tids if tid is not None]

        # 分类：静止任务 vs 运行中任务
        running_tids = [tid for tid in tids if tid in self.scheduler.threads]
        idle_tids = [tid for tid in tids if tid not in self.scheduler.threads]

        if running_tids:
            msg = (
                f"选中的 {len(tids)} 个任务中，"
                f"有 {len(running_tids)} 个正在下载。\n\n"
                f"是否立即停止并删除全部 {len(tids)} 个任务？"
            )
            confirm = QMessageBox.question(
                self,
                "确认停止并删除",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        else:
            confirm = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除选中的 {len(idle_tids)} 个任务吗？",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        # 循环删除所有选中的任务
        for tid in tids:
            self.scheduler.delete_task(tid)

    def _on_scheduler_status_changed(self, task_id: int, status: str) -> None:
        updates = {"status": status}
        if status == "finished":
            updates.update({"progress": 100, "speed": "--", "eta": "--"})
        elif status in ("cancelled", "error"):
            updates.update({"progress": 0, "speed": "--", "eta": "--"})
        elif status in ("downloading", "queued"):
            updates.update({"speed": "--", "eta": "--"})
        self._update_table_row(task_id, updates)

    @Slot(int, dict)
    def _on_scheduler_progress(self, task_id: int, data: dict[str, Any]) -> None:
        if data["status"] == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes")

            progress = 0
            if total and downloaded:
                progress = int(downloaded / total * 100)

            speed_str = data.get("speed_str") or data.get("_speed_str")
            if speed_str:
                speed_str = clean_ansi(speed_str)
            else:
                speed_str = format_speed(data.get("speed"))

            eta_str = data.get("eta_str") or data.get("_eta_str")
            if eta_str:
                eta_str = clean_ansi(eta_str)
            else:
                eta_str = format_eta(data.get("eta"))

            self._update_table_row(
                task_id, {"progress": progress, "speed": speed_str, "eta": eta_str}
            )
        elif data["status"] == "merging":
            self._update_table_row(
                task_id, {"status": "merging", "speed": "Merging...", "eta": "--"}
            )

    def _on_scheduler_title_updated(self, task_id: int, title: str) -> None:
        self._update_table_row(task_id, {"title": title})

    def _on_scheduler_deleted(self, task_id: int) -> None:
        self.table_model.remove_task(task_id)
        self._update_status_counts()

    def _update_table_row(self, task_id: int, data: dict[str, Any]) -> None:
        """更新模型中的任务数据，由视图自动重绘"""
        self.table_model.update_task_data(task_id, data)

    @Slot(int, str)
    def _on_log(self, task_id, msg):
        # 如果日志窗口打开，实时更新
        if task_id in self.active_log_dialogs:
            self.active_log_dialogs[task_id].append_log(msg)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """窗口关闭事件处理"""
        # 关闭所有打开的日志对话框
        for dialog in list(self.active_log_dialogs.values()):
            dialog.close()
        event.accept()

    def _on_search_changed(self, text: str) -> None:
        """当搜索输入框内容改变时，更新过滤器参数"""
        self.proxy_model.setFilterFixedString(text.strip())


def run_gui():
    app = QApplication(sys.argv)
    db = Database()
    scheduler = DownloadScheduler(db)

    # 绑定生命周期（当事件循环正常退出时，在 app 销毁前触发）
    app.aboutToQuit.connect(scheduler.shutdown)
    app.aboutToQuit.connect(db.close)

    try:
        window = MainWindow(db, scheduler)
        window.show()
        sys.exit(app.exec())
    finally:
        # 双重保障，确保在非 GUI 环境下或在异常退出时也能正确释放资源
        scheduler.shutdown()
        db.close()


@click.command()
@click.version_option(version=__version__)
def cli() -> None:
    run_gui()


if __name__ == "__main__":
    cli()
