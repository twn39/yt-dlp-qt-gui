import os
from PySide6.QtCore import Signal, QObject, Slot
import yt_dlp


class DownloadWorker(QObject):
    progress = Signal(dict)  # 发送进度信息字典
    finished = Signal(bool, str)  # 发送完成状态 (成功/失败, 消息/文件路径)
    log_message = Signal(str)  # 发送普通日志消息

    # 修改 __init__ 以接受 proxy 参数
    def __init__(self, url, download_path=".", ydl_opts=None, proxy=None):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.ydl_opts = ydl_opts if ydl_opts else {}
        self.proxy = proxy  # 存储代理地址
        self._is_cancelled = False

    def _progress_hook(self, d):
        """yt-dlp 进度钩子函数"""
        if self._is_cancelled:  # 如果已取消，则忽略后续钩子调用
            # 可以在这里尝试引发一个错误来中断 yt-dlp，但这比较复杂且不可靠
            # raise yt_dlp.utils.DownloadError("用户取消") # 不推荐，可能导致状态混乱
            return

        if d["status"] == "downloading":
            self.progress.emit(d)
        elif d["status"] == "finished":
            # 检查是否是真正的文件下载完成，而不是后处理步骤
            # filename 通常在下载完成后出现
            if "filename" in d:
                self.log_message.emit(
                    f"文件下载完成: {os.path.basename(d.get('filename', '未知文件'))}"
                )
            else:
                # 可能是合并或其他后处理步骤完成
                self.log_message.emit(
                    f"处理步骤完成: {d.get('info_dict', {}).get('title', '未知任务')}"
                )
        elif d["status"] == "error":
            self.log_message.emit(f"下载错误: {d.get('filename', '未知文件')}")

    @Slot()
    def run(self):
        """执行下载"""
        if not self.url:
            self.finished.emit(False, "URL 不能为空")
            return

        # 基础 yt-dlp 选项
        options = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # 尝试下载最佳 MP4，否则下载最佳
            "outtmpl": os.path.join(
                self.download_path, "%(title)s [%(id)s].%(ext)s"
            ),  # 输出文件名模板
            "progress_hooks": [self._progress_hook],  # 进度回调
            "noplaylist": True,  # 默认不下载播放列表，如有需要可修改
            "logger": self.YtdlpLogger(self.log_message),  # 自定义日志记录器
            "noprogress": True,  # 禁用 yt-dlp 自己的控制台进度条，我们用钩子
            # 'verbose': True, # 开启详细日志（调试用）
            # 'quiet': True, # 如果只想通过 logger 和 hook 获取信息，可以开启
        }

        # --- 添加代理设置 ---
        if self.proxy:
            self.log_message.emit(f"使用代理: {self.proxy}")
            options["proxy"] = self.proxy
        else:
            self.log_message.emit("未使用代理")
        # --------------------

        # 合并用户提供的选项 (如果将来有的话)
        options.update(self.ydl_opts)

        try:
            self.log_message.emit(f"开始下载: {self.url}")
            self.log_message.emit(f"下载目录: {os.path.abspath(self.download_path)}")
            # 记录最终使用的选项，包括代理
            self.log_message.emit(f"使用选项: {options}")

            # 使用 try-finally 确保即使出错也能尝试发送 finished 信号
            download_success = False
            final_message = "下载未知状态结束"

            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    # 检查是否在初始化后就被取消了
                    if self._is_cancelled:
                        self.log_message.emit("下载在开始前被取消")
                        final_message = "下载被用户取消"
                        # finished 信号将在 finally 块中发送
                        return  # 直接退出 run 方法

                    # 这里需要处理可能的下载错误
                    try:
                        # download=True 会执行下载
                        info_dict = ydl.extract_info(self.url, download=True)

                        # 如果下载过程被取消 (通过 _is_cancelled 标志)
                        if self._is_cancelled:
                            self.log_message.emit("下载过程中被取消")
                            final_message = "下载被用户取消"
                            # finished 信号将在 finally 块中发送
                            return

                        # 如果没有被取消且没有抛出异常，认为下载（或提交给yt-dlp）成功
                        # 注意：yt-dlp 内部的完成状态由 progress_hook 处理
                        download_success = True
                        # 尝试获取最终的文件名，但这可能在合并前不可用
                        # filename = ydl.prepare_filename(info_dict) if info_dict else "未知文件"
                        final_message = (
                            f"下载任务完成 (最终状态请查看日志)"  # 消息可以更具体
                        )

                    # 特别捕捉 DownloadError
                    except yt_dlp.utils.DownloadError as e:
                        # 检查是否是因为取消操作导致的错误（虽然不完美）
                        if self._is_cancelled:
                            self.log_message.emit(
                                f"下载因取消操作而中断 (可能伴随错误: {e})"
                            )
                            final_message = "下载被用户取消"
                        else:
                            self.log_message.emit(f"yt-dlp 下载错误: {e}")
                            final_message = f"下载失败: {e}"
                        download_success = False  # 明确标记失败
                    # 捕捉其他可能的 yt-dlp 或网络相关的异常
                    except Exception as e:
                        if self._is_cancelled:
                            self.log_message.emit(
                                f"下载因取消操作而中断 (可能伴随意外错误: {e})"
                            )
                            final_message = "下载被用户取消"
                        else:
                            self.log_message.emit(f"yt-dlp 执行时发生意外错误: {e}")
                            final_message = f"意外错误: {e}"
                        download_success = False  # 明确标记失败

            # 捕捉 YoutubeDL 初始化时的错误
            except Exception as e:
                self.log_message.emit(f"初始化 YoutubeDL 时出错: {e}")
                final_message = f"初始化失败: {e}"
                download_success = False  # 明确标记失败

            finally:
                # 确保无论如何都发送 finished 信号（除非线程已被强制终止）
                # 只有在没有被取消的情况下，才根据 download_success 判断最终状态
                # 如果被取消了，总是发送 False (表示未成功完成)
                if not self._is_cancelled:
                    self.finished.emit(download_success, final_message)
                else:
                    # 如果是取消导致的结束，发送 False 和取消信息
                    self.finished.emit(False, "下载被用户取消")

        except Exception as e:
            # 捕捉 run 方法中其他未预料的错误
            self.log_message.emit(f"DownloadWorker.run 发生严重错误: {e}")
            if not self._is_cancelled:
                self.finished.emit(False, f"工作线程运行时错误: {e}")
            else:
                self.finished.emit(False, "下载被用户取消 (伴随运行时错误)")

    def cancel(self):
        """请求取消下载"""
        if not self._is_cancelled:  # 避免重复记录
            self._is_cancelled = True
            self.log_message.emit("请求取消下载...")
            # 注意：这只是设置了一个标志位。yt-dlp 本身不一定能优雅地中断所有操作。
            # progress_hook 会检查这个标志位，但网络请求可能仍在进行。

    class YtdlpLogger:
        def __init__(self, log_signal):
            self.log_signal = log_signal

        def debug(self, msg):
            # 过滤掉 yt-dlp 内部的进度更新信息，因为我们用 progress_hook
            # msg 格式通常是 '[debug] message' 或 '[download] message'
            if msg.startswith("[debug] "):
                # 可以选择性记录更详细的 debug 信息
                # self.log_signal.emit(f"DEBUG: {msg[len('[debug] '):]}")
                pass  # 默认忽略 debug 信息
            elif not msg.startswith("[download]"):  # 过滤掉下载进度信息
                self.log_signal.emit(msg)  # 记录其他非 debug, 非 download 的信息

        def warning(self, msg):
            self.log_signal.emit(f"警告: {msg}")

        def error(self, msg):
            self.log_signal.emit(f"错误: {msg}")

        # yt-dlp 的 info 方法有时也用来输出下载进度，需要过滤
        def info(self, msg):
            # 过滤掉进度条更新信息
            if not msg.startswith("[download]"):
                # 有些插件或信息会用 info 级别输出，不过滤掉 '[info]' 前缀
                self.log_signal.emit(msg)
