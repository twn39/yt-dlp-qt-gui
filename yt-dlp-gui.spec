# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件
用于将 yt-dlp-gui 打包为独立的可执行文件
"""

block_cipher = None

a = Analysis(
    ['src/yt_dlp_gui/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dark_theme.qss', '.'),  # 样式文件
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='yt-dlp-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标路径，例如: 'assets/icon.ico'
)