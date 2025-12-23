#!/usr/bin/env python3
"""
打包脚本 - 使用 PyInstaller 打包 yt-dlp-gui 应用

使用方法:
    python build.py
"""

import os
import sys
import subprocess
import shutil


def clean_build_dirs():
    """清理之前的构建目录"""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"清理目录: {dir_name}")
            shutil.rmtree(dir_name)


def build():
    """执行打包"""
    print("=" * 50)
    print("开始打包 yt-dlp-gui...")
    print("=" * 50)
    
    # 清理之前的构建
    clean_build_dirs()
    
    # 使用 PyInstaller 打包
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "yt-dlp-gui.spec",
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print()
    
    try:
        subprocess.run(cmd, check=True)
        print()
        print("=" * 50)
        print("✓ 打包完成！")
        print("=" * 50)
        print(f"可执行文件位于: dist/yt-dlp-gui")
        print()
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