from unittest.mock import patch
from yt_dlp_gui.worker import DownloadWorker


def test_worker_initialization():
    """Test that DownloadWorker initializes with correct parameters."""
    urls = ["https://example.com/video1"]
    download_path = "/tmp/downloads"
    worker = DownloadWorker(
        url=urls,
        download_path=download_path,
        format_preset="best",
        proxy="http://127.0.0.1:8080",
        concurrent_fragments=4,
        write_subs=True,
    )

    assert worker.urls == urls
    assert worker.download_path == download_path
    assert worker.proxy == "http://127.0.0.1:8080"
    assert worker.concurrent_fragments == 4
    assert worker.write_subs is True
    assert worker._is_cancelled is False


def test_worker_cancel():
    """Test that the worker can be cancelled."""
    worker = DownloadWorker(url=["url"], download_path="path")
    assert not worker._is_cancelled
    worker.cancel()
    assert worker._is_cancelled


def test_worker_logger(qtbot):
    """Test the YtdlpLogger signal emission."""
    worker = DownloadWorker(url=["url"], download_path="path")
    logger = worker.YtdlpLogger(worker.log_message)

    with qtbot.waitSignal(worker.log_message, timeout=1000) as blocker:
        logger.info("Test Info Message")
    assert blocker.args[0] == "Test Info Message"

    with qtbot.waitSignal(worker.log_message, timeout=1000) as blocker:
        logger.warning("Test Warning")
    assert "警告: Test Warning" in blocker.args[0]

    with qtbot.waitSignal(worker.log_message, timeout=1000) as blocker:
        logger.error("Test Error")
    assert "错误: Test Error" in blocker.args[0]


@patch("yt_dlp.YoutubeDL")
def test_worker_run_success(mock_ytdl, qtbot):
    """Test successful worker run with mocked yt-dlp."""
    worker = DownloadWorker(url=["https://example.com/v"], download_path=".")

    # Mocking behavior
    mock_instance = mock_ytdl.return_value.__enter__.return_value

    with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
        worker.run()

    assert blocker.args[0] is True  # Success
    assert "全部成功" in blocker.args[1]
    mock_instance.extract_info.assert_called_once()


@patch("yt_dlp.YoutubeDL")
def test_worker_run_failure(mock_ytdl, qtbot):
    """Test worker failure handling."""
    worker = DownloadWorker(url=["https://example.com/v"], download_path=".")

    # Mocking an exception
    mock_ytdl.return_value.__enter__.return_value.extract_info.side_effect = Exception(
        "Download Error"
    )

    with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
        worker.run()

    assert blocker.args[0] is False  # Failure
    assert "任务结束" in blocker.args[1]


@patch("yt_dlp.YoutubeDL")
def test_worker_run_complex_config(mock_ytdl, qtbot):
    """Test worker.run with various configuration options."""
    worker = DownloadWorker(
        url=["url"],
        download_path=".",
        proxy="http://proxy",
        concurrent_fragments=8,
        write_subs=True,
        download_playlist=True,
        playlist_items="1-3",
        playlist_random=True,
        max_downloads=5,
    )

    with qtbot.waitSignal(worker.finished, timeout=2000):
        worker.run()

    # Get the options passed to YoutubeDL
    args, kwargs = mock_ytdl.call_args
    opts = args[0]

    assert opts["proxy"] == "http://proxy"
    assert opts["concurrent_fragments"] == 8
    assert opts["writesubtitles"] is True
    assert opts["noplaylist"] is False
    assert opts["playlist_items"] == "1-3"
    assert opts["playlist_random"] is True
    assert opts["max_downloads"] == 5


def test_progress_hook_extensions(qtbot):
    """Test _progress_hook signal emission for specific file extensions."""
    worker = DownloadWorker(url=["url"], download_path=".")

    # Test merging status
    with qtbot.waitSignal(worker.progress, timeout=1000) as blocker:
        worker._progress_hook({"status": "finished", "filename": "test.mp4"})
    assert blocker.args[0]["status"] == "merging"

    # Test subtitle extension (should NOT emit merging)
    import pytest

    with pytest.raises(qtbot.TimeoutError):
        with qtbot.waitSignal(worker.progress, timeout=200):
            worker._progress_hook({"status": "finished", "filename": "test.srt"})


def test_progress_hook_cancellation():
    """Test that _progress_hook raises DownloadCancelled when cancelled."""
    from yt_dlp.utils import DownloadCancelled
    import pytest

    worker = DownloadWorker(url=["url"], download_path=".")
    worker.cancel()

    with pytest.raises(DownloadCancelled):
        worker._progress_hook({"status": "downloading"})
