import os
from typing import Any
from PySide6.QtCore import Signal, SignalInstance, QObject, Slot
import yt_dlp
from yt_dlp.utils import DownloadCancelled
from .config import DEFAULT_FORMAT, OUTPUT_TEMPLATE, NO_PROGRESS


class DownloadWorker(QObject):
    """下载工作线程，负责执行 yt-dlp 下载任务"""

    progress = Signal(dict)  # 发送进度信息字典
    finished = Signal(bool, str)  # 发送完成状态 (成功/失败, 消息/文件路径)
    log_message = Signal(str)  # 发送普通日志消息

    def __init__(
        self,
        url: str | list[str],
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
            url: 要下载的视频 URL 或 URL 列表
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
        if isinstance(url, str):
            self.urls = [url]
        else:
            self.urls = url
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
                filename = d.get("filename", "")
                self.log_message.emit(f"文件下载完成: {os.path.basename(filename)}")
                # 只有当下载的是视频文件（非字幕文件）时才发送合并状态
                if filename and not any(
                    filename.endswith(ext) for ext in [".srt", ".vtt", ".ass", ".ssa", ".json"]
                ):
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
        if not self.urls:
            self.finished.emit(False, "URL 列表不能为空")
            return

        # 使用配置文件中的常量
        base_options: Any = {
            "format": self.format_preset,
            "outtmpl": os.path.join(self.download_path, OUTPUT_TEMPLATE),
            "progress_hooks": [self._progress_hook],
            "noplaylist": not self.download_playlist,
            "logger": self.YtdlpLogger(self.log_message),
            "noprogress": NO_PROGRESS,
            "merge_output_format": "mp4",
            "allow_unplayable_formats": False,
            "extract_flat": False,
            "remote_components": ["ejs:github"],
            "nocheckcertificate": True,
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
        }

        # 添加代理设置
        if self.proxy:
            self.log_message.emit(f"使用代理: {self.proxy}")
            base_options["proxy"] = self.proxy
        else:
            self.log_message.emit("未使用代理")

        # 添加并发片段设置
        if self.concurrent_fragments is not None:
            self.log_message.emit(f"并发片段数: {self.concurrent_fragments}")
            base_options["concurrent_fragments"] = self.concurrent_fragments

        # 添加字幕下载设置
        if self.write_subs:
            self.log_message.emit("启用字幕下载")
            base_options["writesubtitles"] = True
            base_options["subtitleslangs"] = ["all"]
        else:
            self.log_message.emit("不下载字幕")

        # 添加播放列表下载设置
        if self.download_playlist:
            self.log_message.emit("启用播放列表下载")
            if self.playlist_items:
                self.log_message.emit(f"播放列表项目范围: {self.playlist_items}")
                base_options["playlist_items"] = self.playlist_items
            if self.playlist_random:
                self.log_message.emit("启用随机顺序下载")
                base_options["playlist_random"] = True
            if self.max_downloads is not None:
                self.log_message.emit(f"最大下载数: {self.max_downloads}")
                base_options["max_downloads"] = self.max_downloads
        else:
            self.log_message.emit("不下载播放列表")

        base_options.update(self.ydl_opts)

        total_urls = len(self.urls)
        success_count = 0
        error_messages = []

        self.log_message.emit(f"开始批量下载任务，共 {total_urls} 个链接")
        self.log_message.emit(f"下载目录: {os.path.abspath(self.download_path)}")

        for i, url in enumerate(self.urls, 1):
            if self._is_cancelled:
                self.log_message.emit("批量下载任务已被用户取消")
                break

            self.log_message.emit(f"[{i}/{total_urls}] 正在处理: {url}")

            try:
                with yt_dlp.YoutubeDL(base_options) as ydl:
                    ydl.extract_info(url, download=True)
                    success_count += 1
            except DownloadCancelled:
                self.log_message.emit(f"[{i}/{total_urls}] 已取消")
                break
            except Exception as e:
                self.log_message.emit(f"[{i}/{total_urls}] 下载出错: {e}")
                error_messages.append(f"URL {url}: {e}")

        final_success = success_count == total_urls
        if self._is_cancelled:
            self.finished.emit(False, f"已取消。完成了 {success_count}/{total_urls}")
        elif final_success:
            self.finished.emit(True, f"全部成功！共完成 {success_count} 个任务")
        else:
            self.finished.emit(
                False, f"任务结束。成功: {success_count}, 失败: {len(error_messages)}"
            )

    def cancel(self) -> None:
        """请求取消下载"""
        if not self._is_cancelled:
            self._is_cancelled = True
            self.log_message.emit("请求取消下载...")

    class YtdlpLogger:
        """yt-dlp 日志记录器，过滤并转发日志消息到 Qt 信号"""

        def __init__(self, log_signal: SignalInstance) -> None:
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
