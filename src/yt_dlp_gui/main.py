import sys
import os
from typing import Any
import click
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QTextEdit,
    QToolBar,
    QProgressBar,
    QLabel,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QComboBox,
)
from PySide6.QtCore import (
    QThread,
    Slot,
    QSize,
    QStandardPaths,
    QMimeData,
    Qt,
)
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QClipboard
from .worker import DownloadWorker
from .config import (
    WINDOW_TITLE,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    STYLESHEET_FILE,
    ICON_SIZE,
    ICON_COLOR,
    ICON_COLOR_ACTIVE_ACCENT,
    ICON_COLOR_ACTIVE_DELETE,
    ICON_COLOR_ACTIVE_CANCEL,
    PROGRESS_BAR_MAX_WIDTH,
    FORMAT_PRESETS,
)


def load_stylesheet(filename: str = STYLESHEET_FILE) -> str | None:
    """加载 QSS 样式文件"""
    # 尝试多个可能的路径
    possible_paths = []
    
    # PyInstaller 打包后的临时目录路径
    if getattr(sys, 'frozen', False):
        # 在 PyInstaller 打包的环境中运行
        if hasattr(sys, '_MEIPASS'):
            # 文件被解压到 _MEIPASS 目录
            possible_paths.append(os.path.join(sys._MEIPASS, filename))
        # 可执行文件所在目录
        possible_paths.append(os.path.join(os.path.dirname(sys.executable), filename))
    else:
        # 开发环境
        possible_paths.append(filename)  # 相对于当前工作目录
        possible_paths.append(os.path.join(os.path.dirname(__file__), "..", "..", filename))  # src 布局
        possible_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", filename))
    
    for filepath in possible_paths:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"加载样式文件时出错: {e}")
                continue
    
    print(f"警告: 样式文件未找到，尝试的路径: {possible_paths}")
    return None


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # 启用拖拽
        self.setAcceptDrops(True)

        self.current_thread: QThread | None = None
        self.current_worker: DownloadWorker | None = None
        self._last_progress: int = 0  # 跟踪最大进度，防止进度条跳动

        self.selected_download_path = self._get_default_download_path()

        self._setup_ui()
        self._apply_dark_theme()
        self._setup_toolbar()
        self._setup_status_bar()

    def _get_default_download_path(self) -> str:
        """获取默认的下载目录"""
        path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if not path or not os.path.exists(path):
            path = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.HomeLocation
            )
        if not path:
            path = "."
        return path

    def _setup_ui(self) -> None:
        """设置用户界面布局和控件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- URL 输入 ---
        url_layout = QHBoxLayout()
        self.url_label = QLabel("视频 URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("在此粘贴视频链接，或拖拽 URL 到此窗口...")
        self.url_input.returnPressed.connect(self._start_download)  # 回车开始下载
        url_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)

        # --- 格式选择 ---
        format_layout = QHBoxLayout()
        self.format_label = QLabel("下载格式:")
        self.format_combo = QComboBox()
        
        # 为每个格式预设添加图标
        format_icons = {
            "最佳质量 (MP4)": qta.icon("fa5s.star", color=ICON_COLOR),
            "最佳质量 (任意格式)": qta.icon("fa5s.crown", color=ICON_COLOR),
            "1080p": qta.icon("fa5s.video", color=ICON_COLOR),
            "720p": qta.icon("fa5s.film", color=ICON_COLOR),
            "480p": qta.icon("fa5s.play-circle", color=ICON_COLOR),
            "仅音频 (最佳)": qta.icon("fa5s.music", color=ICON_COLOR),
            "仅音频 (MP3)": qta.icon("fa5s.headphones", color=ICON_COLOR),
        }
        
        # 添加带图标的格式选项
        for format_name in FORMAT_PRESETS.keys():
            icon = format_icons.get(format_name, qta.icon("fa5s.file", color=ICON_COLOR))
            self.format_combo.addItem(icon, format_name)
        
        self.format_combo.setCurrentIndex(0)  # 默认选择第一个
        self.format_combo.setToolTip("选择视频下载质量和格式")
        
        # 设置下拉箭头图标
        arrow_icon = qta.icon("fa5s.caret-down", color=ICON_COLOR)
        self.format_combo.view().window().setWindowIcon(arrow_icon)
        
        # 修复下拉列表白边问题
        dropdown_view = self.format_combo.view()
        dropdown_view.setStyleSheet("""
            QAbstractItemView {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                outline: none;
                padding: 0px;
                margin: 0px;
            }
            QAbstractItemView::item {
                padding: 6px 10px;
                min-height: 25px;
                border: none;
                background-color: transparent;
            }
            QAbstractItemView::item:hover {
                background-color: #444444;
                border: none;
            }
            QAbstractItemView::item:selected {
                background-color: #007acc;
                color: white;
                border: none;
            }
        """)
        
        format_layout.addWidget(self.format_label)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()

        # --- 代理输入 ---
        proxy_layout = QHBoxLayout()
        self.proxy_label = QLabel("HTTP 代理:")
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText(
            "例如: http://127.0.0.1:7890 (留空则不使用)"
        )
        proxy_layout.addWidget(self.proxy_label)
        proxy_layout.addWidget(self.proxy_input)

        # --- 下载目录 ---
        download_dir_layout = QHBoxLayout()
        self.download_dir_label = QLabel("保存目录:")
        self.download_directory_input = QLineEdit(self.selected_download_path)
        self.download_directory_input.setReadOnly(True)
        self.select_dir_button = QPushButton("浏览...")
        self.select_dir_button.setToolTip("选择视频保存的文件夹")
        self.select_dir_button.clicked.connect(self._select_download_directory)
        download_dir_layout.addWidget(self.download_dir_label)
        download_dir_layout.addWidget(self.download_directory_input)
        download_dir_layout.addWidget(self.select_dir_button)

        # --- 日志/输出区域 ---
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("下载日志将在此显示...")

        # 添加所有布局
        main_layout.addLayout(url_layout)
        main_layout.addLayout(format_layout)
        main_layout.addLayout(proxy_layout)
        main_layout.addLayout(download_dir_layout)
        main_layout.addWidget(self.log_output)

    def _setup_toolbar(self) -> None:
        """设置工具栏及其动作"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.addToolBar(toolbar)

        # 下载按钮
        download_icon = qta.icon(
            "fa5s.download", color=ICON_COLOR, color_active=ICON_COLOR_ACTIVE_ACCENT
        )
        self.download_action = QAction(download_icon, "下载", self)
        self.download_action.setStatusTip("开始下载输入的 URL (Enter)")
        self.download_action.triggered.connect(self._start_download)
        toolbar.addAction(self.download_action)

        # 粘贴 URL 按钮
        paste_icon = qta.icon(
            "fa5s.paste", color=ICON_COLOR, color_active=ICON_COLOR_ACTIVE_ACCENT
        )
        paste_action = QAction(paste_icon, "粘贴 URL", self)
        paste_action.setStatusTip("从剪贴板粘贴 URL")
        paste_action.triggered.connect(self._paste_url_from_clipboard)
        toolbar.addAction(paste_action)

        toolbar.addSeparator()

        # 清除日志按钮
        clear_icon = qta.icon(
            "fa5s.trash-alt", color=ICON_COLOR, color_active=ICON_COLOR_ACTIVE_DELETE
        )
        clear_action = QAction(clear_icon, "清除日志", self)
        clear_action.setStatusTip("清除下方的日志输出")
        clear_action.triggered.connect(self._clear_log)
        toolbar.addAction(clear_action)

        # 取消按钮
        cancel_icon = qta.icon(
            "fa5s.times-circle", color=ICON_COLOR, color_active=ICON_COLOR_ACTIVE_CANCEL
        )
        self.cancel_action = QAction(cancel_icon, "取消下载", self)
        self.cancel_action.setStatusTip("尝试取消当前下载")
        self.cancel_action.triggered.connect(self._cancel_download)
        self.cancel_action.setEnabled(False)
        toolbar.addAction(self.cancel_action)

    def _setup_status_bar(self) -> None:
        """设置状态栏"""
        self.status_label = QLabel("就绪 - 拖拽或粘贴 URL 开始下载")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(PROGRESS_BAR_MAX_WIDTH)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.statusBar().addPermanentWidget(self.status_label)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()

    def _apply_dark_theme(self) -> None:
        """应用深色主题"""
        style_sheet = load_stylesheet(STYLESHEET_FILE)
        if style_sheet:
            self.setStyleSheet(style_sheet)
        else:
            print("未能加载暗色主题样式。")

    # ==================== 拖拽支持 ====================

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """处理拖拽进入事件"""
        mime_data: QMimeData = event.mimeData()
        if mime_data.hasUrls() or mime_data.hasText():
            event.acceptProposedAction()
            self.status_label.setText("释放以添加 URL...")
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """处理拖放事件"""
        mime_data: QMimeData = event.mimeData()
        url = ""
        if mime_data.hasUrls():
            # 获取第一个 URL
            urls = mime_data.urls()
            if urls:
                url = urls[0].toString()
        elif mime_data.hasText():
            url = mime_data.text().strip()

        if url:
            self.url_input.setText(url)
            self._append_log(f"已添加拖拽的 URL: {url}")
            self.status_label.setText("就绪")
            event.acceptProposedAction()
        else:
            event.ignore()
            self.status_label.setText("就绪")

    # ==================== 槽函数 ====================

    @Slot()
    def _paste_url_from_clipboard(self) -> None:
        """从剪贴板粘贴 URL"""
        clipboard: QClipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.url_input.setText(text)
            self._append_log(f"已从剪贴板粘贴: {text}")
        else:
            self._append_log("剪贴板中没有文本内容")

    @Slot()
    def _select_download_directory(self) -> None:
        """打开目录选择对话框并更新路径"""
        start_dir = (
            self.selected_download_path
            if os.path.isdir(self.selected_download_path)
            else self._get_default_download_path()
        )
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:
            normalized_path = os.path.normpath(directory)
            self.selected_download_path = normalized_path
            self.download_directory_input.setText(normalized_path)
            self._append_log(f"设置保存目录为: {normalized_path}")

    def _cleanup_previous_download(self) -> None:
        """清理上一次下载的资源"""
        if self.current_worker:
            try:
                self.current_worker.progress.disconnect()
                self.current_worker.finished.disconnect()
                self.current_worker.log_message.disconnect()
            except RuntimeError:
                pass  # 信号可能已经断开
            self.current_worker.deleteLater()
            self.current_worker = None

        if self.current_thread:
            if self.current_thread.isRunning():
                self.current_thread.quit()
                self.current_thread.wait(100)  # 等待线程结束
            self.current_thread = None

    @Slot()
    def _start_download(self) -> None:
        """开始下载过程"""
        if self.current_thread is not None and self.current_thread.isRunning():
            QMessageBox.warning(self, "提示", "当前已有下载任务在进行中。")
            return

        # 确保上次下载的资源已清理
        self._cleanup_previous_download()

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入有效的视频 URL。")
            return

        # 获取代理地址
        proxy_address = self.proxy_input.text().strip()
        if proxy_address and not (
            proxy_address.startswith("http://")
            or proxy_address.startswith("https://")
            or proxy_address.startswith("socks")
        ):
            self._append_log(
                f"警告: 代理地址 '{proxy_address}' 格式可能不正确"
            )

        # 获取下载路径
        download_path = self.download_directory_input.text().strip()
        if not download_path or not os.path.isdir(download_path):
            QMessageBox.warning(
                self,
                "错误",
                f"无效的保存目录: {download_path}\n请通过 '浏览...' 按钮选择一个有效的文件夹。",
            )
            return

        # 获取格式预设
        format_name = self.format_combo.currentText()
        format_preset = FORMAT_PRESETS.get(format_name)

        # UI 状态更新
        self.status_label.setText("准备下载...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMaximum(100)
        self.progress_bar.show()
        self._last_progress = 0  # 重置进度跟踪
        self.download_action.setEnabled(False)
        self.cancel_action.setEnabled(True)

        # 创建工作线程
        self.current_thread = QThread(self)
        self.current_worker = DownloadWorker(
            url=url,
            download_path=download_path,
            format_preset=format_preset,
            proxy=proxy_address if proxy_address else None,
        )
        self.current_worker.moveToThread(self.current_thread)

        # 连接信号
        self.current_worker.progress.connect(self._update_progress)
        self.current_worker.finished.connect(self._download_finished)
        self.current_worker.log_message.connect(self._append_log)
        self.current_thread.finished.connect(self._thread_cleanup)
        self.current_thread.started.connect(self.current_worker.run)

        # 开始下载
        self._append_log(f"开始下载: {url}")
        self._append_log(f"格式: {format_name}")
        self.current_thread.start()

    @Slot(dict)
    def _update_progress(self, progress_data: dict[str, Any]) -> None:
        """更新进度条和状态栏"""
        try:
            status = progress_data.get("status")
            if status == "downloading":
                filename = os.path.basename(
                    progress_data.get("info_dict", {}).get("filename")
                    or progress_data.get("filename")
                    or "未知文件"
                )
                total_bytes_str = progress_data.get(
                    "total_bytes_estimate"
                ) or progress_data.get("total_bytes")
                downloaded_bytes_str = progress_data.get("downloaded_bytes")
                speed_str = progress_data.get("speed_str", "N/A").strip()
                eta_str = progress_data.get("eta_str", "N/A").strip()

                if total_bytes_str is not None and downloaded_bytes_str is not None:
                    total_bytes = float(total_bytes_str)
                    downloaded_bytes = float(downloaded_bytes_str)
                    if total_bytes > 0:
                        percentage = int((downloaded_bytes / total_bytes) * 100)
                        # 确保进度只增不减（防止续传时跳动）
                        if percentage >= self._last_progress:
                            self._last_progress = percentage
                            self.progress_bar.setValue(percentage)
                        self.progress_bar.setFormat("%p%")
                        self.progress_bar.setMaximum(100)
                        self.status_label.setText(
                            f"下载中: {filename[:30]}... ({self._last_progress}%) | {speed_str} | 剩余: {eta_str}"
                        )
                    else:
                        downloaded_mbytes = downloaded_bytes / (1024 * 1024)
                        self.progress_bar.setFormat("%.2f MiB" % downloaded_mbytes)
                        self.progress_bar.setValue(0)
                        self.progress_bar.setMaximum(0)
                        self.status_label.setText(
                            f"下载中: {filename[:30]}... | {speed_str}"
                        )
                else:
                    self.status_label.setText(
                        f"下载中: {filename[:30]}... | {speed_str} | 剩余: {eta_str}"
                    )
                    self.progress_bar.setFormat("处理中...")
                    self.progress_bar.setMaximum(0)
                    self.progress_bar.setValue(0)

            elif status == "finished":
                filename = os.path.basename(progress_data.get("filename") or "未知文件")
                self.status_label.setText(f"处理完成: {filename[:40]}...")
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("%p%")
                self.progress_bar.setMaximum(100)

        except Exception as e:
            self._append_log(f"处理进度信息时出错: {e}")

    @Slot(bool, str)
    def _download_finished(self, success: bool, message: str) -> None:
        """下载完成回调"""
        if success:
            self.status_label.setText("✓ 下载成功完成")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("完成")
            self.progress_bar.setMaximum(100)
            self._append_log(f"✓ 成功: {message}")
        else:
            if "取消" in message:
                self.status_label.setText("⊘ 下载已取消")
                self.progress_bar.setFormat("已取消")
                self._append_log(f"⊘ 信息: {message}")
            else:
                self.status_label.setText("✗ 下载失败")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("失败")
                self.progress_bar.setMaximum(100)
                QMessageBox.critical(self, "失败", f"下载失败。\n原因: {message}")
                self._append_log(f"✗ 失败: {message}")

        self.download_action.setEnabled(True)
        self.cancel_action.setEnabled(False)

        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()

    @Slot()
    def _thread_cleanup(self) -> None:
        """线程结束后清理资源"""
        self._append_log("下载线程已结束。")
        # 断开信号连接防止残留信号影响新下载
        if self.current_worker:
            try:
                self.current_worker.progress.disconnect()
                self.current_worker.finished.disconnect()
                self.current_worker.log_message.disconnect()
            except RuntimeError:
                pass
            self.current_worker.deleteLater()
            self.current_worker = None
        self.current_thread = None

        if not self.cancel_action.isEnabled():
            self.download_action.setEnabled(True)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """向日志区域追加消息"""
        self.log_output.append(message)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _clear_log(self) -> None:
        """清除日志区域内容"""
        self.log_output.clear()

    @Slot()
    def _cancel_download(self) -> None:
        """尝试取消当前下载"""
        if (
            self.current_worker
            and self.current_thread
            and self.current_thread.isRunning()
        ):
            self.status_label.setText("正在尝试取消...")
            self._append_log("发送取消请求...")
            self.current_worker.cancel()
            self.cancel_action.setEnabled(False)
        else:
            self._append_log("没有正在运行的下载任务可以取消。")

    def closeEvent(self, event) -> None:
        """关闭窗口前尝试停止线程"""
        if self.current_thread and self.current_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
                "当前有下载任务正在进行中，确定要退出吗？\n（将尝试取消下载）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._append_log("用户请求退出，尝试取消下载...")
                self._cancel_download()
                if self.current_thread:
                    self.current_thread.quit()
                    if not self.current_thread.wait(500):
                        self._append_log(
                            "警告：下载线程未能及时停止，可能在后台继续运行。"
                        )
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def run_gui() -> None:
    """启动 GUI 应用程序"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


@click.command()
@click.version_option(version="0.1.0", prog_name="yt-dlp-gui")
def cli() -> None:
    """Yt-dlp GUI - 现代化视频下载工具
    
    支持从 YouTube、Bilibili、Vimeo 等数千个视频网站下载视频。
    """
    run_gui()


if __name__ == "__main__":
    # 支持两种启动方式
    # 如果是 click 的帮助或版本命令，使用 cli()
    # 否则直接启动 GUI
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "--version", "-h", "-V"]:
        cli()
    else:
        run_gui()
