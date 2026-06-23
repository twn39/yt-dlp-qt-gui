import re
from typing import Any

# Pre-compile the regex at module level for efficiency
_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def clean_ansi(text: Any) -> Any:
    """清除 ANSI 转义代码 (如 [0;32m)"""
    if not isinstance(text, str):
        return text
    return _ANSI_ESCAPE.sub("", text).strip()


def format_speed(speed: Any) -> str:
    """格式化下载速度"""
    if speed is None:
        return "--"
    if isinstance(speed, str):
        return clean_ansi(speed)

    # 处理数值类型
    try:
        speed_val = float(speed)
    except (ValueError, TypeError):
        return "--"

    for unit in ["B/s", "KB/s", "MB/s", "GB/s"]:
        if speed_val < 1024.0:
            return f"{speed_val:.1f} {unit}"
        speed_val /= 1024.0
    return f"{speed_val:.1f} TB/s"


def format_eta(seconds: Any) -> str:
    """格式化剩余时间"""
    if seconds is None:
        return "--"
    if isinstance(seconds, str):
        return clean_ansi(seconds)

    # 处理数值类型 (秒)
    try:
        seconds_val = int(seconds)
        m, s = divmod(seconds_val, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return "--"
