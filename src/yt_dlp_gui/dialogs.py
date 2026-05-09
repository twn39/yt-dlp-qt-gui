import os

import qtawesome as qta
from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .components import Switch
from .config import FORMAT_PRESETS


class LogDialog(QDialog):
    def __init__(self, task_id, title, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setWindowTitle(f"任务日志 - {title}")
        self.resize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Courier New", 10) if os.name == "nt" else QFont("Menlo", 10))
        self.log_output.setStyleSheet("background-color: #0F0F0F; color: #FFFFFF; border: 1px solid #000000; border-radius: 3px;")
        layout.addWidget(self.log_output)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

    def append_log(self, message):
        self.log_output.append(message)
        # 自动滚动到底部
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def set_initial_logs(self, logs):
        self.log_output.setPlainText(logs)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

class AddTaskDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加下载任务")
        self.setMinimumWidth(600)
        self.selected_download_path = self._get_default_download_path()
        self._setup_ui()

    def _get_default_download_path(self) -> str:
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        return path if path and os.path.exists(path) else "."

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # URL Input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴视频链接...")
        layout.addWidget(QLabel("视频链接:"))
        layout.addWidget(self.url_input)

        # Download Options
        options_group = QGroupBox("下载选项")
        options_layout = QGridLayout()

        self.format_combo = QComboBox()
        for format_name in FORMAT_PRESETS.keys():
            self.format_combo.addItem(format_name)

        options_layout.addWidget(QLabel("下载格式:"), 0, 0)
        options_layout.addWidget(self.format_combo, 0, 1)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("例如: http://127.0.0.1:7890")
        options_layout.addWidget(QLabel("HTTP 代理:"), 0, 2)
        options_layout.addWidget(self.proxy_input, 0, 3)

        self.concurrent_input = QLineEdit()
        self.concurrent_input.setPlaceholderText("并发数 (1-16)")
        options_layout.addWidget(QLabel("并发片段数:"), 1, 0)
        options_layout.addWidget(self.concurrent_input, 1, 1)

        self.write_subs_checkbox = Switch("下载字幕")
        options_layout.addWidget(self.write_subs_checkbox, 1, 3)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Playlist Options
        playlist_group = QGroupBox("播放列表设置")
        playlist_layout = QGridLayout()

        self.download_playlist_checkbox = Switch("启用")
        playlist_layout.addWidget(QLabel("下载播放列表:"), 0, 0)
        playlist_layout.addWidget(self.download_playlist_checkbox, 0, 1)

        self.playlist_items_input = QLineEdit()
        playlist_layout.addWidget(QLabel("项目范围:"), 0, 2)
        playlist_layout.addWidget(self.playlist_items_input, 0, 3)

        self.max_downloads_input = QLineEdit()
        self.max_downloads_input.setPlaceholderText("例如: 10")
        playlist_layout.addWidget(QLabel("最大下载数:"), 1, 0)
        playlist_layout.addWidget(self.max_downloads_input, 1, 1)

        playlist_group.setLayout(playlist_layout)
        layout.addWidget(playlist_group)

        # Save Directory
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit(self.selected_download_path)
        self.dir_input.setReadOnly(True)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._select_dir)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(btn_browse)
        layout.addWidget(QLabel("保存目录:"))
        layout.addLayout(dir_layout)

        # Buttons
        btns_layout = QHBoxLayout()
        btn_add = QPushButton("确认添加")
        btn_add.setMinimumHeight(40)
        btn_add.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btns_layout.addWidget(btn_cancel)
        btns_layout.addWidget(btn_add)
        layout.addLayout(btns_layout)

    def _select_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", self.selected_download_path)
        if directory:
            self.selected_download_path = directory
            self.dir_input.setText(directory)

    def get_task_data(self):
        return {
            "url": self.url_input.text().strip(),
            "save_path": self.dir_input.text(),
            "format_preset": FORMAT_PRESETS[self.format_combo.currentText()],
            "proxy": self.proxy_input.text().strip() or None,
            "concurrent_fragments": int(self.concurrent_input.text()) if self.concurrent_input.text().isdigit() else None,
            "write_subs": self.write_subs_checkbox.isChecked(),
            "download_playlist": self.download_playlist_checkbox.isChecked(),
            "playlist_items": self.playlist_items_input.text().strip() or None,
            "max_downloads": int(self.max_downloads_input.text()) if self.max_downloads_input.text().isdigit() else None,
        }


GITHUB_URL = "https://github.com/twn39/yt-dlp-qt-gui"


class AboutDialog(QDialog):
    """现代化「关于」对话框，包含项目信息和 GitHub 链接"""

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于 Yt-dlp GUI")
        self.setFixedWidth(400)
        # 去掉标题栏问号按鈕
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui(version)

    def _setup_ui(self, version: str) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(36, 28, 36, 24)

        # 应用图标
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon("fa5s.cloud-download-alt", color="#4A90E2").pixmap(56, 56))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # 应用名称
        name_label = QLabel("Yt-dlp GUI")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 20pt; font-weight: bold; color: #E0E0E0;")
        layout.addWidget(name_label)

        # 副标题 + 版本
        subtitle_label = QLabel(f"现代化视频下载管理器 · v{version}")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 9pt; color: #888888;")
        layout.addWidget(subtitle_label)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2A2A2A;")
        layout.addWidget(sep)

        # 简介
        desc_label = QLabel(
            "基于 yt-dlp 构建的开源视频下载工具\n"
            "支持 YouTube、Bilibili、Vimeo 等数千个视频平台"
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 9pt; color: #AAAAAA;")
        layout.addWidget(desc_label)

        # GitHub 链接（点击打开浏览器）
        github_btn = QPushButton(
            qta.icon("fa5b.github", color="#BBBBBB"),
            f"  {GITHUB_URL.removeprefix('https://')}",
        )
        github_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #2A2A2A;"
            " border-radius: 6px; padding: 6px 12px; color: #4A90E2; font-size: 9pt; }"
            "QPushButton:hover { border-color: #4A90E2; color: #6AAFE8; background: #1A2A3A; }"
        )
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        layout.addWidget(github_btn)

        # 关闭按鈕
        btn_close = QPushButton("关闭")
        btn_close.setMinimumHeight(36)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
