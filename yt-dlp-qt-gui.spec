# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件
用于将 yt-dlp-qt-gui 打包为独立的可执行文件
"""

block_cipher = None

a = Analysis(
    ['src/yt_dlp_gui/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dark_theme.qss', '.'),  # 样式文件
        ('src/yt_dlp_gui/resources/logo.jpg', '.'),  # 应用图标
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
    icon='logo.icns',
)

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

app = BUNDLE(
    coll,
    name='yt-dlp-qt-gui.app',
    icon='logo.icns',
    bundle_identifier='com.yt-dlp-gui.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSBackgroundOnly': 'False',
    },
)