import pytest

from yt_dlp_gui.database import Database
from yt_dlp_gui.main import MainWindow
from yt_dlp_gui.scheduler import DownloadScheduler


@pytest.fixture
def app_window(qtbot, tmp_path):
    """Fixture to create and return the MainWindow instance with clean isolation."""
    db_file = tmp_path / "test_downloads.db"
    db = Database(db_path=str(db_file))
    scheduler = DownloadScheduler(db)

    window = MainWindow(db, scheduler)
    qtbot.addWidget(window)

    yield window

    # Clean up background threads and DB connections deterministically after each test
    scheduler.shutdown()
    db.close()
