import pytest
from PySide6.QtWidgets import QListWidget
from yt_dlp_gui.components import TaskItemWidget

def test_mainwindow_has_list_widget(app_window):
    """Verify MainWindow uses QListWidget instead of QTableWidget"""
    assert hasattr(app_window, 'list_widget')
    assert isinstance(app_window.list_widget, QListWidget)
    # assert not hasattr(app_window, 'table') # We removed 'table' attribute in refactor

def test_add_task_creates_item_widget(app_window, qtbot):
    """Verify adding a task creates a TaskItemWidget"""
    app_window.list_widget.clear()
    
    # Mock task data
    task_data = {
        'id': 999,
        'url': 'https://example.com/video',
        'title': 'Test Video',
        'status': 'waiting',
        'progress': 0,
        'speed': '0 KB/s',
        'eta': '00:00',
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
    app_window._add_task_to_list(task_data)
    
    assert app_window.list_widget.count() == 1
    item = app_window.list_widget.item(0)
    widget = app_window.list_widget.itemWidget(item)
    assert isinstance(widget, TaskItemWidget)
    assert widget.title_label.text() == 'Test Video'
