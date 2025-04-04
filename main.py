import sys
import os
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QToolBar, QStatusBar, QProgressBar, QLabel,
    QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, Slot
from PySide6.QtGui import QAction, QPalette, QColor

# 尝试导入 yt_dlp
try:
    import yt_dlp
except ImportError:
    print("错误：找不到 yt-dlp 库。请确保已安装：pip install yt-dlp")
    sys.exit(1)

# --- 黑色磨砂主题样式表 ---
DARK_STYLE_SHEET = """
QWidget {
    background-color: #2b2b2b; /* 深灰色背景 */
    color: #dcdcdc; /* 浅灰色文字 */
    font-family: "Segoe UI", Arial, sans-serif; /* 可选：指定字体 */
    font-size: 10pt;
}

QMainWindow {
    background-color: #2b2b2b;
}

QToolBar {
    background-color: #3c3c3c; /* 工具栏稍亮背景 */
    border: none;
    padding: 3px;
    spacing: 5px; /* 图标间距 */
}

QToolBar QToolButton {
    background-color: #3c3c3c;
    color: #dcdcdc;
    padding: 5px;
    border-radius: 3px;
}

QToolBar QToolButton:hover {
    background-color: #555555; /* 悬停效果 */
}

QToolBar QToolButton:pressed {
    background-color: #4a4a4a;
}

QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #555555;
    padding: 5px;
    border-radius: 3px;
    color: #dcdcdc;
}

QLineEdit:focus {
    border: 1px solid #007acc; /* 焦点时边框颜色 */
}

QTextEdit {
    background-color: #252525; /* 文本区域更暗背景 */
    border: 1px solid #555555;
    color: #cccccc; /* 日志文本颜色 */
    border-radius: 3px;
    font-family: "Consolas", "Courier New", monospace; /* 等宽字体适合日志 */
}

QStatusBar {
    background-color: #3c3c3c;
    color: #dcdcdc;
}

QStatusBar QLabel { /* 确保状态栏内的标签也应用颜色 */
    color: #dcdcdc;
    background-color: transparent; /* 避免覆盖背景 */
}


QProgressBar {
    border: 1px solid #555555;
    border-radius: 3px;
    text-align: center;
    background-color: #3c3c3c;
    color: #dcdcdc;
}

QProgressBar::chunk {
    background-color: #007acc; /* 进度条颜色 */
    border-radius: 2px;
    margin: 0.5px;
}

QMessageBox {
     background-color: #2b2b2b;
}

QMessageBox QLabel {
    color: #dcdcdc;
    background-color: transparent;
}

QMessageBox QPushButton {
    background-color: #3c3c3c;
    color: #dcdcdc;
    border: 1px solid #555555;
    padding: 5px 10px;
    border-radius: 3px;
    min-width: 60px;
}

QMessageBox QPushButton:hover {
    background-color: #555555;
}

QMessageBox QPushButton:pressed {
    background-color: #4a4a4a;
}
"""

# --- 下载工作线程 ---
class DownloadWorker(QObject):
    """
    在单独线程中运行 yt-dlp 下载任务。
    """
    progress = Signal(dict)  # 发送进度信息字典
    finished = Signal(bool, str)  # 发送完成状态 (成功/失败, 消息/文件路径)
    log_message = Signal(str)     # 发送普通日志消息

    def __init__(self, url, download_path='.', ydl_opts=None):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.ydl_opts = ydl_opts if ydl_opts else {}
        self._is_cancelled = False

    def _progress_hook(self, d):
        """yt-dlp 进度钩子函数"""
        # print(d) # 调试用，查看所有信息
        if d['status'] == 'downloading':
            self.progress.emit(d)
        elif d['status'] == 'finished':
            self.log_message.emit(f"下载完成: {d.get('filename', '未知文件')}")
        elif d['status'] == 'error':
            self.log_message.emit(f"下载错误: {d.get('filename', '未知文件')}")
        # 可以根据需要处理 'processing', 'error' 等其他状态

    @Slot()
    def run(self):
        """执行下载"""
        if not self.url:
            self.finished.emit(False, "URL 不能为空")
            return

        # 基础 yt-dlp 选项
        options = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # 尝试下载最佳 MP4，否则下载最佳
            'outtmpl': os.path.join(self.download_path, '%(title)s [%(id)s].%(ext)s'), # 输出文件名模板
            'progress_hooks': [self._progress_hook], # 进度回调
            'noplaylist': True, # 默认不下载播放列表，如有需要可修改
            'logger': self.YtdlpLogger(self.log_message), # 自定义日志记录器
            'noprogress': True, # 禁用 yt-dlp 自己的控制台进度条，我们用钩子
            # 'verbose': True, # 开启详细日志（调试用）
        }
        # 合并用户提供的选项
        options.update(self.ydl_opts)

        try:
            self.log_message.emit(f"开始下载: {self.url}")
            self.log_message.emit(f"下载目录: {os.path.abspath(self.download_path)}")
            self.log_message.emit(f"使用选项: {options}") # 调试

            with yt_dlp.YoutubeDL(options) as ydl:
                # 这里需要处理可能的下载错误
                try:
                    info_dict = ydl.extract_info(self.url, download=True)
                    if not self._is_cancelled:
                        self.finished.emit(True, "下载任务已提交给 yt-dlp。") # 消息可以更具体

                except yt_dlp.utils.DownloadError as e:
                    self.log_message.emit(f"yt-dlp 下载错误: {e}")
                    if not self._is_cancelled:
                        self.finished.emit(False, f"下载失败: {e}")
                except Exception as e:
                    self.log_message.emit(f"yt-dlp 执行时发生意外错误: {e}")
                    if not self._is_cancelled:
                        self.finished.emit(False, f"意外错误: {e}")

        except Exception as e:
            self.log_message.emit(f"初始化 YoutubeDL 时出错: {e}")
            if not self._is_cancelled:
                self.finished.emit(False, f"初始化失败: {e}")

    def cancel(self):
        self._is_cancelled = True
        self.log_message.emit("请求取消下载...")
        # 注意：yt-dlp 没有直接的 API 来中断正在进行的下载
        # 这里设置标志位，避免下载完成后发送 finished 信号
        # 对于长时间的下载，这可能不会立即停止

    # --- 自定义日志记录器，将 yt-dlp 的日志发送到 GUI ---
    class YtdlpLogger:
        def __init__(self, log_signal):
            self.log_signal = log_signal

        def debug(self, msg):
            # 通常我们不在 GUI 中显示 debug 信息，除非需要详细调试
            # print(f"DEBUG: {msg}")
            # 过滤掉进度条更新信息，因为我们用 progress_hook
            if msg.startswith('[debug] '):
                pass # 可以选择性记录
            elif not msg.startswith('[download]'): # 过滤掉进度信息
                self.log_signal.emit(msg)


        def warning(self, msg):
            self.log_signal.emit(f"警告: {msg}")

        def error(self, msg):
            self.log_signal.emit(f"错误: {msg}")

        def info(self, msg):
            # 过滤掉进度条更新信息
            if not msg.startswith('[download]'):
                self.log_signal.emit(msg)


# --- 主窗口 ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频下载管理器 (PySide6 + yt-dlp)")
        self.setGeometry(100, 100, 800, 600)

        self.current_thread = None
        self.current_worker = None

        self.setup_ui()
        self.setup_toolbar()
        self.apply_dark_theme() # 应用深色主题

        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200) # 限制进度条宽度
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%") # 显示百分比
        self.statusBar().addPermanentWidget(self.status_label)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.hide() # 初始隐藏

    def setup_ui(self):
        """设置用户界面布局和控件"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # URL 输入区域
        input_layout = QHBoxLayout()
        self.url_label = QLabel("视频 URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("在此粘贴视频链接...")
        input_layout.addWidget(self.url_label)
        input_layout.addWidget(self.url_input)

        # 日志/输出区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        main_layout.addLayout(input_layout)
        main_layout.addWidget(self.log_output)

    def setup_toolbar(self):
        """设置工具栏及其动作"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False) # 不允许移动
        self.addToolBar(toolbar)

        # --- 下载动作 ---
        # 使用 qtawesome 获取图标
        download_icon = qta.icon('fa5s.download', color='#dcdcdc', color_active='#007acc')
        self.download_action = QAction(download_icon, "下载", self)
        self.download_action.setStatusTip("开始下载输入的 URL")
        self.download_action.triggered.connect(self.start_download)
        toolbar.addAction(self.download_action)

        # --- 清除日志动作 ---
        clear_icon = qta.icon('fa5s.trash-alt', color='#dcdcdc', color_active='#cc0000')
        clear_action = QAction(clear_icon, "清除日志", self)
        clear_action.setStatusTip("清除下方的日志输出")
        clear_action.triggered.connect(self.clear_log)
        toolbar.addAction(clear_action)

        # --- (可选) 取消动作 ---
        cancel_icon = qta.icon('fa5s.times-circle', color='#dcdcdc', color_active='#cc0000')
        self.cancel_action = QAction(cancel_icon, "取消下载", self)
        self.cancel_action.setStatusTip("尝试取消当前下载")
        self.cancel_action.triggered.connect(self.cancel_download)
        self.cancel_action.setEnabled(False) # 初始禁用
        toolbar.addAction(self.cancel_action)


    def apply_dark_theme(self):
        """应用 QSS 样式表"""
        self.setStyleSheet(DARK_STYLE_SHEET)

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

        # 准备下载目录 (这里简单使用当前目录，可以添加选择功能)
        download_path = '.'
        # self.download_directory # 如果实现了目录选择


        self.status_label.setText("准备下载...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.download_action.setEnabled(False) # 禁用下载按钮
        self.cancel_action.setEnabled(True)  # 启用取消按钮

        # 创建线程和工作对象
        self.current_thread = QThread(self)
        self.current_worker = DownloadWorker(url, download_path)
        self.current_worker.moveToThread(self.current_thread)

        # 连接信号槽
        self.current_worker.progress.connect(self.update_progress)
        self.current_worker.finished.connect(self.download_finished)
        self.current_worker.log_message.connect(self.append_log)
        self.current_thread.started.connect(self.current_worker.run)
        self.current_thread.finished.connect(self.thread_cleanup) # 线程结束后清理

        # 启动线程
        self.current_thread.start()

    @Slot(dict)
    def update_progress(self, progress_data):
        """更新进度条和状态栏"""
        try:
            status = progress_data.get('status')
            if status == 'downloading':
                total_bytes_str = progress_data.get('total_bytes_estimate') or progress_data.get('total_bytes')
                downloaded_bytes_str = progress_data.get('downloaded_bytes')
                speed_str = progress_data.get('speed_str', 'N/A')
                eta_str = progress_data.get('eta_str', 'N/A')
                filename = os.path.basename(progress_data.get('filename', '未知文件'))
                # filename = progress_data.get('_filename', '未知文件') # 尝试 _filename

                if total_bytes_str and downloaded_bytes_str:
                    total_bytes = float(total_bytes_str)
                    downloaded_bytes = float(downloaded_bytes_str)
                    if total_bytes > 0:
                        percentage = int((downloaded_bytes / total_bytes) * 100)
                        self.progress_bar.setValue(percentage)
                        self.status_label.setText(f"下载中: {filename} ({percentage}%) | 速度: {speed_str} | 剩余: {eta_str}")
                    else:
                        # 处理未知总大小的情况
                        self.progress_bar.setFormat("%v bytes") # 显示已下载字节数
                        self.progress_bar.setValue(int(downloaded_bytes))
                        self.progress_bar.setMaximum(0) # 设置为不定模式或显示字节
                        self.status_label.setText(f"下载中: {filename} ({progress_data.get('downloaded_bytes_str', '?')} B) | 速度: {speed_str}")

                else:
                    # 缺少进度信息时显示基本状态
                    self.status_label.setText(f"下载中: {filename} | 速度: {speed_str} | 剩余: {eta_str}")
                    self.progress_bar.setFormat("下载中...")
                    self.progress_bar.setMaximum(0) # 不定进度
                    self.progress_bar.setValue(0)


            elif status == 'finished':
                self.status_label.setText(f"处理完成: {os.path.basename(progress_data.get('filename', ''))}")
                self.progress_bar.setValue(100) # 确保完成时是100%
                self.progress_bar.setFormat("%p%")
                self.progress_bar.setMaximum(100)

        except Exception as e:
            self.append_log(f"处理进度信息时出错: {e}")
            print(f"原始进度数据: {progress_data}") # 调试用

    @Slot(bool, str)
    def download_finished(self, success, message):
        """下载完成或失败的处理"""
        if success:
            self.status_label.setText("下载成功完成")
            self.progress_bar.setValue(100) # 确保是100%
            self.progress_bar.setFormat("完成")
            QMessageBox.information(self, "成功", f"下载任务完成。\n{message}")
        else:
            self.status_label.setText(f"下载失败: {message}")
            self.progress_bar.setValue(0) # 或保持当前值，表示失败
            self.progress_bar.setFormat("失败")
            QMessageBox.critical(self, "失败", f"下载失败。\n原因: {message}")


        # 重新启用/禁用按钮
        self.download_action.setEnabled(True)
        self.cancel_action.setEnabled(False)

        # 请求线程退出 (如果它还没结束)
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()
            self.current_thread.wait(1000) # 等待最多1秒

        # 清理工作应该在 thread_cleanup 中完成，以确保线程完全停止


    @Slot()
    def thread_cleanup(self):
        """线程结束后清理资源"""
        self.append_log("下载线程已结束。")
        self.current_thread = None
        self.current_worker = None
        # 确保按钮状态正确
        self.download_action.setEnabled(True)
        self.cancel_action.setEnabled(False)
        # 可以选择隐藏进度条
        # self.progress_bar.hide()


    @Slot(str)
    def append_log(self, message):
        """向日志区域追加消息"""
        self.log_output.append(message)
        # 可以添加滚动到底部的逻辑
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())


    @Slot()
    def clear_log(self):
        """清除日志区域内容"""
        self.log_output.clear()

    @Slot()
    def cancel_download(self):
        """尝试取消当前下载"""
        if self.current_worker:
            self.status_label.setText("正在尝试取消...")
            self.append_log("发送取消请求...")
            self.current_worker.cancel()
            self.cancel_action.setEnabled(False) # 取消动作发出后禁用
            # 注意：这不保证能立即停止 yt-dlp 的网络操作


    def closeEvent(self, event):
        """关闭窗口前尝试停止线程"""
        if self.current_thread and self.current_thread.isRunning():
            reply = QMessageBox.question(self, '确认退出',
                                         '当前有下载任务正在进行中，确定要退出吗？\n（尝试取消下载）',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.cancel_download() # 尝试取消
                # 等待一小段时间让取消生效或线程自然结束
                self.current_thread.quit()
                if not self.current_thread.wait(2000): # 等待最多2秒
                    self.append_log("警告：下载线程未能及时停止。")
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# --- 程序入口 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())