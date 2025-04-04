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
)
from PySide6.QtCore import QThread, Slot, QSize
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

    def setup_ui(self):
        """设置用户界面布局和控件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        input_layout = QHBoxLayout()
        self.url_label = QLabel("视频 URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("在此粘贴视频链接...")
        input_layout.addWidget(self.url_label)
        input_layout.addWidget(self.url_input)

        proxy_layout = QHBoxLayout()
        self.proxy_label = QLabel("HTTP 代理:")
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText(
            "例如: http://127.0.0.1:7890 (留空则不使用)"
        )
        proxy_layout.addWidget(self.proxy_label)
        proxy_layout.addWidget(self.proxy_input)

        # 日志/输出区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        main_layout.addLayout(input_layout)
        main_layout.addLayout(proxy_layout)  # 将代理布局添加到主布局
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
        # 可以添加一些基本的验证，但 yt-dlp 会处理无效的代理字符串
        if proxy_address and not (
            proxy_address.startswith("http://")
            or proxy_address.startswith("https://")
            or proxy_address.startswith("socks")
        ):
            # 简单的提示，非强制
            self.append_log(
                f"警告: 代理地址 '{proxy_address}' 格式可能不正确，请确保其以 http://, https:// 或 socks5:// 等开头。"
            )

        download_path = "."  # 可以考虑让用户选择下载路径

        self.status_label.setText("准备下载...")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")  # 重置格式
        self.progress_bar.setMaximum(100)  # 重置最大值
        self.progress_bar.show()
        self.download_action.setEnabled(False)  # 禁用下载按钮
        self.cancel_action.setEnabled(True)  # 启用取消按钮

        # 创建线程和工作对象，传入代理地址
        self.current_thread = QThread(self)
        # 将 proxy_address 传递给 DownloadWorker
        self.current_worker = DownloadWorker(url, download_path, proxy=proxy_address)
        self.current_worker.moveToThread(self.current_thread)

        # 连接信号槽
        self.current_worker.progress.connect(self.update_progress)
        self.current_worker.finished.connect(self.download_finished)
        self.current_worker.log_message.connect(self.append_log)
        # 当线程结束时，执行清理操作
        self.current_thread.finished.connect(self.thread_cleanup)
        # 当线程启动时，执行 worker 的 run 方法
        self.current_thread.started.connect(self.current_worker.run)

        # 启动线程
        self.current_thread.start()

    @Slot(dict)
    def update_progress(self, progress_data):
        """更新进度条和状态栏"""
        try:
            status = progress_data.get("status")
            if status == "downloading":
                # 尝试获取更可靠的文件名
                filename = os.path.basename(
                    progress_data.get("info_dict", {}).get("filename")
                    or progress_data.get("filename")
                    or "未知文件"
                )

                total_bytes_str = progress_data.get(
                    "total_bytes_estimate"
                ) or progress_data.get("total_bytes")
                downloaded_bytes_str = progress_data.get("downloaded_bytes")
                speed_str = progress_data.get(
                    "speed_str", "N/A"
                ).strip()  # yt-dlp 可能输出带空格的速度
                eta_str = progress_data.get("eta_str", "N/A").strip()

                if total_bytes_str is not None and downloaded_bytes_str is not None:
                    total_bytes = float(total_bytes_str)
                    downloaded_bytes = float(downloaded_bytes_str)

                    if total_bytes > 0:
                        percentage = int((downloaded_bytes / total_bytes) * 100)
                        self.progress_bar.setValue(percentage)
                        self.progress_bar.setFormat("%p%")
                        self.progress_bar.setMaximum(100)  # 确保是百分比模式
                        self.status_label.setText(
                            f"下载中: {filename} ({percentage}%) | {speed_str} | 剩余: {eta_str}"
                        )
                    else:
                        # 处理总大小未知的情况 (例如直播或某些格式)
                        downloaded_mbytes = downloaded_bytes / (1024 * 1024)
                        self.progress_bar.setFormat(
                            "%.2f MiB" % downloaded_mbytes
                        )  # 显示已下载 MB
                        self.progress_bar.setValue(0)  # 不确定进度时值设为0
                        self.progress_bar.setMaximum(0)  # 设置为不定模式
                        self.status_label.setText(
                            f"下载中: {filename} ({progress_data.get('downloaded_bytes_str', '? B').strip()}) | {speed_str}"
                        )
                else:
                    # 缺少进度信息时显示基本状态
                    self.status_label.setText(
                        f"下载中: {filename} | {speed_str} | 剩余: {eta_str}"
                    )
                    self.progress_bar.setFormat("处理中...")
                    self.progress_bar.setMaximum(0)  # 不定进度
                    self.progress_bar.setValue(0)

            elif status == "finished":
                # 这个 finished 状态可能只是某个步骤完成，不一定是整个下载
                # 最终状态由 finished 信号处理
                filename = os.path.basename(progress_data.get("filename") or "未知文件")
                self.status_label.setText(f"处理完成: {filename}")
                # 可以在这里将进度条设为 100%，但最终状态在 download_finished 中确认
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("%p%")
                self.progress_bar.setMaximum(100)

        except Exception as e:
            self.append_log(f"处理进度信息时出错: {e}")
            # print(f"原始进度数据: {progress_data}") # 调试用

    @Slot(bool, str)
    def download_finished(self, success, message):

        if success:
            self.status_label.setText("下载成功完成")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("完成")
            self.progress_bar.setMaximum(100)  # 确保不是不定模式
            # QMessageBox.information(self, "成功", f"下载任务完成。\n{message}") # 可以简化提示
            self.append_log(f"成功: {message}")  # 将成功消息记录到日志
        else:
            # 检查是否是用户取消
            if "取消" in message:
                self.status_label.setText("下载已取消")
                self.progress_bar.setFormat("已取消")
                # 取消时进度条可以保持原样或归零
                # self.progress_bar.setValue(0)
                self.append_log(f"信息: {message}")  # 记录取消信息
                # QMessageBox.warning(self, "已取消", message) # 取消时可以不弹窗
            else:
                self.status_label.setText(f"下载失败")
                self.progress_bar.setValue(0)  # 失败时归零
                self.progress_bar.setFormat("失败")
                self.progress_bar.setMaximum(100)  # 确保不是不定模式
                QMessageBox.critical(self, "失败", f"下载失败。\n原因: {message}")
                self.append_log(f"失败: {message}")  # 记录失败信息

        # 重新启用/禁用按钮
        self.download_action.setEnabled(True)
        self.cancel_action.setEnabled(False)  # 任务结束后禁用取消按钮

        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()  # 请求退出事件循环

    @Slot()
    def thread_cleanup(self):
        """线程结束后清理资源"""
        # 这个槽函数会在 QThread 的 finished 信号发出后被调用
        self.append_log("下载线程已结束。")
        # 确保 worker 对象被删除或不再被引用，以便垃圾回收
        if self.current_worker:
            self.current_worker.deleteLater()  # 请求稍后删除 worker 对象
            self.current_worker = None
        self.current_thread = None  # 清除对线程对象的引用

        if not self.cancel_action.isEnabled():  # 只有当任务正常结束或失败时才重置
            self.download_action.setEnabled(True)

    @Slot(str)
    def append_log(self, message):
        """向日志区域追加消息"""
        self.log_output.append(message)
        # 自动滚动到底部
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
            # 注意：这不保证能立即停止 yt-dlp 的网络操作。
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
                self.cancel_download()  # 尝试取消

                if self.current_thread:
                    self.current_thread.quit()  # 请求线程事件循环退出
                    # 短暂等待，但不强制，避免卡死 UI
                    if not self.current_thread.wait(500):
                        self.append_log(
                            "警告：下载线程未能及时停止，可能在后台继续运行直到完成或出错。"
                        )

                event.accept()  # 接受关闭事件
            else:
                event.ignore()  # 忽略关闭事件，窗口不关闭
        else:
            event.accept()  # 没有任务运行，直接接受关闭事件


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
