import os
from unittest.mock import MagicMock, patch


def test_main_window_init(app_window):
    """Test that the main window initializes with correct title and components."""
    assert "Yt-dlp GUI" in app_window.windowTitle()
    assert app_window.url_input is not None
    assert app_window.format_combo is not None
    assert app_window.download_action.isEnabled()
    assert not app_window.cancel_action.isEnabled()


def test_url_input_persistence(app_window, qtbot):
    """Test that text entered in the URL input is correctly stored."""
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    app_window.url_input.setPlainText(test_url)
    assert app_window.url_input.toPlainText().strip() == test_url


def test_clear_log(app_window):
    """Test the clear log functionality."""
    app_window.log_output.setText("Some log message")
    assert app_window.log_output.toPlainText() != ""
    app_window._clear_log()
    assert app_window.log_output.toPlainText() == ""


def test_paste_from_clipboard(app_window, qtbot):
    """Test pasting from clipboard."""
    from PySide6.QtWidgets import QApplication

    clipboard = QApplication.clipboard()
    test_text = "https://example.com/clipboard"
    clipboard.setText(test_text)

    app_window._paste_url_from_clipboard()
    assert test_text in app_window.url_input.toPlainText()


@patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory")
def test_select_directory(mock_get_dir, app_window):
    """Test directory selection dialog."""
    mock_path = "/mock/path"
    mock_get_dir.return_value = mock_path
    app_window._select_download_directory()
    # Normalize paths for cross-platform comparison
    expected_path = os.path.normpath(mock_path)
    assert app_window.selected_download_path == expected_path
    assert app_window.download_directory_input.text() == expected_path


@patch("PySide6.QtWidgets.QMessageBox.about")
def test_show_about(mock_about, app_window):
    """Test showing the about dialog."""
    app_window._show_about()
    mock_about.assert_called_once()


def test_ui_settings_interaction(app_window):
    """Test that UI settings can be changed."""
    # Format combo
    app_window.format_combo.setCurrentIndex(1)
    assert app_window.format_combo.currentIndex() == 1

    # Proxy input
    app_window.proxy_input.setText("http://proxy:8080")
    assert app_window.proxy_input.text() == "http://proxy:8080"

    # Checkboxes
    app_window.write_subs_checkbox.setChecked(True)
    assert app_window.write_subs_checkbox.isChecked()

    app_window.download_playlist_checkbox.setChecked(True)
    assert app_window.download_playlist_checkbox.isChecked()


def test_update_progress_downloading(app_window):
    """Test _update_progress with downloading status."""
    # Test with full data
    data = {
        "status": "downloading",
        "filename": "test.mp4",
        "total_bytes": 1000,
        "downloaded_bytes": 500,
        "speed_str": "1MB/s",
        "eta_str": "1s",
    }
    app_window._update_progress(data)
    assert app_window.progress_bar.value() == 50
    assert "下载中" in app_window.status_label.text()

    # Test without total_bytes (indeterminate)
    data_no_total = {
        "status": "downloading",
        "filename": "test.mp4",
        "downloaded_bytes": 500,
        "speed_str": "1MB/s",
        "eta_str": "1s",
    }
    app_window._update_progress(data_no_total)
    assert app_window.progress_bar.maximum() == 0  # Indeterminate state


def test_update_progress_merging(app_window):
    """Test _update_progress with merging status."""
    data = {"status": "merging"}
    app_window._update_progress(data)
    assert "合并中" in app_window.status_label.text()
    assert app_window.progress_bar.maximum() == 0


def test_download_finished_success(app_window):
    """Test _download_finished success state."""
    app_window._download_finished(True, "Success Message")
    assert "成功" in app_window.status_label.text()
    assert app_window.progress_bar.value() == 100
    assert app_window.download_action.isEnabled()


def test_download_finished_failure_cancelled(app_window):
    """Test _download_finished cancelled state."""
    app_window._download_finished(False, "用户取消了下载")
    assert "已取消" in app_window.status_label.text()


@patch("PySide6.QtWidgets.QMessageBox.critical")
def test_download_finished_failure_error(mock_critical, app_window):
    """Test _download_finished error state."""
    app_window._download_finished(False, "Fatal Error")
    assert "失败" in app_window.status_label.text()
    mock_critical.assert_called_once()


def test_drag_drop_logic(app_window):
    """Test drag and drop event handling using mocks."""
    from PySide6.QtCore import QMimeData, QUrl

    # Mock DragEnterEvent
    mime_data = MagicMock(spec=QMimeData)
    mime_data.hasUrls.return_value = True
    mime_data.hasText.return_value = False

    event_enter = MagicMock()
    event_enter.mimeData.return_value = mime_data

    app_window.dragEnterEvent(event_enter)
    event_enter.acceptProposedAction.assert_called_once()

    # Mock DropEvent
    mime_data_drop = MagicMock(spec=QMimeData)
    mime_data_drop.hasUrls.return_value = True
    mime_data_drop.urls.return_value = [QUrl("https://example.com")]

    event_drop = MagicMock()
    event_drop.mimeData.return_value = mime_data_drop

    app_window.dropEvent(event_drop)
    assert "https://example.com" in app_window.url_input.toPlainText()
