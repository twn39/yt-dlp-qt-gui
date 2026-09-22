# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件 - macOS 极致精简版
通过排除大量未使用的 Qt 模块和 Python 依赖，显著减小打包体积。
"""

import importlib.metadata
import sys
import os

# 从已安装的包元数据读取版本（与 pyproject.toml 保持同步）
try:
    _app_version = importlib.metadata.version("yt-dlp-qt-gui")
except importlib.metadata.PackageNotFoundError:
    _app_version = "0.0.0-dev"

block_cipher = None

# ============================================================
# 排除列表 - 大幅减小体积的关键
# ============================================================

# 未使用的 PySide6 / Qt 模块（本项目只用 QtCore/QtGui/QtWidgets）
excluded_qt_modules = [
    # Qml / Quick 相关（非常大，通常 100MB+）
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickTemplates2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQmlWorkerScript",
    "PySide6.QtQmlMetaObject",
    "PySide6.QtQmlModels",
    # WebEngine 相关（最大的模块，单个模块就 100MB+）
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngine",
    "PySide6.QtWebChannel",
    "PySide6.QtWebView",
    # 多媒体相关
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio",
    # 3D 相关
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    # 网络 / 位置（yt-dlp 自己处理网络）
    "PySide6.QtNetwork",
    "PySide6.QtNetworkAuth",
    "PySide6.QtLocation",
    "PySide6.QtPositioning",
    # 数据库（本项目用 SQLite 内置模块）
    "PySide6.QtSql",
    # OpenGL / 图形
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    # 打印
    "PySide6.QtPrintSupport",
    # SVG（qtawesome 用字体图标，不需要 Qt SVG）
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    # 传感器 / 蓝牙 / NFC / 串口
    "PySide6.QtSensors",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtCanBus",
    # 图表 / 数据可视化
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    # 虚拟键盘 / 文本转语音
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtTextToSpeech",
    # 测试 / 调试
    "PySide6.QtTest",
    # UI 工具
    "PySide6.QtUiTools",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    # State Machine
    "PySide6.QtStateMachine",
    "PySide6.QtStateMachineQmlPlugin",
    # Scxml
    "PySide6.QtScxml",
    # Remote Objects
    "PySide6.QtRemoteObjects",
    # 其它
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtLabs",
]

# 不需要的 Python 模块（只排除明确的开发/测试依赖，不排除标准库以免破坏功能）
excluded_python_modules = [
    # 测试框架（开发依赖，运行时不需要）
    "pytest",
    "_pytest",
    # Tkinter（GUI 用 Qt，不需要 Tk）
    "tkinter",
    "Tkinter",
    # IPython / Jupyter（如果被依赖带进来）
    "IPython",
    "jupyter",
    "notebook",
    # 文档工具
    "sphinx",
    "docutils",
    # 代码检查
    "ruff",
    "pyflakes",
    "pycodestyle",
    # 构建工具
    "setuptools",
    "distutils",
    "wheel",
    "pip",
    # dev 依赖
    "ty",
    "pytest_cov",
    "coverage",
]

# 合并所有排除项
excludes = excluded_qt_modules + excluded_python_modules

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
        'curl_cffi',
        # yt-dlp 可能动态加载的模块
        'yt_dlp.networking',
        'yt_dlp.networking.common',
        'yt_dlp.networking.exceptions',
        'yt_dlp.networking.impersonate',
        'yt_dlp.extractor.common',
        'yt_dlp.postprocessor',
        'yt_dlp.postprocessor.common',
        'mutagen',
        'brotli',
        'brotlicffi',
        'certifi',
        'websockets',
        'urllib3',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ============================================================
# 进一步过滤：移除不需要的 Qt 翻译、示例、插件等
# ============================================================

# 过滤掉不需要的 Qt 插件
qt_plugins_to_keep = {
    'platforms',      # 平台插件（必须）
    'styles',         # 样式插件
    'iconengines',    # 图标引擎（qtawesome 可能需要）
    'imageformats',   # 图片格式（logo.jpg 需要）
    'tls',            # TLS 后端（虽然不用 QtNetwork，但某些系统可能需要）
}

# 手动从 datas 和 binaries 中过滤掉不需要的 Qt 插件和翻译
def _is_unwanted_qt_asset(tup):
    """判断是否为不需要的 Qt 资源"""
    path = tup[0] if isinstance(tup, (list, tuple)) else str(tup)
    
    # 排除 Qt 翻译文件（几十MB）
    if 'translations' in path and ('qt_' in path or 'qtbase_' in path or 'qtmultimedia' in path):
        # 保留中文翻译（如果需要的话），否则全排除
        # 本项目界面是中文的，但 Qt 自带的翻译主要是标准对话框
        return True
    
    # 排除 Qt 插件目录中不需要的类型
    for plugin_dir in ['qml', 'quick3d', 'webview', 'webengine', 'multimedia', 
                        'geoservices', 'position', 'sensors', 'gamepads',
                        'renderers', 'scenegraph']:
        if f'/{plugin_dir}/' in path or f'\\{plugin_dir}\\' in path:
            return True
    
    return False

# 过滤 datas
a.datas = [d for d in a.datas if not _is_unwanted_qt_asset(d)]

# 过滤 binaries
a.binaries = [b for b in a.binaries if not _is_unwanted_qt_asset(b)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 生成可执行文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt-dlp-qt-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,              # 启用 strip，移除符号表（macOS/Linux 有效）
    upx=True,                # 启用 UPX 压缩（如果系统安装了 UPX）
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.icns',
)

# 收集所有输出到目录
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,              # 启用 strip
    upx=True,                # 启用 UPX
    upx_exclude=[],          # UPX 排除列表
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
        'CFBundleShortVersionString': _app_version,
        'CFBundleVersion': _app_version,
        'LSApplicationCategoryType': 'public.app-category.video',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # 允许深色模式
        'LSEnvironment': {
            'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
        },
    },
)
