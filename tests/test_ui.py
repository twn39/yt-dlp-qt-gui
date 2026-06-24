from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableView

from yt_dlp_gui.models import DownloadTask


def test_mainwindow_has_table_view(app_window):
    """Verify MainWindow uses QTableView"""
    assert hasattr(app_window, "table")
    assert isinstance(app_window.table, QTableView)


def test_add_task_creates_table_row(app_window, qtbot):
    """Verify adding a task creates a row in the table model"""
    # Reset model tasks
    app_window.table_model.set_tasks([])

    # Mock DownloadTask object
    task = DownloadTask(
        id=999,
        url="https://example.com/video",
        title="Test Video",
        status="downloading",
        progress=50,
        speed="1.5 MB/s",
        eta="01:00",
        save_path="/tmp",
        format_preset="mp4",
        proxy="",
        concurrent_fragments=1,
        write_subs=False,
        download_playlist=False,
        playlist_items="",
        created_at="2023-01-01",
    )

    # Use internal method to add task to UI/Model
    app_window._add_task_to_table(task)

    model = app_window.table.model()
    assert model.rowCount() == 1

    # Verify title and user role data
    idx_title = model.index(0, 0)
    assert model.data(idx_title, Qt.ItemDataRole.DisplayRole) == "Test Video"
    assert model.data(idx_title, Qt.ItemDataRole.UserRole) == 999

    # Verify status
    idx_status = model.index(0, 1)
    assert model.data(idx_status, Qt.ItemDataRole.DisplayRole) == "downloading"

    # Verify progress
    idx_progress = model.index(0, 2)
    assert model.data(idx_progress, Qt.ItemDataRole.DisplayRole) == 50

    # Verify speed and eta
    idx_speed = model.index(0, 3)
    assert model.data(idx_speed, Qt.ItemDataRole.DisplayRole) == "1.5 MB/s"

    idx_eta = model.index(0, 4)
    assert model.data(idx_eta, Qt.ItemDataRole.DisplayRole) == "01:00"


def test_on_scheduler_status_changed_updates_fields(app_window):
    """Verify that _on_scheduler_status_changed updates status, progress, speed, and eta."""
    # Reset model tasks
    app_window.table_model.set_tasks([])

    # Mock DownloadTask object initially in merging state
    task = DownloadTask(
        id=999,
        url="https://example.com/video",
        title="Test Video",
        status="merging",
        progress=100,
        speed="Merging...",
        eta="--",
        save_path="/tmp",
        format_preset="mp4",
        proxy="",
        concurrent_fragments=1,
        write_subs=False,
        download_playlist=False,
        playlist_items="",
        created_at="2023-01-01",
    )

    app_window._add_task_to_table(task)
    model = app_window.table.model()

    # Trigger finished status change
    app_window._on_scheduler_status_changed(999, "finished")

    # Verify status is updated to finished
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "finished"
    # Verify speed is reset to "--"
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "--"
    # Verify eta is "--"
    assert model.data(model.index(0, 4), Qt.ItemDataRole.DisplayRole) == "--"
    # Verify progress is 100
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == 100

    # Test error status change
    # Set speed/progress back to something else first
    app_window.table_model.update_task_data(
        999, {"speed": "1.2 MB/s", "progress": 50, "eta": "00:10"}
    )
    app_window._on_scheduler_status_changed(999, "error")
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "error"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == 0
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "--"
    assert model.data(model.index(0, 4), Qt.ItemDataRole.DisplayRole) == "--"


def test_mainwindow_show_about_calls_dialog(app_window):
    """验证 MainWindow 触发关于对话框时，调用了 dialog_manager"""
    from unittest.mock import MagicMock

    app_window.dialog_manager = MagicMock()
    app_window._show_about_dialog()
    app_window.dialog_manager.show_about.assert_called_once()


def test_mainwindow_show_add_task_success(app_window):
    """验证当 dialog_manager.show_add_task 返回有效任务时，scheduler 正确添加任务"""
    from unittest.mock import MagicMock

    mock_task = DownloadTask(
        url="https://example.com/video",
        save_path="/tmp",
        format_preset="mp4",
    )
    app_window.dialog_manager = MagicMock()
    app_window.dialog_manager.show_add_task.return_value = mock_task

    app_window.scheduler = MagicMock()
    app_window._show_add_dialog()
    app_window.scheduler.add_task.assert_called_once_with(mock_task)


def test_mainwindow_search_filters_tasks(app_window):
    """验证 MainWindow 搜索栏能正确过滤行显示"""
    app_window.table_model.set_tasks([])
    task_1 = DownloadTask(
        id=1,
        url="http://x.com/1",
        title="Apple Keynote",
        save_path=".",
        format_preset="mp4",
    )
    task_2 = DownloadTask(
        id=2,
        url="http://x.com/2",
        title="Banana Tutorial",
        save_path=".",
        format_preset="mp4",
    )

    app_window._add_task_to_table(task_1)
    app_window._add_task_to_table(task_2)

    # 初始应为 2 条
    assert app_window.proxy_model.rowCount() == 2

    # 输入 "apple"，过滤后应仅剩下 1 条（区分大小写测试）
    app_window._on_search_changed("apple")
    assert app_window.proxy_model.rowCount() == 1

    # 输入 "xyz"，应匹配不到，数量为 0
    app_window._on_search_changed("xyz")
    assert app_window.proxy_model.rowCount() == 0

    # 清空搜索框，应恢复为 2 条
    app_window._on_search_changed("")
    assert app_window.proxy_model.rowCount() == 2


def test_add_task_dialog_fields(qtbot):
    """测试 AddTaskDialog 界面字段的交互与 DownloadTask 数据实体拼装"""
    from yt_dlp_gui.dialogs import AddTaskDialog

    dialog = AddTaskDialog()
    qtbot.addWidget(dialog)

    # 模拟输入链接
    dialog.url_input.setText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    # 模拟更改格式为 1080p 选项
    dialog.format_combo.setCurrentText("1080p")

    # 模拟开启字幕
    dialog.write_subs_checkbox.setChecked(True)

    task_data = dialog.get_task_data()
    assert task_data.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert task_data.format_preset == "bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best"
    assert task_data.write_subs is True


def test_about_dialog_version_label(qtbot):
    """测试 AboutDialog 正确渲染和展示传入的版本号"""
    from PySide6.QtWidgets import QLabel

    from yt_dlp_gui.dialogs import AboutDialog

    dialog = AboutDialog(version="9.9.9")
    qtbot.addWidget(dialog)

    # 检查界面上是否存在包含 "v9.9.9" 的标签文本
    labels = dialog.findChildren(QLabel)
    version_label_found = False
    for label in labels:
        if "v9.9.9" in label.text():
            version_label_found = True
            break
    assert version_label_found is True


def test_mainwindow_delete_selected_task_confirmed(app_window, monkeypatch):
    """测试 MainWindow 中多选并确认删除任务的逻辑流程"""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMessageBox

    # 1. 模拟任务库
    task = DownloadTask(id=123, url="http://x.com", save_path=".", format_preset="mp4")
    app_window.table_model.set_tasks([task])

    # 2. 选中任务行
    app_window.table.selectRow(0)

    # 3. Mock 掉删除弹窗 QMessageBox.question 并使其返回 Yes 确认
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)

    # 4. Mock 掉调度器
    app_window.scheduler = MagicMock()
    app_window.scheduler.threads = {}  # 模拟任务处于静止非运行状态

    # 5. 触发删除
    app_window._delete_selected_task()

    # 6. 断言 scheduler.delete_task 接收到了正确的 task_id
    app_window.scheduler.delete_task.assert_called_once_with(123)


def test_switch_paint(qtbot):
    """测试 Switch 开关自定义绘图方法"""
    from PySide6.QtGui import QPixmap

    from yt_dlp_gui.components import Switch

    switch = Switch("Test Switch")
    qtbot.addWidget(switch)
    switch.show()

    # 渲染以触发 paintEvent
    pixmap = QPixmap(switch.size())
    switch.render(pixmap)

    # 切换状态并再次渲染
    switch.setChecked(True)
    switch.render(pixmap)


def test_progress_delegate_paint_explicit(app_window, monkeypatch):
    """测试自定义进度条委托 Paint 与 initStyleOption 方法"""
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyleOptionViewItem

    from yt_dlp_gui.main import ProgressDelegate
    from yt_dlp_gui.models import DownloadTask

    delegate = ProgressDelegate(app_window)
    pixmap = QPixmap(100, 50)
    painter = QPainter(pixmap)

    option = QStyleOptionViewItem()
    option.rect = pixmap.rect()

    model = app_window.table_model
    task = DownloadTask(id=1, url="http://a", save_path=".", format_preset="best", progress=75)
    model.set_tasks([task])

    index = model.index(0, 2)
    delegate.initStyleOption(option, index)
    delegate.paint(painter, option, index)

    # 非进度列
    index_other = model.index(0, 0)
    delegate.paint(painter, option, index_other)

    # 用 monkeypatch 模拟数据返回 None 的分支
    monkeypatch.setattr(model, "data", lambda idx, role=None: None)
    delegate.paint(painter, option, index)

    painter.end()


def test_dialog_manager_show_about(app_window, monkeypatch):
    """测试 DialogManager 显示关于对话框"""
    from yt_dlp_gui.dialogs import AboutDialog, DialogManager

    monkeypatch.setattr(AboutDialog, "exec", lambda self: None)
    manager = DialogManager(app_window)
    manager.show_about("1.2.3")


def test_dialog_manager_show_add_task(app_window, monkeypatch):
    """测试 DialogManager 显示添加任务对话框"""
    from yt_dlp_gui.dialogs import AddTaskDialog, DialogManager
    from yt_dlp_gui.models import DownloadTask

    dummy = DownloadTask(url="http://example.com", save_path=".", format_preset="best")
    monkeypatch.setattr(AddTaskDialog, "exec", lambda self: 1)  # Accepted
    monkeypatch.setattr(AddTaskDialog, "get_task_data", lambda self: dummy)

    manager = DialogManager(app_window)
    res = manager.show_add_task()
    assert res == dummy

    monkeypatch.setattr(AddTaskDialog, "exec", lambda self: 0)  # Rejected
    res = manager.show_add_task()
    assert res is None


def test_dialog_manager_show_log(app_window, monkeypatch):
    """测试 DialogManager 显示非模态日志对话框"""
    from typing import cast

    from yt_dlp_gui.dialogs import DialogManager, LogDialog

    called = False

    def on_finished():
        nonlocal called
        called = True

    monkeypatch.setattr(LogDialog, "show", lambda self: None)
    manager = DialogManager(app_window)
    dialog = cast(LogDialog, manager.show_log(1, "title", "logs content", on_finished))
    assert dialog is not None
    assert dialog.log_output.toPlainText() == "logs content"

    dialog.finished.emit(0)
    assert called is True


def test_mainwindow_on_sort_changed(app_window):
    """测试 MainWindow 排序选择变更"""
    app_window._on_sort_changed("最佳质量 (MP4)")
    assert app_window.sort_button.text() == "最佳质量 (MP4)"


def test_mainwindow_context_menu(app_window, monkeypatch):
    """测试 MainWindow 的右键上下文菜单及对应各动作"""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMenu, QMessageBox

    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(url="http://a.com", save_path=".", format_preset="best")
    task_id = app_window.db.add_task(task)
    task.id = task_id

    app_window.table_model.set_tasks([task])
    app_window.table.selectRow(0)
    app_window.table.setCurrentIndex(app_window.proxy_model.index(0, 0))

    # 定义 MockMenu 并在 main 模块中替换 QMenu
    class MockMenu(QMenu):
        return_filter = "打开"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.actions_list = []

        def addAction(self, *args, **kwargs):
            action = super().addAction(*args, **kwargs)
            self.actions_list.append(action)
            return action

        def exec(self, *args, **kwargs):
            for act in self.actions_list:
                if MockMenu.return_filter in act.text():
                    return act
            return None

    monkeypatch.setattr("yt_dlp_gui.main.QMenu", MockMenu)

    open_url_called = False

    class MockDesktopServices:
        @staticmethod
        def openUrl(url):
            nonlocal open_url_called
            open_url_called = True
            return True

    monkeypatch.setattr("yt_dlp_gui.main.QDesktopServices", MockDesktopServices)

    # 1. 测试打开保存文件夹
    MockMenu.return_filter = "打开"
    app_window._show_context_menu(app_window.table.pos())
    assert open_url_called is True

    # 2. 测试查看日志
    app_window.dialog_manager = MagicMock()
    MockMenu.return_filter = "查看"
    app_window._show_context_menu(app_window.table.pos())
    app_window.dialog_manager.show_log.assert_called_once()

    # 3. 测试开始 / 重试
    app_window.scheduler = MagicMock()
    app_window.scheduler.threads = {}
    MockMenu.return_filter = "开始"
    app_window._show_context_menu(app_window.table.pos())
    app_window.scheduler.start_task.assert_called_once_with(task_id)

    # 4. 测试停止
    MockMenu.return_filter = "停止"
    app_window._show_context_menu(app_window.table.pos())
    app_window.scheduler.stop_task.assert_called_once_with(task_id)

    # 5. 测试删除
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    MockMenu.return_filter = "删除"
    app_window._show_context_menu(app_window.table.pos())
    app_window.scheduler.delete_task.assert_called_once_with(task_id)


def test_open_task_folder_invalid(app_window, monkeypatch):
    """测试打开不存在的任务保存文件夹弹出警告"""
    from PySide6.QtWidgets import QMessageBox

    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(url="http://a.com", save_path="/nonexistent_path_xyz", format_preset="best")
    task_id = app_window.db.add_task(task)
    task.id = task_id

    app_window.table_model.set_tasks([task])
    app_window.table.selectRow(0)
    app_window.table.setCurrentIndex(app_window.proxy_model.index(0, 0))

    warning_called = False

    def mock_warning(parent, title, text):
        nonlocal warning_called
        warning_called = True

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    app_window._open_task_folder()
    assert warning_called is True


def test_mainwindow_delete_running_task_confirmed(app_window, monkeypatch):
    """测试删除运行中的任务（先停止并询问）"""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMessageBox

    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(id=123, url="http://a.com", save_path=".", format_preset="best")
    app_window.table_model.set_tasks([task])
    app_window.table.selectRow(0)

    app_window.scheduler = MagicMock()
    app_window.scheduler.threads = {123: MagicMock()}

    question_called = False

    def mock_question(parent, title, msg, buttons=None):
        nonlocal question_called
        question_called = True
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", mock_question)

    app_window._delete_selected_task()
    assert question_called is True
    app_window.scheduler.delete_task.assert_called_once_with(123)


def test_mainwindow_delete_selected_task_rejected(app_window, monkeypatch):
    """测试删除任务时选择 No 拒绝逻辑"""
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QMessageBox

    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(id=123, url="http://a.com", save_path=".", format_preset="best")
    app_window.table_model.set_tasks([task])
    app_window.table.selectRow(0)

    app_window.scheduler = MagicMock()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)

    app_window._delete_selected_task()
    app_window.scheduler.delete_task.assert_not_called()


def test_on_scheduler_progress_status(app_window):
    """测试 _on_scheduler_progress 处理各类下载及合并进度"""
    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(id=123, url="http://a.com", save_path=".", format_preset="best")
    app_window.table_model.set_tasks([task])

    # 1. 模拟百分比计算下载
    data_downloading = {
        "status": "downloading",
        "total_bytes": 1000,
        "downloaded_bytes": 500,
        "speed": 100,
        "eta": 10,
    }
    app_window._on_scheduler_progress(123, data_downloading)
    row = app_window.table_model.find_row_by_id(123)
    assert row is not None
    retrieved = app_window.table_model._tasks[row]
    assert retrieved.progress == 50
    assert retrieved.speed == "100.0 B/s"
    assert retrieved.eta == "00:10"

    # 2. 模拟使用 speed_str 与 eta_str
    data_strs = {
        "status": "downloading",
        "total_bytes_estimate": 1000,
        "downloaded_bytes": 250,
        "speed_str": "2.5MB/s",
        "eta_str": "05:00",
    }
    app_window._on_scheduler_progress(123, data_strs)
    row = app_window.table_model.find_row_by_id(123)
    assert row is not None
    retrieved = app_window.table_model._tasks[row]
    assert retrieved.progress == 25
    assert retrieved.speed == "2.5MB/s"
    assert retrieved.eta == "05:00"

    # 3. 模拟合并状态
    data_merging = {
        "status": "merging",
    }
    app_window._on_scheduler_progress(123, data_merging)
    row = app_window.table_model.find_row_by_id(123)
    assert row is not None
    retrieved = app_window.table_model._tasks[row]
    assert retrieved.status == "merging"
    assert retrieved.speed == "Merging..."
    assert retrieved.eta == "--"


def test_scheduler_signals_and_close(app_window):
    """测试 scheduler 相关的辅助槽函数和 closeEvent"""
    from PySide6.QtGui import QCloseEvent

    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(id=123, url="http://a.com", save_path=".", format_preset="best")
    app_window.table_model.set_tasks([task])

    # 标题更新
    app_window._on_scheduler_title_updated(123, "New Video Title")
    row = app_window.table_model.find_row_by_id(123)
    assert row is not None
    assert app_window.table_model._tasks[row].title == "New Video Title"

    # 状态下载/排队中更新
    app_window._on_scheduler_status_changed(123, "downloading")
    assert app_window.table_model._tasks[row].speed == "--"

    # 日志实时输出
    from unittest.mock import MagicMock

    dialog_mock = MagicMock()
    app_window.active_log_dialogs = {123: dialog_mock}
    app_window._on_log(123, "new log output")
    dialog_mock.append_log.assert_called_once_with("new log output")

    # 删除回调
    app_window._on_scheduler_deleted(123)
    assert app_window.table_model.find_row_by_id(123) is None

    # 关闭事件
    app_window.active_log_dialogs = {999: dialog_mock}
    event = QCloseEvent()
    app_window.closeEvent(event)
    dialog_mock.close.assert_called_once()
