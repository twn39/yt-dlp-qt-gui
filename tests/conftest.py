import pytest
from yt_dlp_gui.main import MainWindow


@pytest.fixture
def app_window(qtbot):
    """Fixture to create and return the MainWindow instance."""
    window = MainWindow()
    qtbot.addWidget(window)
    return window
