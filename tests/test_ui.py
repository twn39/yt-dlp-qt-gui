from PySide6.QtWidgets import QTableWidget, QProgressBar
from PySide6.QtCore import Qt


def test_mainwindow_has_table_widget(app_window):
    """Verify MainWindow uses QTableWidget"""
    assert hasattr(app_window, 'table')
    assert isinstance(app_window.table, QTableWidget)


def test_add_task_creates_table_row(app_window, qtbot):
    """Verify adding a task creates a row in the table"""
    app_window.table.setRowCount(0)

    # Mock task data
    task_data = {
        'id': 999,
        'url': 'https://example.com/video',
        'title': 'Test Video',
        'status': 'downloading',
        'progress': 50,
        'speed': '1.5 MB/s',
        'eta': '01:00',
        'save_path': '/tmp',
        'format_preset': 'mp4',
        'proxy': '',
        'concurrent_fragments': 1,
        'write_subs': False,
        'download_playlist': False,
        'playlist_items': '',
        'created_at': '2023-01-01'
    }

    # Use internal method to add task to UI
    app_window._add_task_to_table(task_data)

    assert app_window.table.rowCount() == 1

    # Verify title
    title_item = app_window.table.item(0, 0)
    assert title_item.text() == 'Test Video'
    assert title_item.data(Qt.ItemDataRole.UserRole) == 999

    # Verify status
    status_item = app_window.table.item(0, 1)
    assert status_item.text() == 'downloading'

    # Verify progress bar
    progress_widget = app_window.table.cellWidget(0, 2)
    assert progress_widget is not None
    pbar = progress_widget.findChild(QProgressBar)
    assert pbar is not None
    assert pbar.value() == 50

    # Verify speed and eta
    speed_item = app_window.table.item(0, 3)
    assert speed_item.text() == '1.5 MB/s'

    eta_item = app_window.table.item(0, 4)
    assert eta_item.text() == '01:00'
