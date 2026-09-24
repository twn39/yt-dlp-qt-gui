from unittest.mock import MagicMock, patch

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

from yt_dlp_gui.dialogs import AddTaskDialog
from yt_dlp_gui.models import DownloadTask
from yt_dlp_gui.worker import DownloadWorker

# ==========================================
# 1. DownloadTask Models & Edge Cases
# ==========================================


def test_download_task_from_dict_edge_cases():
    """Test DownloadTask.from_dict handling invalid numbers and boolean coercion."""
    raw_data = {
        "id": 1,
        "url": "https://example.com/video",
        "title": None,
        "status": "pending",
        "progress": None,
        "speed": None,
        "eta": None,
        "save_path": "/tmp",
        "format_preset": "best",
        "proxy": "",  # Empty string should become None
        "concurrent_fragments": "invalid_number",  # Non-digit string
        "max_downloads": "invalid_number",  # Non-digit string
        "write_subs": 1,  # SQLite 1 integer coercion to bool
        "download_playlist": 0,  # SQLite 0 integer coercion to bool
        "playlist_items": "",
        "no_cookies": 1,
        "cookie_browser": "edge",
    }

    task = DownloadTask.from_dict(raw_data)

    assert task.title == "正在解析..."
    assert task.progress == 0
    assert task.speed == "--"
    assert task.eta == "--"
    assert task.proxy is None
    assert task.concurrent_fragments is None
    assert task.max_downloads is None
    assert task.write_subs is True
    assert task.download_playlist is False
    assert task.playlist_items is None
    assert task.no_cookies is True
    assert task.cookie_browser == "edge"


# ==========================================
# 2. Worker Exception & Logging Edge Cases
# ==========================================


def test_worker_run_empty_url(qtbot):
    """Test worker.run when URL is empty."""
    worker = DownloadWorker(task_id=1, url="", download_path=".")

    with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
        worker.run()

    assert blocker.args[0] == 1
    assert blocker.args[1] is False
    assert "URL 不能为空" in blocker.args[2]


def test_worker_log_file_open_failure(qtbot):
    """Test worker behavior when log file fails to open due to permission error."""
    worker = DownloadWorker(task_id=1, url="https://example.com", download_path=".")

    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        # Should not crash, just fail open and continue
        worker._write_log("Test log")
        assert worker._log_file is None


def test_worker_progress_hook_error_status(qtbot):
    """Test progress hook when status is 'error' or missing filename."""
    worker = DownloadWorker(task_id=1, url="https://example.com", download_path=".")

    # Status error
    with qtbot.waitSignal(worker.log_message, timeout=1000) as blocker:
        worker._progress_hook({"status": "error", "filename": "failed.mp4"})
    assert "下载错误: failed.mp4" in blocker.args[1]

    # Finished status without filename
    with qtbot.waitSignal(worker.log_message, timeout=1000) as blocker:
        worker._progress_hook({"status": "finished", "info_dict": {"title": "Sample Title"}})
    assert "处理步骤完成: Sample Title" in blocker.args[1]


# ==========================================
# 3. AddTaskDialog Clipboard Autofill Edge Cases
# ==========================================


def test_add_task_dialog_initial_url(qtbot):
    """Test AddTaskDialog with explicit initial_url."""
    dialog = AddTaskDialog(initial_url="https://bilibili.com/video/BV123")
    qtbot.addWidget(dialog)
    assert dialog.url_input.text() == "https://bilibili.com/video/BV123"


def test_add_task_dialog_clipboard_autofill(qtbot):
    """Test AddTaskDialog auto-filling valid URL from clipboard."""
    clipboard = QApplication.clipboard()
    clipboard.setText("https://youtube.com/watch?v=test")

    dialog = AddTaskDialog()
    qtbot.addWidget(dialog)
    assert dialog.url_input.text() == "https://youtube.com/watch?v=test"

    # Reset clipboard to non-URL text
    clipboard.setText("Not a URL string")
    dialog_non_url = AddTaskDialog()
    qtbot.addWidget(dialog_non_url)
    assert dialog_non_url.url_input.text() == ""


# ==========================================
# 4. Drag and Drop Edge Cases
# ==========================================


def test_mainwindow_drag_and_drop_url(app_window):
    """Test MainWindow dragEnterEvent and dropEvent with URL mime data."""
    mime_data = QMimeData()
    mime_data.setUrls([QUrl("https://youtube.com/watch?v=dragtest")])

    mock_drag_event = MagicMock()
    mock_drag_event.mimeData.return_value = mime_data

    app_window.dragEnterEvent(mock_drag_event)
    mock_drag_event.acceptProposedAction.assert_called_once()

    mock_drop_event = MagicMock()
    mock_drop_event.mimeData.return_value = mime_data

    with patch.object(app_window.dialog_manager, "show_add_task", return_value=None) as mock_show:
        app_window.dropEvent(mock_drop_event)
        mock_show.assert_called_once_with(initial_url="https://youtube.com/watch?v=dragtest")


def test_mainwindow_drag_and_drop_invalid(app_window):
    """Test MainWindow dragEnterEvent with empty mime data."""
    mime_data = QMimeData()

    mock_drag_event = MagicMock()
    mock_drag_event.mimeData.return_value = mime_data

    app_window.dragEnterEvent(mock_drag_event)
    mock_drag_event.acceptProposedAction.assert_not_called()


# ==========================================
# 5. Scheduler Queue Drain & Edge Cases
# ==========================================


def test_scheduler_non_existent_task_operations(app_window):
    """Test starting, stopping, and deleting tasks that do not exist."""
    scheduler = app_window.scheduler

    # Operations on non-existent task IDs should execute safely without crashing
    scheduler.start_task(99999)
    scheduler.stop_task(99999)
    scheduler.delete_task(99999)

    assert 99999 not in scheduler._waiting_queue
    assert 99999 not in scheduler._active_task_ids


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_queue_draining_deleted_tasks(mock_run_thread, app_window):
    """Test _schedule_next iteratively skipping tasks deleted from DB."""
    scheduler = app_window.scheduler
    scheduler.max_concurrent_downloads = 1

    # Populate queue with 2 task IDs: id1 (deleted from DB), id2 (exists)
    task2 = DownloadTask(url="http://v2", save_path=".", format_preset="mp4")
    id2 = scheduler.db.add_task(task2)

    scheduler._waiting_queue = [99998, id2]  # 99998 is non-existent/deleted task ID

    scheduler._schedule_next()

    # _schedule_next should skip 99998 and run id2
    assert id2 in scheduler._active_task_ids
    assert mock_run_thread.called
