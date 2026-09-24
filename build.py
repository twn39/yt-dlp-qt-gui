#!/usr/bin/env python3
"""
打包脚本 - 使用 PyInstaller 打包 yt-dlp-qt-gui 应用（带体积优化）

一条命令即可完成编译，无需手动设置任何环境变量：

    python build.py              # 打包
    python build.py --install    # 打包并安装到 /Applications

脚本会自动：
    1. 检查 / 安装构建依赖（优先使用 uv，其次 pip）
    2. 设置 PyInstaller 缓存目录（避免 ~/Library 权限问题）
    3. 调用 PyInstaller 编译
    4. 自动精简无用的 Qt 框架 / 插件 / 图标字体（600MB → ~80MB）
"""

import importlib.util
import os
import shutil
import subprocess
import sys

# ============================================================
# 路径与环境变量（必须在导入任何 PyInstaller 相关模块前设置）
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# PyInstaller 默认把缓存写到 ~/Library/Application Support/pyinstaller，
# 在部分机器（企业管控 / 沙箱）上会因权限不足报
# PermissionError: [Errno 1] Operation not permitted。
# 统一改到项目本地的缓存目录，任何机器都能写。
LOCAL_CACHE_DIR = os.path.join(PROJECT_ROOT, ".pyinstaller-cache")
os.environ.setdefault("PYINSTALLER_CONFIG_DIR", LOCAL_CACHE_DIR)
os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)


# ============================================================
# 虚拟环境自动切换
# ============================================================


def _is_in_venv() -> bool:
    """判断当前解释器是否运行在某个虚拟环境中（venv / .venv）"""
    return sys.base_prefix != sys.prefix or hasattr(sys, "real_prefix")


def _try_use_project_venv() -> None:
    """
    若当前不在虚拟环境中，且项目根目录下存在 .venv，
    则用 .venv/bin/python 重新执行本脚本，避免 Homebrew 等系统 Python
    因 PEP 668 (externally-managed-environment) 阻断 pip install。
    此函数成功 execv 后不会返回；找不到 .venv 时静默返回。
    """
    if _is_in_venv():
        return

    # 跨平台：macOS/Linux 用 bin/python，Windows 用 Scripts/python.exe
    candidates = [
        os.path.join(PROJECT_ROOT, ".venv", "bin", "python"),
        os.path.join(PROJECT_ROOT, ".venv", "bin", "python3"),
        os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),
    ]
    for venv_python in candidates:
        if os.path.isfile(venv_python):
            print(f"检测到项目虚拟环境，自动切换: {venv_python}")
            os.execv(venv_python, [venv_python, os.path.abspath(__file__), *sys.argv[1:]])
            # os.execv 不返回；若返回说明执行失败，继续走后面的 ensure_dependencies
            break


# ============================================================
# 依赖检查
# ============================================================

BUILD_REQUIREMENTS = ["PyInstaller", "PySide6", "yt_dlp", "qtawesome", "click", "curl_cffi"]


def _module_available(module_name: str) -> bool:
    """检查某个模块是否已安装（不真正导入，避免拉起重依赖）"""
    return importlib.util.find_spec(module_name) is not None


def ensure_dependencies() -> None:
    """
    确保构建依赖已安装。
    优先走 uv（项目自带 uv.lock），否则回退到 pip。
    缺依赖时自动安装，安装后用正确的解释器重新执行本脚本。
    """
    missing = [name for name in BUILD_REQUIREMENTS if not _module_available(name)]
    if not missing:
        return

    print("=" * 50)
    print(f"检测到缺少构建依赖: {', '.join(missing)}")
    print("=" * 50)

    uv_exe = shutil.which("uv")

    if uv_exe:
        # 项目使用 uv 管理依赖（pyproject.toml + uv.lock）
        # dev 依赖组里包含 pyinstaller / pillow
        print("使用 uv 同步依赖（uv sync）...")
        subprocess.run([uv_exe, "sync"], cwd=PROJECT_ROOT, check=True)
        # 用 uv 管理的虚拟环境重新执行本脚本
        print("使用 uv run 重新启动构建...")
        os.execv(uv_exe, [uv_exe, "run", "python", os.path.abspath(__file__), *sys.argv[1:]])
    else:
        # 回退方案：用 pip 直接安装运行时依赖 + 构建工具
        # 注意：本项目的 pyinstaller 放在 [dependency-groups].dev，
        # 不是 extras，不能用 pip install -e '.[dev]'
        print("未找到 uv，使用 pip 安装构建依赖...")
        print("（推荐安装 uv: https://docs.astral.sh/uv/ ，依赖解析更快）")
        pip_packages = [
            "-e",
            ".",
            "pyinstaller>=6.19.0",
            "pillow>=12.1.1",
        ]
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *pip_packages],
            cwd=PROJECT_ROOT,
            check=True,
        )
        print("依赖安装完成，重新启动构建...")
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), *sys.argv[1:]])


# ============================================================
# 构建辅助
# ============================================================


def clean_build_dirs():
    """清理之前的构建目录"""
    for dir_name in ["build", "dist"]:
        if os.path.exists(dir_name):
            print(f"清理目录: {dir_name}")
            shutil.rmtree(dir_name)


def optimize_app_size(app_path: str) -> None:
    """
    构建后体积优化：移除未使用的 Qt 框架、插件和图标字体。
    本项目仅使用 QtWidgets（QtCore/QtGui/QtWidgets/QtDBus）和 Font Awesome 5 图标。
    """
    print()
    print("=" * 50)
    print("执行体积优化...")
    print("=" * 50)

    frameworks_dir = os.path.join(app_path, "Contents", "Frameworks")
    qt_lib_dir = os.path.join(frameworks_dir, "PySide6", "Qt", "lib")
    qt_plugins_dir = os.path.join(frameworks_dir, "PySide6", "Qt", "plugins")
    resources_dir = os.path.join(app_path, "Contents", "Resources")

    removed_bytes = 0

    def get_size(path: str) -> int:
        """获取文件或目录的总大小（字节），不统计符号链接"""
        if os.path.islink(path):
            return 0
        if os.path.isfile(path):
            try:
                return os.path.getsize(path)
            except OSError:
                return 0
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
        return total

    def remove_path(path: str, desc: str = "") -> None:
        """删除路径并记录节省的空间"""
        nonlocal removed_bytes
        if os.path.exists(path) or os.path.islink(path):
            size = get_size(path)
            removed_bytes += size
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            if desc:
                print(f"  - {desc} ({size / 1024 / 1024:.1f} MB)")

    # 1. 移除未使用的 Qt 框架
    print("\n[1/3] 移除未使用的 Qt 框架...")
    # 保留的核心框架（依赖链：QtWidgets → QtGui → QtCore + QtDBus）
    keep_frameworks = {"QtCore", "QtGui", "QtWidgets", "QtDBus"}
    if os.path.isdir(qt_lib_dir):
        for fw_name in os.listdir(qt_lib_dir):
            if fw_name.endswith(".framework"):
                base_name = fw_name[: -len(".framework")]
                if base_name not in keep_frameworks:
                    remove_path(os.path.join(qt_lib_dir, fw_name), f"Qt 框架: {base_name}")
                    # 同时删除 Frameworks 根目录下的符号链接
                    symlink = os.path.join(frameworks_dir, base_name)
                    if os.path.islink(symlink):
                        os.remove(symlink)

    # 2. 精简 Qt 插件
    print("\n[2/3] 精简 Qt 插件...")

    # imageformats: 只保留 jpg/gif/ico
    img_dir = os.path.join(qt_plugins_dir, "imageformats")
    if os.path.isdir(img_dir):
        keep_img = {"libqjpeg.dylib", "libqgif.dylib", "libqico.dylib"}
        for f in os.listdir(img_dir):
            if f.endswith(".dylib") and f not in keep_img:
                remove_path(os.path.join(img_dir, f), f"图片插件: {f}")

    # platforms: 删除 offscreen（仅调试用）
    remove_path(
        os.path.join(qt_plugins_dir, "platforms", "libqoffscreen.dylib"),
        "平台插件: offscreen",
    )
    # platforminputcontexts: 删除虚拟键盘插件
    remove_path(
        os.path.join(qt_plugins_dir, "platforminputcontexts", "libqtvirtualkeyboardplugin.dylib"),
        "输入插件: virtualkeyboard",
    )
    # generic: 删除触控插件
    remove_path(
        os.path.join(qt_plugins_dir, "generic", "libqtuiotouchplugin.dylib"),
        "通用插件: tuiotouch",
    )
    # iconengines: 删除 svg 图标引擎（QtSvg 已移除）
    remove_path(
        os.path.join(qt_plugins_dir, "iconengines", "libqsvgicon.dylib"),
        "图标引擎: svgicon",
    )

    # 3. qtawesome 字体不做精简
    # qtawesome/__init__.py 硬编码注册所有 family 的全部变体（FA5+FA6 各 solid/regular/brands），
    # 初始化时一次性加载，删任何一个都会 FileNotFoundError。字体总量很小（~700 KB），不值得精简。

    # 4. 清理死符号链接
    print("\n[3/3] 清理死符号链接...")
    dead_links = 0
    for search_dir in [resources_dir, frameworks_dir]:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, files in os.walk(search_dir):
            for name in files + dirs:
                path = os.path.join(root, name)
                if os.path.islink(path) and not os.path.exists(path):
                    os.remove(path)
                    dead_links += 1
    if dead_links:
        print(f"  - 清理了 {dead_links} 个死符号链接")

    saved_mb = removed_bytes / 1024 / 1024
    print()
    print(f"✓ 体积优化完成，共节省 {saved_mb:.1f} MB")

    # 修改了 bundle 内容后需要重新做一次 ad-hoc 签名，否则 macOS 可能拒绝启动
    print()
    print("重新签名 App Bundle...")
    try:
        subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", app_path],
            check=True,
            capture_output=True,
        )
        print("✓ 重新签名完成")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"⚠ 签名跳过: {e}")


def get_dir_size_mb(path: str) -> float:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total / 1024 / 1024


# ============================================================
# 主流程
# ============================================================


def build():
    # 自动切换到项目 .venv（若系统 Python 直接调用且 .venv 存在）
    _try_use_project_venv()

    # 先确保依赖就绪（可能会重启进程，所以要放在最前面）
    ensure_dependencies()

    os.chdir(PROJECT_ROOT)

    print("=" * 50)
    print("开始打包 yt-dlp-qt-gui...")
    print("=" * 50)
    print(f"Python:      {sys.executable}")
    print(f"项目目录:    {PROJECT_ROOT}")
    print(f"PyInstaller 缓存: {LOCAL_CACHE_DIR}")

    clean_build_dirs()

    # --clean: 构建前清缓存；-y/--noconfirm: dist 已存在时直接覆盖，不弹确认
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "yt-dlp-qt-gui.spec",
    ]

    print(f"\n执行命令: {' '.join(cmd)}\n")

    try:
        # env 继承当前进程（包含上面设置好的 PYINSTALLER_CONFIG_DIR）
        subprocess.run(cmd, check=True, env=os.environ.copy())

        app_path = os.path.join("dist", "yt-dlp-qt-gui.app")
        if os.path.exists(app_path):
            optimize_app_size(app_path)

        # 防止 macOS Spotlight/Launchpad 检索构建副本导致重复图标
        if os.path.exists("dist"):
            open(os.path.join("dist", ".metadata_never_index"), "w").close()

        # 支持 --install 自动安装到 /Applications
        if "--install" in sys.argv:
            app_src = os.path.join("dist", "yt-dlp-qt-gui.app")
            if os.path.exists(app_src):
                print("\n正在安装到 /Applications/yt-dlp-qt-gui.app...")
                dest = "/Applications/yt-dlp-qt-gui.app"
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(app_src, dest)
                clean_build_dirs()
                print("✓ 已成功安装到 /Applications/yt-dlp-qt-gui.app！")

        if os.path.exists(app_path):
            print(f"\n最终 App 大小: {get_dir_size_mb(app_path):.1f} MB")
            print(f"产物位置: {os.path.abspath(app_path)}")

        print()
        print("=" * 50)
        print("✓ 打包完成！")
        print("=" * 50)
        print("注意事项:")
        print("- 打包后的应用仍需要系统安装 FFmpeg")
        print("- 首次运行可能需要防火墙权限")
        print("- macOS 用户可能需要在系统设置中允许运行未签名的应用")
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 50)
        print("✗ 打包失败！")
        print("=" * 50)
        print(f"错误: {e}")
        print()
        print("排查建议:")
        print("  1. 删除 .pyinstaller-cache、build、dist 后重试")
        print("  2. 确认依赖完整: uv sync --dev  (或 pip install -e '.[dev]')")
        print("  3. 直接运行 PyInstaller 查看完整报错:")
        print("     uv run pyinstaller --clean -y yt-dlp-qt-gui.spec")
        sys.exit(1)


if __name__ == "__main__":
    build()
