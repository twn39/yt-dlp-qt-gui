import os
from typing import Any
from PySide6.QtCore import Signal, SignalInstance, QObject, Slot
import yt_dlp
from yt_dlp.utils import DownloadCancelled
from .config import DEFAULT_FORMAT, OUTPUT_TEMPLATE, NO_PROGRESS


class DownloadWorker(QObject):
    """下载工作线程，负责执行 yt-dlp 下载任务"""

    progress = Signal(int, dict)  # 发送 (task_id, 进度信息字典)
    finished = Signal(int, bool, str)  # 发送 (task_id, 成功/失败, 消息/文件路径)
    log_message = Signal(int, str)  # 发送 (task_id, 普通日志消息)

    def __init__(
        self,
        task_id: int,
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
            task_id: 数据库中的任务 ID
            url: 要下载的视频 URL
            ...
        """
        super().__init__()
        self.task_id = task_id
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
        # 检查取消标志
        if self._is_cancelled:
            self.log_message.emit(self.task_id, "正在中断下载...")
            raise DownloadCancelled("用户取消下载")

        if d["status"] == "downloading":
            self.progress.emit(self.task_id, d)
        elif d["status"] == "finished":
            if "filename" in d:
                filename = d.get("filename", "")
                self.log_message.emit(self.task_id, f"文件下载完成: {os.path.basename(filename)}")
                if filename and not any(
                    filename.endswith(ext) for ext in [".srt", ".vtt", ".ass", ".ssa", ".json"]
                ):
                    self.progress.emit(self.task_id, {"status": "merging"})
            else:
                self.log_message.emit(
                    self.task_id, f"处理步骤完成: {d.get('info_dict', {}).get('title', '未知任务')}"
                )
        elif d["status"] == "error":
            self.log_message.emit(self.task_id, f"下载错误: {d.get('filename', '未知文件')}")

    @Slot()
    def run(self) -> None:
        """执行下载"""
        if not self.url:
            self.finished.emit(self.task_id, False, "URL 不能为空")
            return

        # 使用配置文件中的常量
        base_options: Any = {
            "format": self.format_preset,
            "outtmpl": os.path.join(self.download_path, OUTPUT_TEMPLATE),
            "progress_hooks": [self._progress_hook],
            "noplaylist": not self.download_playlist,
            "logger": self.YtdlpLogger(self.task_id, self.log_message),
            "noprogress": NO_PROGRESS,
            "merge_output_format": "mp4",
            "allow_unplayable_formats": False,
            "extract_flat": False,
            "nocheckcertificate": True,
            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
        }

        # ... (proxy, concurrent_fragments, etc. logic stays same but logging uses task_id)
        if self.proxy:
            self.log_message.emit(self.task_id, f"使用代理: {self.proxy}")
            base_options["proxy"] = self.proxy

        if self.concurrent_fragments is not None:
            base_options["concurrent_fragments"] = self.concurrent_fragments

        if self.write_subs:
            base_options["writesubtitles"] = True
            base_options["subtitleslangs"] = ["all"]

        if self.download_playlist:
            if self.playlist_items:
                base_options["playlist_items"] = self.playlist_items
            if self.playlist_random:
                base_options["playlist_random"] = True
            if self.max_downloads is not None:
                base_options["max_downloads"] = self.max_downloads

        base_options.update(self.ydl_opts)

        try:
            with yt_dlp.YoutubeDL(base_options) as ydl:
                ydl.extract_info(self.url, download=True)

            if self._is_cancelled:
                 self.finished.emit(self.task_id, False, "用户取消")
            else:
                 self.finished.emit(self.task_id, True, "完成")
        except DownloadCancelled:
            self.finished.emit(self.task_id, False, "已取消")
        except Exception as e:
            self.log_message.emit(self.task_id, f"下载出错: {e}")
            self.finished.emit(self.task_id, False, str(e))

    def cancel(self) -> None:
        """请求取消下载"""
        if not self._is_cancelled:
            self._is_cancelled = True
            self.log_message.emit(self.task_id, "请求取消下载...")

    class YtdlpLogger:
        """yt-dlp 日志记录器，过滤并转发日志消息到 Qt 信号"""

        def __init__(self, task_id: int, log_signal: SignalInstance) -> None:
            self.task_id = task_id
            self.log_signal = log_signal

        def debug(self, msg: str) -> None:
            if not msg.startswith("[debug] ") and not msg.startswith("[download]"):
                self.log_signal.emit(self.task_id, msg)

        def warning(self, msg: str) -> None:
            self.log_signal.emit(self.task_id, f"警告: {msg}")

        def error(self, msg: str) -> None:
            self.log_signal.emit(self.task_id, f"错误: {msg}")

        def info(self, msg: str) -> None:
            if not msg.startswith("[download]"):
                self.log_signal.emit(self.task_id, msg)
