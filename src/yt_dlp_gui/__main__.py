"""模块入口点 - 支持 python -m yt_dlp_gui

重要：setup_environment() 必须在任何 Qt/yt_dlp import 之前调用，
因为 PySide6 在 import 时就会读取 PATH 查找平台插件。
"""

import os
import sys
import traceback
from datetime import datetime


def _write_startup_log(msg: str) -> None:
    """尽早写一行启动日志到 ~/.yt-dlp-gui/startup.log（或 temp 兜底）。
    这个函数必须不依赖 config.py 里的 import 顺序，否则早期崩也写不进去。
    """
    try:
        # 写日志本身不能崩，所以每一步都 try
        home = os.path.expanduser("~")
        if home:
            log_dir = os.path.join(home, ".yt-dlp-gui")
        else:
            log_dir = os.path.join(os.environ.get("TMPDIR", "/tmp"), ".yt-dlp-gui")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "startup.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        # 真写不了就算了，不能因为日志写不了又引发新崩溃
        sys.stderr.write(f"[startup] {msg}\n")


# ———————————————————————————————————————————————————
# 顶层启动 try/except：任何未捕获异常都必须落盘 traceback
# ———————————————————————————————————————————————————
try:
    _write_startup_log(f"进程启动: frozen={getattr(sys, 'frozen', False)}, python={sys.executable}")

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
    _write_startup_log("setup_environment() 完成")

    # noqa: E402 — 故意在 setup_environment() 之后 import，顺序依赖是有意为之
    from yt_dlp_gui.main import cli  # noqa: E402

    _write_startup_log("import cli 完成")

    if __name__ == "__main__":
        cli()

except SystemExit:
    raise  # 正常退出，不拦
except BaseException:
    # 任何其他异常（包括 KeyboardInterrupt）都写 traceback 落盘
    tb = traceback.format_exc()
    _write_startup_log("FATAL 未捕获异常:\n" + tb)
    # 再打到 stderr 一份，方便 console 模式下直接看到
    sys.stderr.write(tb)
    sys.stderr.flush()
    # 正常退出码 1
    sys.exit(1)
