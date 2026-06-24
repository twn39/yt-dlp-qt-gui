from yt_dlp_gui.utils import clean_ansi, format_eta, format_speed


def test_clean_ansi() -> None:
    # Strings containing ANSI escape codes
    assert clean_ansi("\x1b[0;32mTest Video Title\x1b[0m") == "Test Video Title"
    assert clean_ansi("\x1b[31;1;4mRed Underlined\x1b[0m Text") == "Red Underlined Text"

    # Regular string without codes
    assert clean_ansi("Hello World") == "Hello World"

    # Edge cases / Non-string input
    assert clean_ansi(None) is None
    assert clean_ansi(12345) == 12345


def test_format_speed() -> None:
    # None value
    assert format_speed(None) == "--"

    # String inputs
    assert format_speed("100 KB/s") == "100 KB/s"
    assert format_speed("\x1b[32m5.2 MB/s\x1b[0m") == "5.2 MB/s"

    # Numeric inputs (bytes per second)
    assert format_speed(500) == "500.0 B/s"
    assert format_speed(1024) == "1.0 KB/s"
    assert format_speed(1536) == "1.5 KB/s"
    assert format_speed(1048576) == "1.0 MB/s"
    assert format_speed(1073741824) == "1.0 GB/s"
    assert format_speed(1099511627776) == "1.0 TB/s"

    # Invalid numeric strings or objects
    assert format_speed("invalid_speed") == "invalid_speed"
    assert format_speed({}) == "--"


def test_format_eta() -> None:
    # None value
    assert format_eta(None) == "--"

    # String inputs
    assert format_eta("01:23") == "01:23"
    assert format_eta("\x1b[33m02:05:10\x1b[0m") == "02:05:10"

    # Numeric inputs (seconds)
    assert format_eta(45) == "00:45"
    assert format_eta(125) == "02:05"
    assert format_eta(3600) == "01:00:00"
    assert format_eta(3665) == "01:01:05"
    assert format_eta(90065) == "25:01:05"

    # Invalid / Unparsable inputs
    assert format_eta("not_a_number") == "not_a_number"
    assert format_eta([]) == "--"


def test_setup_environment() -> None:
    import os

    from yt_dlp_gui.__main__ import setup_environment

    # Run it
    setup_environment()
    paths = os.environ.get("PATH", "").split(os.pathsep)
    assert len(paths) > 0
