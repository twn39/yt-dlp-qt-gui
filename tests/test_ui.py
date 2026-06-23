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
