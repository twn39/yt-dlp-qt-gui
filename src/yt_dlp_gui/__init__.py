"""Yt-dlp GUI - 现代化视频下载工具

支持从 YouTube、Bilibili、Vimeo 等数千个视频网站下载视频。
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # 从已安装的包元数据读取版本（唯一版本来源：pyproject.toml）
    __version__ = version("yt-dlp-qt-gui")
except PackageNotFoundError:
    # 仅在未通过 pip/uv 安装时（例如直接 clone 运行）出现
    __version__ = "0.0.0-dev"


# cli 延迟导入以避免循环依赖（main.py → __init__.py → main.py）
# 外部使用者请直接 from yt_dlp_gui.main import cli
def __getattr__(name: str):  # noqa: N807
    if name == "cli":
        from .main import cli

        return cli
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["cli", "__version__"]
