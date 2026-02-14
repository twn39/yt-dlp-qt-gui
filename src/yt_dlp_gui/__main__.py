"""模块入口点 - 支持 python -m yt_dlp_gui"""

import os
import sys

def setup_environment():
    """为打包后的环境设置必要的 PATH 变量"""
    # 获取当前 PATH
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
    
    # 也可以添加打包后的内部路径 (如果将来决定把 ffmpeg 塞进 app 包)
    if getattr(sys, 'frozen', False):
        bundle_dir = sys._MEIPASS
        extra_paths.append(bundle_dir)

    for p in extra_paths:
        if p not in paths and os.path.exists(p):
            paths.insert(0, p)
            
    os.environ["PATH"] = os.pathsep.join(paths)

from yt_dlp_gui.main import cli

if __name__ == "__main__":
    setup_environment()
    cli()
