"""
Yt-dlp GUI 配置常量

集中管理应用程序配置，便于维护和修改。
"""

import os
import sys
import tempfile
from typing import Final

# =====================
# 下载格式预设
# =====================

# 默认下载格式
DEFAULT_FORMAT: Final[str] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

# 输出文件名模板
OUTPUT_TEMPLATE: Final[str] = "%(title)s [%(id)s].%(ext)s"

# 格式预设选项（下拉菜单显示）
# 每个格式都包含回退选项，避免特定分辨率不可用时失败
FORMAT_PRESETS: Final[dict[str, str]] = {
    "最佳质量 (MP4)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    "最佳质量 (任意格式)": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best",
    "720p": "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best",
    "480p": "bestvideo[height<=480]+bestaudio/bestvideo+bestaudio/best",
    "仅音频 (最佳)": "bestaudio/best",
    "仅音频 (MP3)": "bestaudio[ext=m4a]/bestaudio/best",
}

# =====================
# UI 配置
# =====================

# 窗口设置
WINDOW_TITLE: Final[str] = "Yt-dlp GUI"
WINDOW_MIN_WIDTH: Final[int] = 800
WINDOW_MIN_HEIGHT: Final[int] = 800

# 进度条
PROGRESS_BAR_MAX_WIDTH: Final[int] = 200

# 工具栏图标
ICON_SIZE: Final[int] = 24
ICON_COLOR: Final[str] = "#E0E0E0"
ICON_COLOR_ACTIVE_ACCENT: Final[str] = "#4A90E2"
ICON_COLOR_ACTIVE_DELETE: Final[str] = "#F44336"
ICON_COLOR_ACTIVE_CANCEL: Final[str] = "#FF9800"

# =====================
# 样式文件
# =====================

STYLESHEET_FILE: Final[str] = "dark_theme.qss"

# =====================
# yt-dlp 选项
# =====================

# 禁用 yt-dlp 自带的控制台进度条
NO_PROGRESS: Final[bool] = True

# =====================
# 播放列表选项默认值
# =====================

# 默认不下载播放列表（用户可以通过 UI 启用）
DEFAULT_DOWNLOAD_PLAYLIST: Final[bool] = False

# 默认播放列表项目范围（空表示下载所有）
DEFAULT_PLAYLIST_ITEMS: Final[str] = ""

# 默认不随机顺序下载播放列表
DEFAULT_PLAYLIST_RANDOM: Final[bool] = False

# 默认最大下载数（空表示无限制）
DEFAULT_MAX_DOWNLOADS: Final[str] = ""


# =====================
# 日志配置与管理助手
# =====================


def _config_dir() -> str:
    """返回可写的配置目录，依次尝试 ~/.yt-dlp-gui → 系统 temp"""
    candidates = [os.path.expanduser("~/.yt-dlp-gui")]
    # 打包后的 macOS 沙箱环境下 ~ 可能不可写，fallback 到 temp
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(tempfile.gettempdir(), ".yt-dlp-gui"))
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            # 实际写一次验证权限（某些容器环境 exist_ok=True 也会"成功"返回但写不了）
            probe = os.path.join(d, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return d
        except OSError:
            continue
    # 极端兜底（正常不会走到）
    fallback = tempfile.gettempdir()
    os.makedirs(fallback, exist_ok=True)
    return fallback


def get_log_dir() -> str:
    """获取日志存储目录并确保其存在"""
    log_dir = os.path.join(_config_dir(), "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        log_dir = tempfile.gettempdir()
    return log_dir


def get_app_startup_log_path() -> str:
    """启动日志路径（顶层 try/except 会把 traceback 落在这里）"""
    return os.path.join(_config_dir(), "startup.log")


def get_task_log_path(task_id: int) -> str:
    """获取特定任务的日志文件路径"""
    return os.path.join(get_log_dir(), f"task_{task_id}.log")


def remove_task_log(task_id: int) -> None:
    """删除特定任务的日志文件"""
    try:
        path = get_task_log_path(task_id)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
