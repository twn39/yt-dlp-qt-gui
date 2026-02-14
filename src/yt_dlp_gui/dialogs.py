import os
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, 
    QPushButton, QFileDialog, QComboBox, QGroupBox, QGridLayout, QLabel
)
from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtGui import QFont
from .config import FORMAT_PRESETS, ICON_COLOR, DEFAULT_DOWNLOAD_PLAYLIST, DEFAULT_PLAYLIST_ITEMS, DEFAULT_PLAYLIST_RANDOM, DEFAULT_MAX_DOWNLOADS
from .components import Switch

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
