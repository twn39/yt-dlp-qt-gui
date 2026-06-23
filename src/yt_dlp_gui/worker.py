import os
from typing import Any

import yt_dlp
from PySide6.QtCore import QObject, Signal, Slot
from yt_dlp.utils import DownloadCancelled

from .config import DEFAULT_FORMAT, NO_PROGRESS, OUTPUT_TEMPLATE, get_task_log_path


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
        impersonate: str | None = None,
        no_cookies: bool = False,
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
        self.impersonate = impersonate
        self.no_cookies = no_cookies
        self._is_cancelled = False
        self._log_file = None

    def _write_log(self, msg: str) -> None:
        """写日志到文件并发出信号"""
        if self._log_file:
            try:
                self._log_file.write(msg + "\n")
            except Exception:
                pass
        self.log_message.emit(self.task_id, msg)

    def _progress_hook(self, d: dict[str, Any]) -> None:
        """yt-dlp 进度钩子函数"""
        # 检查取消标志
        if self._is_cancelled:
            self._write_log("正在中断下载...")
            raise DownloadCancelled("用户取消下载")

        if d["status"] == "downloading":
            self.progress.emit(self.task_id, d)
        elif d["status"] == "finished":
            if "filename" in d:
                filename = d.get("filename", "")
                self._write_log(f"文件下载完成: {os.path.basename(filename)}")
                if filename and not any(
                    filename.endswith(ext) for ext in [".srt", ".vtt", ".ass", ".ssa", ".json"]
                ):
                    self.progress.emit(self.task_id, {"status": "merging"})
            else:
                self._write_log(f"处理步骤完成: {d.get('info_dict', {}).get('title', '未知任务')}")
        elif d["status"] == "error":
            self._write_log(f"下载错误: {d.get('filename', '未知文件')}")

    @Slot()
    def run(self) -> None:
        """执行下载"""
        if not self.url:
            self.finished.emit(self.task_id, False, "URL 不能为空")
            return

        # 使用行缓冲 (buffering=1) 打开日志文件，确保实时写入且性能最佳
        log_path = get_task_log_path(self.task_id)
        try:
            self._log_file = open(log_path, "w", encoding="utf-8", buffering=1)
        except Exception:
            pass

        try:
            # 使用配置文件中的常量
            base_options: Any = {
                "format": self.format_preset,
                "outtmpl": os.path.join(self.download_path, OUTPUT_TEMPLATE),
                "progress_hooks": [self._progress_hook],
                "noplaylist": not self.download_playlist,
                "logger": self.YtdlpLogger(self.task_id, self._write_log),
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
                self._write_log(f"使用代理: {self.proxy}")
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

            if self.impersonate:
                self._write_log(f"浏览器伪装: {self.impersonate}")
                try:
                    from yt_dlp.networking.impersonate import ImpersonateTarget

                    base_options["impersonate"] = ImpersonateTarget.from_str(self.impersonate)
                except (ImportError, AttributeError):
                    base_options["impersonate"] = self.impersonate

            if self.no_cookies:
                self._write_log("已启用无 Cookies 模式")
                base_options["no_cookies"] = True

            base_options.update(self.ydl_opts)

            with yt_dlp.YoutubeDL(base_options) as ydl:
                ydl.extract_info(self.url, download=True)

            if self._is_cancelled:
                self.finished.emit(self.task_id, False, "用户取消")
            else:
                self.finished.emit(self.task_id, True, "完成")
        except DownloadCancelled:
            self.finished.emit(self.task_id, False, "已取消")
        except Exception as e:
            self._write_log(f"下载出错: {e}")
            self.finished.emit(self.task_id, False, str(e))
        finally:
            if self._log_file:
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None

    def cancel(self) -> None:
        """请求取消下载"""
        if not self._is_cancelled:
            self._is_cancelled = True
            self._write_log("请求取消下载...")

    class YtdlpLogger:
        """yt-dlp 日志记录器，过滤并转发日志消息"""

        def __init__(self, task_id: int, write_func) -> None:
            self.task_id = task_id
            self.write_func = write_func

        def debug(self, msg: str) -> None:
            if not msg.startswith("[debug] ") and not msg.startswith("[download]"):
                self.write_func(msg)

        def warning(self, msg: str) -> None:
            self.write_func(f"警告: {msg}")

        def error(self, msg: str) -> None:
            self.write_func(f"错误: {msg}")

        def info(self, msg: str) -> None:
            if not msg.startswith("[download]"):
                self.write_func(msg)
