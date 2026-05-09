"""模块入口点 - 支持 python -m yt_dlp_gui

重要：setup_environment() 必须在任何 Qt/yt_dlp import 之前调用，
因为 PySide6 在 import 时就会读取 PATH 查找平台插件。
"""

import os
import sys


def setup_environment() -> None:
    """为打包后的环境设置必要的 PATH 变量。

    必须在 import PySide6 / yt_dlp_gui 之前调用，
    否则 Qt 插件查找路径已经固定，修改 PATH 无效。
    """
    paths = os.environ.get("PATH", "").split(os.pathsep)

    # 添加常见的 binary 路径 (特别是针对 macOS Homebrew 用户)
    extra_paths = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]

    # 打包后的内部路径（如果将来把 ffmpeg 塞进 app 包）
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        extra_paths.append(bundle_dir)

    for p in extra_paths:
        if p not in paths and os.path.exists(p):
            paths.insert(0, p)

    os.environ["PATH"] = os.pathsep.join(paths)


# ✅ 在 import PySide6 / yt_dlp_gui 之前立即调用，确保 Qt 初始化时 PATH 已正确
setup_environment()

# noqa: E402 — 故意在 setup_environment() 之后 import，顺序依赖是有意为之
from yt_dlp_gui.main import cli  # noqa: E402

if __name__ == "__main__":
    cli()
