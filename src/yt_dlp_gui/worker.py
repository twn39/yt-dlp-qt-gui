import os
from typing import Any
from PySide6.QtCore import Signal, QObject, Slot
import yt_dlp
from yt_dlp.utils import DownloadCancelled, DownloadError
from .config import DEFAULT_FORMAT, OUTPUT_TEMPLATE, NO_PROGRESS


class DownloadWorker(QObject):
    """下载工作线程，负责执行 yt-dlp 下载任务"""

    progress = Signal(dict)  # 发送进度信息字典
    finished = Signal(bool, str)  # 发送完成状态 (成功/失败, 消息/文件路径)
    log_message = Signal(str)  # 发送普通日志消息

    def __init__(
        self,
        url: str,
        download_path: str = ".",
        format_preset: str | None = None,
        ydl_opts: dict[str, Any] | None = None,
        proxy: str | None = None,
        concurrent_fragments: int | None = None,
        write_subs: bool = False,
        download_playlist: bool = False,
        playlist_items: str | None = None,
        playlist_random: bool = False,
        max_downloads: int | None = None,
    ) -> None:
        """
        初始化下载工作器

        Args:
            url: 要下载的视频 URL
            download_path: 下载保存路径
            format_preset: 格式预设 (使用 config.py 中的格式字符串)
            ydl_opts: 额外的 yt-dlp 选项
            proxy: HTTP/SOCKS 代理地址
            concurrent_fragments: 并发下载片段数
            write_subs: 是否下载字幕
            download_playlist: 是否下载播放列表
            playlist_items: 播放列表项目范围 (例如: "1-5,7,10")
            playlist_random: 是否随机顺序下载播放列表
            max_downloads: 最大下载数
        """
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.format_preset = format_preset or DEFAULT_FORMAT
        self.ydl_opts = ydl_opts if ydl_opts else {}
        self.proxy = proxy
        self.concurrent_fragments = concurrent_fragments
        self.write_subs = write_subs
        self.download_playlist = download_playlist
        self.playlist_items = playlist_items
        self.playlist_random = playlist_random
        self.max_downloads = max_downloads
        self._is_cancelled = False

    def _progress_hook(self, d: dict[str, Any]) -> None:
        """yt-dlp 进度钩子函数"""
        # 检查取消标志 - 通过抛出异常强制中断 yt-dlp
        if self._is_cancelled:
            self.log_message.emit("正在中断下载...")
            raise DownloadCancelled("用户取消下载")

        if d["status"] == "downloading":
            self.progress.emit(d)
        elif d["status"] == "finished":
            if "filename" in d:
                filename = d.get('filename', '')
                self.log_message.emit(
                    f"文件下载完成: {os.path.basename(filename)}"
                )
                # 只有当下载的是视频文件（非字幕文件）时才发送合并状态
                # 字幕文件通常以 .srt, .vtt, .ass 等结尾
                if filename and not any(filename.endswith(ext) for ext in ['.srt', '.vtt', '.ass', '.ssa', '.json']):
                    self.progress.emit({"status": "merging"})
            else:
                self.log_message.emit(
                    f"处理步骤完成: {d.get('info_dict', {}).get('title', '未知任务')}"
                )
        elif d["status"] == "error":
            self.log_message.emit(f"下载错误: {d.get('filename', '未知文件')}")

    @Slot()
    def run(self) -> None:
        """执行下载"""
        if not self.url:
            self.finished.emit(False, "URL 不能为空")
            return

        # 使用配置文件中的常量
        options: Any = {
            "format": self.format_preset,
            "outtmpl": os.path.join(self.download_path, OUTPUT_TEMPLATE),
            "progress_hooks": [self._progress_hook],
            "noplaylist": not self.download_playlist,  # 根据用户选择决定是否下载播放列表
            "logger": self.YtdlpLogger(self.log_message),
            "noprogress": NO_PROGRESS,
            "merge_output_format": "mp4",  # 强制合并为 mp4 格式，确保兼容性
            "allow_unplayable_formats": False,
            "extract_flat": False,
            "remote_components": ["ejs:github"],  # 启用远程组件以解决 JS challenge (n-sig)
            "nocheckcertificate": True,  # 禁用 SSL 证书验证，解决部分环境下的 SSL 错误
            "socket_timeout": 30,  # 设置超时时间，防止连接僵死
            "retries": 10,  # 增加重试次数
            "fragment_retries": 10,
        }

        # 添加代理设置
        if self.proxy:
            self.log_message.emit(f"使用代理: {self.proxy}")
            options["proxy"] = self.proxy
        else:
            self.log_message.emit("未使用代理")

        # 添加并发片段设置
        if self.concurrent_fragments is not None:
            self.log_message.emit(f"并发片段数: {self.concurrent_fragments}")
            options["concurrent_fragments"] = self.concurrent_fragments

        # 添加字幕下载设置
        if self.write_subs:
            self.log_message.emit("启用字幕下载")
            options["writesubtitles"] = True
            options["subtitleslangs"] = ["all"]  # 下载所有可用语言的字幕
        else:
            self.log_message.emit("不下载字幕")

        # 添加播放列表下载设置
        if self.download_playlist:
            self.log_message.emit("启用播放列表下载")
            # 添加播放列表项目范围
            if self.playlist_items:
                self.log_message.emit(f"播放列表项目范围: {self.playlist_items}")
                options["playlist_items"] = self.playlist_items
            # 添加随机顺序选项
            if self.playlist_random:
                self.log_message.emit("启用随机顺序下载")
                options["playlist_random"] = True
            # 添加最大下载数限制
            if self.max_downloads is not None:
                self.log_message.emit(f"最大下载数: {self.max_downloads}")
                options["max_downloads"] = self.max_downloads
        else:
            self.log_message.emit("不下载播放列表")

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
                        return

                    try:
                        info_dict = ydl.extract_info(self.url, download=True)

                        if self._is_cancelled:
                            self.log_message.emit("下载过程中被取消")
                            final_message = "下载被用户取消"
                            return

                        download_success = True
                        final_message = "下载任务完成"

                    # 捕捉用户取消异常
                    except DownloadCancelled:
                        self.log_message.emit("下载已被用户取消")
                        final_message = "下载被用户取消"
                        download_success = False

                    # 捕捉 DownloadError
                    except DownloadError as e:
                        if self._is_cancelled:
                            self.log_message.emit("下载因取消操作而中断")
                            final_message = "下载被用户取消"
                        else:
                            self.log_message.emit(f"yt-dlp 下载错误: {e}")
                            final_message = f"下载失败: {e}"
                        download_success = False

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

    def cancel(self) -> None:
        """请求取消下载"""
        if not self._is_cancelled:
            self._is_cancelled = True
            self.log_message.emit("请求取消下载...")

    class YtdlpLogger:
        """yt-dlp 日志记录器，过滤并转发日志消息到 Qt 信号"""

        def __init__(self, log_signal: Signal) -> None:
            self.log_signal = log_signal

        def debug(self, msg: str) -> None:
            # 过滤掉 yt-dlp 内部的进度更新信息
            if msg.startswith("[debug] "):
                pass  # 默认忽略 debug 信息
            elif not msg.startswith("[download]"):
                self.log_signal.emit(msg)

        def warning(self, msg: str) -> None:
            self.log_signal.emit(f"警告: {msg}")

        def error(self, msg: str) -> None:
            self.log_signal.emit(f"错误: {msg}")

        def info(self, msg: str) -> None:
            # 过滤掉进度条更新信息
            if not msg.startswith("[download]"):
                self.log_signal.emit(msg)

