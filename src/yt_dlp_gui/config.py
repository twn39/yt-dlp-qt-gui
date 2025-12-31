"""
Yt-dlp GUI 配置常量

集中管理应用程序配置，便于维护和修改。
"""

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
ICON_COLOR: Final[str] = "#cccccc"
ICON_COLOR_ACTIVE_ACCENT: Final[str] = "#00aaff"
ICON_COLOR_ACTIVE_DELETE: Final[str] = "#ff6b6b"
ICON_COLOR_ACTIVE_CANCEL: Final[str] = "#ffcc00"

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
