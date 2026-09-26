import os
from typing import Any, Callable, Optional

import qtawesome as qta
from PySide6.QtCore import QObject, QStandardPaths, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .components import Switch
from .config import FORMAT_PRESETS, get_last_save_path, save_ui_state
from .models import DownloadTask


class LogDialog(QDialog):
    def __init__(self, task_id, title, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setWindowTitle(f"任务日志 - {title}")
        self.resize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(2000)
        self.log_output.setFont(QFont("Courier New", 10) if os.name == "nt" else QFont("Menlo", 10))
        self.log_output.setStyleSheet(
            "background-color: #0F0F0F; color: #FFFFFF; border: 1px solid #000000; border-radius: 3px;"
        )
        layout.addWidget(self.log_output)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

    def append_log(self, message):
        self.log_output.appendPlainText(message)
        # 自动滚动到底部
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def set_initial_logs(self, logs):
        self.log_output.setPlainText(logs)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())


class FormatPreviewWorker(QObject):
    """后台线程：调用 yt-dlp extract_info 解析可用格式"""

    finished = Signal(dict)  # info_dict 或 None（成功）
    error = Signal(str)  # 失败原因

    def __init__(
        self, url: str, proxy: str | None, impersonate: str | None, cookie_browser: str | None
    ) -> None:
        super().__init__()
        self.url = url
        self.proxy = proxy
        self.impersonate = impersonate
        self.cookie_browser = cookie_browser

    @Slot()
    def run(self) -> None:
        try:
            import yt_dlp
            from yt_dlp.networking.impersonate import ImpersonateTarget

            opts: dict[str, Any] = {
                "quiet": True,
                "skip_download": True,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "merge_output_format": None,
                "socket_timeout": 30,
                "retries": 3,
                "nocheckcertificate": True,
            }
            if self.proxy:
                opts["proxy"] = self.proxy
            if self.cookie_browser:
                opts["cookiesfrombrowser"] = (self.cookie_browser,)
            if self.impersonate:
                try:
                    opts["impersonate"] = ImpersonateTarget.from_str(self.impersonate)
                except Exception:
                    opts["impersonate"] = self.impersonate

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


def _format_filesize(n: int | float | None) -> str:
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class FormatPreviewDialog(QDialog):
    """格式预览对话框：列出所有可用视频+音频轨道，让用户挑"""

    def __init__(self, info: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择下载格式")
        self.resize(920, 560)
        self.video_format_id: Optional[str] = None
        self.audio_format_id: Optional[str] = None
        self._formats: list[dict[str, Any]] = info.get("formats", [])

        title = info.get("title", "") or info.get("id", "")
        self._build_ui(title, info)
        self._populate_tables(self._formats)

    # ---------- UI ----------
    def _build_ui(self, title: str, info: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)

        meta = QLabel(
            f"<b>{title}</b>  ·  <span style='color:#888'>{info.get('webpage_url', '')}</span>"
        )
        meta.setWordWrap(True)
        layout.addWidget(meta)

        grid = QGridLayout()
        grid.addWidget(QLabel("视频轨道"), 0, 0)
        grid.addWidget(QLabel("音频轨道"), 0, 1)
        self.video_table = self._make_table()
        self.audio_table = self._make_table()
        grid.addWidget(self.video_table, 1, 0)
        grid.addWidget(self.audio_table, 1, 1)
        layout.addLayout(grid, 1)

        tip = QLabel(
            "提示：<b>杜比视界 (DoVi) / HDR / AV1 (av01)</b> 在 Mac 上需要 macOS 13+ 和 Apple Silicon 硬解，"
            "Intel Mac 会黑屏。视频和音频可以自由组合。"
        )
        tip.setStyleSheet("color: #AAA; font-size: 11px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("确认下载")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._btns = btns
        self._update_ok_enabled()

    def _make_table(self) -> QTableWidget:
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels(["格式 ID", "分辨率", "帧率", "编码", "大小"])
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(
            "QTableWidget { background:#1E1E1E; alternate-background-color:#252525; color:#E0E0E0; }"
            "QHeaderView::section { background:#2D2D2D; color:#CCC; padding:4px; border:0; }"
            "QTableWidget::item:selected { background:#004C8C; }"
        )
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        return t

    # ---------- 填数据 ----------
    def _populate_tables(self, formats: list[dict[str, Any]]) -> None:
        videos = [f for f in formats if (f.get("vcodec") or "") != "none"]
        audios = [
            f
            for f in formats
            if (f.get("acodec") or "") != "none" and (f.get("vcodec") or "") == "none"
        ]

        # 视频表：按 height 降序 + is_dovi 标记
        videos.sort(key=lambda f: int(str(f.get("height") or 0)), reverse=True)
        # 音频表：按 abr 降序
        audios.sort(key=lambda f: float(str(f.get("abr") or 0)), reverse=True)

        def _row(table: QTableWidget, f: dict[str, Any]) -> None:
            row = table.rowCount()
            table.insertRow(row)
            # 杜比视界：优先读 dynamic_range，fallback 到 format_note
            dyn = f.get("dynamic_range") or ""
            note = f.get("format_note") or ""
            dovi = dyn == "dv" or "dovi" in note.lower()
            hdr = dyn and dyn != "dv" and dyn != "sdr"
            res = f.get("resolution") or f"{f.get('width', '')}x{f.get('height', '')}"
            fps = f.get("fps")
            codec = f.get("vcodec") if table is self.video_table else f.get("acodec")
            if dovi:
                codec = (codec or "") + " (DoVi)"
            elif hdr:
                codec = (codec or "") + f" (HDR {dyn.upper()})"
            size = f.get("filesize") or f.get("filesize_approx")
            table.setItem(
                row, 0, QTableWidgetItem(str(f.get("format_id", "")) + ("  ★杜比" if dovi else ""))
            )
            table.setItem(row, 1, QTableWidgetItem(str(res)))
            table.setItem(row, 2, QTableWidgetItem(f"{fps:g}fps" if fps else "—"))
            table.setItem(row, 3, QTableWidgetItem(str(codec or "")))
            table.setItem(row, 4, QTableWidgetItem(_format_filesize(size)))

        for f in videos:
            _row(self.video_table, f)
        for f in audios:
            _row(self.audio_table, f)

        self.video_table.itemSelectionChanged.connect(self._update_ok_enabled)
        self.audio_table.itemSelectionChanged.connect(self._update_ok_enabled)

    # ---------- 选行 ----------
    def _selected_format_id(self, table: QTableWidget) -> Optional[str]:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if not item:
            return None
        return item.text().split()[0]  # 去掉 " ★杜比"

    def _update_ok_enabled(self) -> None:
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            self.video_table.currentRow() >= 0 and self.audio_table.currentRow() >= 0
        )

    def _on_ok(self) -> None:
        self.video_format_id = self._selected_format_id(self.video_table)
        self.audio_format_id = self._selected_format_id(self.audio_table)
        if self.video_format_id and self.audio_format_id:
            self.accept()

    def get_format_spec(self) -> str:
        """给 yt-dlp format 参数用的字符串，例如 '30080+30280'"""
        if self.video_format_id and self.audio_format_id:
            return f"{self.video_format_id}+{self.audio_format_id}"
        return ""

    def get_human_label(self) -> str:
        """给用户看的人类可读标签，例如 'DoVi 3840x2160 HEVC / AAC 192kbps'"""

        def _find(fid: Optional[str]) -> Optional[dict]:
            if not fid:
                return None
            for f in self._formats:
                if str(f.get("format_id")) == fid:
                    return f
            return None

        vid = _find(self.video_format_id)
        aid = _find(self.audio_format_id)
        if not vid or not aid:
            return self.get_format_spec()
        res = vid.get("resolution") or f"{vid.get('width', '')}x{vid.get('height', '')}"
        vcodec = (vid.get("vcodec") or "").split(".")[0].upper()
        acodec = (aid.get("acodec") or "").split(".")[0].upper()
        abr = aid.get("abr") or 0
        dyn = vid.get("dynamic_range") or ""
        dovi = dyn == "dv" or "dovi" in (vid.get("format_note") or "").lower()
        prefix = "DoVi " if dovi else ("HDR " if dyn and dyn != "dv" and dyn != "sdr" else "")
        return f"{prefix}{res} {vcodec} / {acodec} {int(abr) if abr else '?'}kbps"


class AddTaskDialog(QDialog):
    def __init__(self, parent=None, initial_url: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("添加下载任务")
        self.setMinimumWidth(600)
        # 用上次保存目录，没有则回退到系统下载目录
        self.selected_download_path = get_last_save_path()
        self._format_spec: str = ""  # 用户手动选的 format_id+format_id
        self._format_human_label: str = ""  # 显示给用户看的格式描述
        self._parse_thread: Optional[QThread] = None
        self._parse_worker: Optional[FormatPreviewWorker] = None
        self._setup_ui()
        self._try_autofill_clipboard(initial_url)

    def _get_default_download_path(self) -> str:
        path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        return path if path and os.path.exists(path) else "."

    def _try_autofill_clipboard(self, initial_url: str | None = None) -> None:
        """如果传入了初始 URL 则使用它，否则尝试从系统剪贴板自动填入有效 URL"""
        if initial_url and initial_url.strip():
            self.url_input.setText(initial_url.strip())
            self.url_input.selectAll()
            return

        clipboard = QApplication.clipboard()
        text = clipboard.text().strip() if clipboard else ""
        if text.startswith(("http://", "https://", "www.")):
            self.url_input.setText(text)
            self.url_input.selectAll()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # URL Input + 解析按钮
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴视频链接...")
        self.url_input.returnPressed.connect(self._on_parse_clicked)
        url_row.addWidget(self.url_input, 1)
        self.parse_btn = QPushButton(qta.icon("fa5s.list-alt", color="#FFFFFF"), "  解析格式")
        self.parse_btn.setMinimumWidth(120)
        self.parse_btn.clicked.connect(self._on_parse_clicked)
        url_row.addWidget(self.parse_btn)
        layout.addWidget(QLabel("视频链接:"))
        layout.addLayout(url_row)

        self.parse_progress = QProgressBar()
        self.parse_progress.setRange(0, 0)
        self.parse_progress.setVisible(False)
        self.parse_progress.setFixedHeight(4)
        self.parse_progress.setTextVisible(False)
        layout.addWidget(self.parse_progress)

        # Download Options
        options_group = QGroupBox("下载选项")
        options_layout = QGridLayout()

        self.format_combo = QComboBox()
        self.format_combo.setView(QListView())
        # 初始只放 preset 选项，解析后如果用户选了具体 format_id 会在头部插入"已选具体格式"项
        self._format_preset_items = list(FORMAT_PRESETS.keys())
        self.format_combo.addItems(self._format_preset_items)

        options_layout.addWidget(QLabel("下载格式:"), 0, 0)
        options_layout.addWidget(self.format_combo, 0, 1)

        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("例如: http://127.0.0.1:7890")
        options_layout.addWidget(QLabel("HTTP 代理:"), 0, 2)
        options_layout.addWidget(self.proxy_input, 0, 3)

        self.concurrent_input = QLineEdit()
        self.concurrent_input.setPlaceholderText("并发数 (1-16)，默认5")
        options_layout.addWidget(QLabel("并发片段数:"), 1, 0)
        options_layout.addWidget(self.concurrent_input, 1, 1)

        self.impersonate_combo = QComboBox()
        self.impersonate_combo.setView(QListView())
        self.impersonate_combo.addItems(["无", "chrome", "firefox", "edge", "safari"])
        options_layout.addWidget(QLabel("浏览器伪装:"), 1, 2)
        options_layout.addWidget(self.impersonate_combo, 1, 3)

        self.ratelimit_input = QLineEdit()
        self.ratelimit_input.setPlaceholderText("例如: 2M, 500K")
        options_layout.addWidget(QLabel("下载限速:"), 2, 0)
        options_layout.addWidget(self.ratelimit_input, 2, 1)

        # 浏览器 Cookies：从本机 Chrome / Edge 导入（Safari 暂不支持）
        self.cookie_browser_combo = QComboBox()
        self.cookie_browser_combo.setView(QListView())
        self.cookie_browser_combo.addItems(["不导入", "Chrome", "Edge"])
        options_layout.addWidget(QLabel("导入 Cookies:"), 2, 2)
        options_layout.addWidget(self.cookie_browser_combo, 2, 3)

        self.write_subs_checkbox = Switch("下载字幕")
        options_layout.addWidget(self.write_subs_checkbox, 3, 0, 1, 2)

        # 提示：选了浏览器时显示简要说明
        tip_label = QLabel("选浏览器 → 自动从本机 cookies 库读登录态；不导入 → 匿名抓取")
        tip_label.setStyleSheet("color: #AAA; font-size: 11px;")
        options_layout.addWidget(tip_label, 4, 0, 1, 4)
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
        btn_add.clicked.connect(self._on_confirm_clicked)
        btn_cancel = QPushButton("取消")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btns_layout.addWidget(btn_cancel)
        btns_layout.addWidget(btn_add)
        layout.addLayout(btns_layout)

    def _on_confirm_clicked(self) -> None:
        """确认添加：先持久化当前目录再 accept"""
        save_ui_state({"last_save_path": self.selected_download_path})
        self.accept()

    def _select_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择保存目录", self.selected_download_path
        )
        if directory:
            self.selected_download_path = directory
            self.dir_input.setText(directory)
            save_ui_state({"last_save_path": directory})

    # ---------- 格式预览 ----------
    def _collect_parse_opts(self) -> dict[str, Any]:
        impersonate_val = self.impersonate_combo.currentText()
        cookie_browser_val = self.cookie_browser_combo.currentText().lower()
        return {
            "proxy": self.proxy_input.text().strip() or None,
            "impersonate": impersonate_val if impersonate_val != "无" else None,
            "cookie_browser": cookie_browser_val if cookie_browser_val != "不导入" else None,
        }

    def _on_parse_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "提示", "请输入有效的视频链接")
            return
        if self._parse_thread:  # 正在解析
            return

        opts = self._collect_parse_opts()
        self.parse_btn.setEnabled(False)
        self.parse_btn.setText("解析中...")
        self.parse_progress.setVisible(True)

        self._parse_thread = QThread(self)
        self._parse_worker = FormatPreviewWorker(
            url=url,
            proxy=opts["proxy"],
            impersonate=opts["impersonate"],
            cookie_browser=opts["cookie_browser"],
        )
        self._parse_worker.moveToThread(self._parse_thread)
        self._parse_thread.started.connect(self._parse_worker.run)
        self._parse_worker.finished.connect(self._on_parse_success)
        self._parse_worker.error.connect(self._on_parse_error)
        self._parse_worker.finished.connect(self._parse_thread.quit)
        self._parse_worker.error.connect(self._parse_thread.quit)
        self._parse_thread.finished.connect(self._cleanup_parse_thread)
        self._parse_thread.start()

    @Slot(dict)
    def _on_parse_success(self, info: dict[str, Any]) -> None:
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("  解析格式")
        self.parse_btn.setIcon(qta.icon("fa5s.list-alt", color="#FFFFFF"))
        self.parse_progress.setVisible(False)

        if not info.get("formats"):
            QMessageBox.warning(self, "提示", "该视频没有可用的格式")
            return
        if info.get("is_live"):
            QMessageBox.information(self, "直播视频", "这是一个直播视频，不支持格式预览")
            return

        dlg = FormatPreviewDialog(info, parent=self)
        if dlg.exec():
            self._format_spec = dlg.get_format_spec()
            self._format_human_label = dlg.get_human_label()
            self._last_url_for_parse = info.get("webpage_url") or self.url_input.text()
            # 动态刷新 format_combo：头部插入"已选具体格式"项并自动选中
            self._refresh_format_combo_for_selection()

    def _refresh_format_combo_for_selection(self) -> None:
        """把用户刚从预览框里选的 format 插到下拉框顶部并自动选中"""
        # 先清空再重建（去掉之前插入的"已选具体格式"项，保留 preset）
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        if self._format_spec:
            label = self._format_human_label or self._format_spec
            display = f"已选：{label}"
            self.format_combo.addItem(display, userData=self._format_spec)
        self.format_combo.addItems(self._format_preset_items)
        self.format_combo.setCurrentIndex(0 if self._format_spec else 1)
        self.format_combo.blockSignals(False)

    @Slot(str)
    def _on_parse_error(self, err: str) -> None:
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("  解析格式")
        self.parse_btn.setIcon(qta.icon("fa5s.list-alt", color="#FFFFFF"))
        self.parse_progress.setVisible(False)
        QMessageBox.critical(self, "解析失败", f"无法获取视频信息：\n\n{err}")

    @Slot()
    def _cleanup_parse_thread(self) -> None:
        if self._parse_worker:
            self._parse_worker.deleteLater()
        self._parse_worker = None
        if self._parse_thread:
            self._parse_thread.deleteLater()
        self._parse_thread = None

    def _close_event(self, event) -> None:
        """关窗口时清理后台线程"""
        if self._parse_thread:
            self._parse_thread.quit()
            self._parse_thread.wait(1000)
        super().closeEvent(event)

    def get_task_data(self) -> DownloadTask:
        impersonate_val = self.impersonate_combo.currentText()
        if impersonate_val == "无":
            impersonate_val = None

        cookie_browser_val = self.cookie_browser_combo.currentText().lower()
        if cookie_browser_val == "不导入":
            cookie_browser_val = None

        # format 取值优先级：
        #   1) combo 里通过 userData 塞的"已选：..."项（具体 format_id+format_id）
        #   2) _format_spec 字段（预览框返回）
        #   3) preset 下拉名字（走 config.py 里的 FORMAT_PRESETS 映射）
        fmt_data = self.format_combo.currentData()
        if isinstance(fmt_data, str) and "+" in fmt_data:
            format_preset = fmt_data
        elif self._format_spec:
            format_preset = self._format_spec
        else:
            preset_name = self.format_combo.currentText()
            format_preset = FORMAT_PRESETS.get(preset_name, "best")

        return DownloadTask(
            url=self.url_input.text().strip(),
            save_path=self.dir_input.text(),
            format_preset=format_preset,
            proxy=self.proxy_input.text().strip() or None,
            concurrent_fragments=int(self.concurrent_input.text())
            if self.concurrent_input.text().isdigit()
            else None,
            write_subs=self.write_subs_checkbox.isChecked(),
            download_playlist=self.download_playlist_checkbox.isChecked(),
            playlist_items=self.playlist_items_input.text().strip() or None,
            max_downloads=int(self.max_downloads_input.text())
            if self.max_downloads_input.text().isdigit()
            else None,
            impersonate=impersonate_val,
            cookie_browser=cookie_browser_val,
            ratelimit=self.ratelimit_input.text().strip() or None,
        )


GITHUB_URL = "https://github.com/twn39/yt-dlp-qt-gui"


class AboutDialog(QDialog):
    """现代化「关于」对话框，包含项目信息和 GitHub 链接"""

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于 Yt-dlp GUI")
        self.setFixedSize(380, 330)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui(version)

    def _setup_ui(self, version: str) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(32, 24, 32, 20)

        # 应用图标 —— scale_factor 避免字形左右边界被裁剪
        icon_container = QLabel()
        icon_container.setFixedSize(64, 64)
        icon_container.setPixmap(
            qta.icon("fa5s.cloud-download-alt", color="#FFFFFF", scale_factor=0.85).pixmap(56, 56)
        )
        icon_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 应用名称（与应用主字号协调：13pt，粗体）
        name_label = QLabel("Yt-dlp GUI")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 15pt; font-weight: bold; color: #E0E0E0;")
        layout.addWidget(name_label)

        # 副标题 + 版本
        try:
            import yt_dlp

            yt_version = getattr(getattr(yt_dlp, "version", None), "__version__", "")
        except Exception:
            yt_version = ""

        ver_info = f"v{version}" + (f" (yt-dlp {yt_version})" if yt_version else "")
        subtitle_label = QLabel(f"{ver_info}  ·  现代化视频下载管理器")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("font-size: 9pt; color: #888888;")
        layout.addWidget(subtitle_label)

        # 分隔线（QFrame HLine 用 background-color 而非 color）
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2A2A2A; border: none;")
        layout.addWidget(sep)
        layout.addSpacing(2)

        # 简介
        desc_label = QLabel(
            "基于 yt-dlp 构建的开源视频下载工具\n支持 YouTube、Bilibili、Vimeo 等数千个视频平台"
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 9pt; color: #AAAAAA; line-height: 160%;")
        layout.addWidget(desc_label)

        layout.addSpacing(4)

        # GitHub 链接按钮 —— 白色图标与白色文字
        github_btn = QPushButton(
            qta.icon("fa5b.github", color="#FFFFFF"),
            f"  {GITHUB_URL.removeprefix('https://')}",
        )
        github_btn.setStyleSheet(
            "QPushButton { color: #FFFFFF; font-size: 9pt; }"
            "QPushButton:hover { color: #E0E0E0; border-color: #555555; }"
        )
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        layout.addWidget(github_btn)

        # 关闭按钮行（居中，固定宽度）
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setMinimumHeight(32)
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        layout.addLayout(btn_row)


class DialogManager:
    """对话框管理器，用于解耦 MainWindow 对具体对话框类的直接实例化依赖"""

    def __init__(self, parent_window: QWidget) -> None:
        self.parent = parent_window

    def show_about(self, version: str) -> None:
        """显示关于对话框"""
        dialog = AboutDialog(version=version, parent=self.parent)
        dialog.exec()

    def show_add_task(self, initial_url: str | None = None) -> Optional[DownloadTask]:
        """显示添加任务对话框，若确认且数据有效，则返回 DownloadTask 实体，否则返回 None"""
        dialog = AddTaskDialog(parent=self.parent, initial_url=initial_url)
        if dialog.exec():
            return dialog.get_task_data()
        return None

    def show_log(
        self, task_id: int, title: str, logs: str, on_finished: Callable[[], None]
    ) -> QDialog:
        """显示非模态的任务日志对话框"""
        dialog = LogDialog(task_id=task_id, title=title, parent=self.parent)
        dialog.set_initial_logs(logs)
        dialog.finished.connect(on_finished)
        dialog.show()
        return dialog
