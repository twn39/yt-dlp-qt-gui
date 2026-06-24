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
