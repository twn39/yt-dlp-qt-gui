import pytest
from yt_dlp_gui.main import create_app


@pytest.fixture
def app_window(qtbot):
    """Fixture to create and return the MainWindow instance."""
    app, window = create_app()
    qtbot.addWidget(window)
    return window
