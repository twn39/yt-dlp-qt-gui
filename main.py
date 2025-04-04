import sys
import os
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
)
from PySide6.QtCore import (
    QThread,
    Slot,
    QSize,
    QStandardPaths,
)
from PySide6.QtGui import QAction
from worker import DownloadWorker


def load_stylesheet(filename="dark_theme.qss"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)
    # 确保样式文件存在
    if not os.path.exists(filepath):
        print(f"警告: 样式文件未找到: {filepath}")
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"加载样式文件时出错: {e}")
        return None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yt-dlp GUI")
        self.setGeometry(100, 100, 800, 600)

        self.current_thread = None
        self.current_worker = None

        self.selected_download_path = self.get_default_download_path()

        self.setup_ui()
        self.apply_dark_theme()  # 应用深色主题
        self.setup_toolbar()

        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)  # 限制进度条宽度
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")  # 显示百分比
        self.statusBar().addPermanentWidget(self.status_label)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()  # 初始隐藏

    def get_default_download_path(self):
        """获取默认的下载目录 (通常是用户的 'Downloads' 文件夹)"""
        path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if not path or not os.path.exists(path):
            # 如果获取失败或目录不存在，则使用用户主目录
            path = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.HomeLocation
            )
        if not path:
            # 如果连主目录都获取失败，则使用当前工作目录
            path = "."
        return path

    def setup_ui(self):
        """设置用户界面布局和控件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- URL 输入 ---
        input_layout = QHBoxLayout()
        self.url_label = QLabel("视频 URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("在此粘贴视频链接...")
        input_layout.addWidget(self.url_label)
        input_layout.addWidget(self.url_input)

        # --- 代理输入 ---
        proxy_layout = QHBoxLayout()
        self.proxy_label = QLabel("HTTP 代理:")
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText(
            "例如: http://127.0.0.1:7890 (留空则不使用)"
        )
        proxy_layout.addWidget(self.proxy_label)
        proxy_layout.addWidget(self.proxy_input)

        download_dir_layout = QHBoxLayout()
        self.download_dir_label = QLabel("保存目录:")
        self.download_directory_input = QLineEdit(self.selected_download_path)
        self.download_directory_input.setReadOnly(True)
        self.select_dir_button = QPushButton("浏览...")
        self.select_dir_button.setToolTip("选择视频保存的文件夹")
        self.select_dir_button.clicked.connect(self.select_download_directory)

        download_dir_layout.addWidget(self.download_dir_label)
        download_dir_layout.addWidget(self.download_directory_input)
        download_dir_layout.addWidget(self.select_dir_button)

        # 日志/输出区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        main_layout.addLayout(input_layout)
        main_layout.addLayout(proxy_layout)
        main_layout.addLayout(download_dir_layout)
        main_layout.addWidget(self.log_output)

    def setup_toolbar(self):
        """设置工具栏及其动作"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        icon_color = "#cccccc"
        active_color_accent = "#00aaff"
        active_color_delete = "#ff6b6b"
        active_color_cancel = "#ffcc00"

        download_icon = qta.icon(
            "fa5s.download", color=icon_color, color_active=active_color_accent
        )
        self.download_action = QAction(download_icon, "下载", self)
        self.download_action.setStatusTip("开始下载输入的 URL")
        self.download_action.triggered.connect(self.start_download)
        toolbar.addAction(self.download_action)

        # --- 清除日志动作 ---
        clear_icon = qta.icon(
            "fa5s.trash-alt", color=icon_color, color_active=active_color_delete
        )
        clear_action = QAction(clear_icon, "清除日志", self)
        clear_action.setStatusTip("清除下方的日志输出")
        clear_action.triggered.connect(self.clear_log)
        toolbar.addAction(clear_action)

        # --- 取消动作 ---
        cancel_icon = qta.icon(
            "fa5s.times-circle", color=icon_color, color_active=active_color_cancel
        )
        self.cancel_action = QAction(cancel_icon, "取消下载", self)
        self.cancel_action.setStatusTip("尝试取消当前下载")
        self.cancel_action.triggered.connect(self.cancel_download)
        self.cancel_action.setEnabled(False)  # 初始禁用
        toolbar.addAction(self.cancel_action)

    def apply_dark_theme(self):
        style_sheet = load_stylesheet("dark_theme.qss")
        if style_sheet:
            self.setStyleSheet(style_sheet)
        else:
            print("未能加载暗色主题样式。")

    @Slot()
    def select_download_directory(self):
        """打开目录选择对话框并更新路径"""
        # 使用上次选择的目录或默认目录作为起始点
        start_dir = (
            self.selected_download_path
            if os.path.isdir(self.selected_download_path)
            else self.get_default_download_path()
        )
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            start_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if directory:  # 如果用户选择了目录 (没有取消)
            # 规范化路径表示 (例如，将 / 转换为 \ 在 Windows 上)
            normalized_path = os.path.normpath(directory)
            self.selected_download_path = normalized_path
            self.download_directory_input.setText(normalized_path)
            self.append_log(f"设置保存目录为: {normalized_path}")

    @Slot()
    def start_download(self):
        """开始下载过程"""
        if self.current_thread is not None and self.current_thread.isRunning():
            QMessageBox.warning(self, "提示", "当前已有下载任务在进行中。")
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入有效的视频 URL。")
            return

        # --- 获取代理地址 ---
        proxy_address = self.proxy_input.text().strip()
        if proxy_address and not (
            proxy_address.startswith("http://")
            or proxy_address.startswith("https://")
            or proxy_address.startswith("socks")
        ):
            self.append_log(
                f"警告: 代理地址 '{proxy_address}' 格式可能不正确，请确保其以 http://, https:// 或 socks5:// 等开头。"
            )

        download_path = self.download_directory_input.text().strip()
        if not download_path or not os.path.isdir(download_path):
            QMessageBox.warning(
                self,
                "错误",
                f"无效的保存目录: {download_path}\n请通过 '浏览...' 按钮选择一个有效的文件夹。",
            )
            return  # 或者直接返回，让用户重新选择

        self.status_label.setText("准备下载...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMaximum(100)
        self.progress_bar.show()
        self.download_action.setEnabled(False)
        self.cancel_action.setEnabled(True)

        self.current_thread = QThread(self)
        self.current_worker = DownloadWorker(url, download_path, proxy=proxy_address)
        self.current_worker.moveToThread(self.current_thread)

        self.current_worker.progress.connect(self.update_progress)
        self.current_worker.finished.connect(self.download_finished)
        self.current_worker.log_message.connect(self.append_log)
        self.current_thread.finished.connect(self.thread_cleanup)
        self.current_thread.started.connect(self.current_worker.run)

        self.current_thread.start()

    @Slot(dict)
    def update_progress(self, progress_data):
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
                        self.progress_bar.setValue(percentage)
                        self.progress_bar.setFormat("%p%")
                        self.progress_bar.setMaximum(100)
                        self.status_label.setText(
                            f"下载中: {filename} ({percentage}%) | {speed_str} | 剩余: {eta_str}"
                        )
                    else:
                        downloaded_mbytes = downloaded_bytes / (1024 * 1024)
                        self.progress_bar.setFormat("%.2f MiB" % downloaded_mbytes)
                        self.progress_bar.setValue(0)
                        self.progress_bar.setMaximum(0)
                        self.status_label.setText(
                            f"下载中: {filename} ({progress_data.get('downloaded_bytes_str', '? B').strip()}) | {speed_str}"
                        )
                else:
                    self.status_label.setText(
                        f"下载中: {filename} | {speed_str} | 剩余: {eta_str}"
                    )
                    self.progress_bar.setFormat("处理中...")
                    self.progress_bar.setMaximum(0)
                    self.progress_bar.setValue(0)

            elif status == "finished":
                filename = os.path.basename(progress_data.get("filename") or "未知文件")
                self.status_label.setText(f"处理完成: {filename}")
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("%p%")
                self.progress_bar.setMaximum(100)

        except Exception as e:
            self.append_log(f"处理进度信息时出错: {e}")

    @Slot(bool, str)
    def download_finished(self, success, message):
        if success:
            self.status_label.setText("下载成功完成")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("完成")
            self.progress_bar.setMaximum(100)
            self.append_log(f"成功: {message}")
        else:
            if "取消" in message:
                self.status_label.setText("下载已取消")
                self.progress_bar.setFormat("已取消")
                self.append_log(f"信息: {message}")
            else:
                self.status_label.setText(f"下载失败")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("失败")
                self.progress_bar.setMaximum(100)
                QMessageBox.critical(self, "失败", f"下载失败。\n原因: {message}")
                self.append_log(f"失败: {message}")

        self.download_action.setEnabled(True)
        self.cancel_action.setEnabled(False)

        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()

    @Slot()
    def thread_cleanup(self):
        """线程结束后清理资源"""
        self.append_log("下载线程已结束。")
        if self.current_worker:
            self.current_worker.deleteLater()
            self.current_worker = None
        self.current_thread = None

        if not self.cancel_action.isEnabled():
            self.download_action.setEnabled(True)

    @Slot(str)
    def append_log(self, message):
        """向日志区域追加消息"""
        self.log_output.append(message)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def clear_log(self):
        """清除日志区域内容"""
        self.log_output.clear()

    @Slot()
    def cancel_download(self):
        """尝试取消当前下载"""
        if (
            self.current_worker
            and self.current_thread
            and self.current_thread.isRunning()
        ):
            self.status_label.setText("正在尝试取消...")
            self.append_log("发送取消请求...")
            self.current_worker.cancel()
            self.cancel_action.setEnabled(False)
        else:
            self.append_log("没有正在运行的下载任务可以取消。")

    def closeEvent(self, event):
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
                self.append_log("用户请求退出，尝试取消下载...")
                self.cancel_download()
                if self.current_thread:
                    self.current_thread.quit()
                    if not self.current_thread.wait(500):
                        self.append_log(
                            "警告：下载线程未能及时停止，可能在后台继续运行直到完成或出错。"
                        )
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
