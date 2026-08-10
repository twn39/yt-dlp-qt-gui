#!/usr/bin/env python3
"""
打包脚本 - 使用 PyInstaller 打包 yt-dlp-qt-gui 应用

使用方法:
    python build.py
"""

import os
import shutil
import subprocess
import sys


def clean_build_dirs():
    """清理之前的构建目录"""
    dirs_to_clean = ["build", "dist"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"清理目录: {dir_name}")
            shutil.rmtree(dir_name)


def build():
    """执行打包"""
    print("=" * 50)
    print("开始打包 yt-dlp-qt-gui...")
    print("=" * 50)

    # 清理之前的构建
    clean_build_dirs()

    # 使用 PyInstaller 打包
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "yt-dlp-qt-gui.spec",
    ]

    print(f"执行命令: {' '.join(cmd)}")
    print()

    try:
        subprocess.run(cmd, check=True)

        # 在 dist 目录放置 .metadata_never_index 防止 macOS Spotlight/Launchpad 检索项目内部构建副本导致重复图标
        if os.path.exists("dist"):
            open(os.path.join("dist", ".metadata_never_index"), "w").close()

        # 支持 --install 自动安装到 /Applications
        if "--install" in sys.argv:
            app_src = os.path.join("dist", "yt-dlp-qt-gui.app")
            if os.path.exists(app_src):
                print("正在安装到 /Applications/yt-dlp-qt-gui.app...")
                dest = "/Applications/yt-dlp-qt-gui.app"
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(app_src, dest)
                clean_build_dirs()
                print("✓ 已成功安装到 /Applications/yt-dlp-qt-gui.app！")

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
        sys.exit(1)


if __name__ == "__main__":
    build()
