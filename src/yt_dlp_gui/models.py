from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class DownloadTask:
    url: str
    save_path: str
    format_preset: str
    id: Optional[int] = None
    title: Optional[str] = "正在解析..."
    status: str = "pending"
    progress: int = 0
    speed: Optional[str] = "--"
    eta: Optional[str] = "--"
    proxy: Optional[str] = None
    concurrent_fragments: Optional[int] = None
    write_subs: bool = False
    download_playlist: bool = False
    playlist_items: Optional[str] = None
    playlist_random: bool = False
    max_downloads: Optional[int] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadTask":
        # Handle concurrent_fragments validation
        raw_cf = data.get("concurrent_fragments")
        concurrent_fragments = None
        if raw_cf is not None and str(raw_cf).isdigit():
            concurrent_fragments = int(raw_cf)

        # Handle max_downloads validation
        raw_md = data.get("max_downloads")
        max_downloads = None
        if raw_md is not None and str(raw_md).isdigit():
            max_downloads = int(raw_md)

        # In sqlite, boolean fields are often stored as 0/1. Force bool conversion.
        return cls(
            id=data.get("id"),
            url=data.get("url", ""),
            title=data.get("title") if data.get("title") is not None else "正在解析...",
            status=data.get("status", "pending"),
            progress=int(data.get("progress") or 0),
            speed=data.get("speed") if data.get("speed") is not None else "--",
            eta=data.get("eta") if data.get("eta") is not None else "--",
            save_path=data.get("save_path", ""),
            format_preset=data.get("format_preset", ""),
            proxy=data.get("proxy") or None,  # Treat empty string as None
            concurrent_fragments=concurrent_fragments,
            write_subs=bool(data.get("write_subs", False)),
            download_playlist=bool(data.get("download_playlist", False)),
            playlist_items=data.get("playlist_items") or None,  # Treat empty string as None
            playlist_random=bool(data.get("playlist_random", False)),
            max_downloads=max_downloads,
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
