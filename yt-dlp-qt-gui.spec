# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件 - macOS 优化版
针对 macOS 平台进行优化，生成标准的 .app 文件夹结构，更便于分发和后续代码签名。
"""

import sys
import os

block_cipher = None

# 分析项目依赖
a = Analysis(
    ['src/yt_dlp_gui/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dark_theme.qss', '.'),  # 样式文件
        ('src/yt_dlp_gui/resources/logo.jpg', 'src/yt_dlp_gui/resources'),  # 保持原始路径结构
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'qtawesome',
        'qtawesome.iconic_font',
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.utils',
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 生成可执行文件 (不包含 binaries, datas 等，它们将由 COLLECT 处理)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt-dlp-qt-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico' if sys.platform.startswith('win') else 'logo.icns',
)

# 收集所有输出到目录 (Standard for macOS bundles)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yt-dlp-qt-gui',
)

# 打包为 macOS .app Bundle
app = BUNDLE(
    coll,
    name='yt-dlp-qt-gui.app',
    icon='logo.icns',
    bundle_identifier='com.yt-dlp-gui.app',
    info_plist={
        'CFBundleDisplayName': 'yt-dlp GUI',
        'CFBundleName': 'yt-dlp-qt-gui',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'LSApplicationCategoryType': 'public.app-category.video',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # 允许深色模式
        'LSEnvironment': {
            'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
        },
    },
)