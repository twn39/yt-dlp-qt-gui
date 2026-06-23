from dataclasses import asdict, dataclass
from typing import Any, Optional

import qtawesome as qta
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QIcon


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
    impersonate: Optional[str] = None
    no_cookies: bool = False
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
            impersonate=data.get("impersonate") or None,
            no_cookies=bool(data.get("no_cookies", False)),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskTableModel(QAbstractTableModel):
    """数据模型，用于在 QTableView 中展示和管理 DownloadTask 列表"""

    def __init__(self, tasks: list[DownloadTask] | None = None) -> None:
        super().__init__()
        self._tasks = tasks or []
        self._icon_cache: dict[tuple[str, str], QIcon] = {}

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._tasks)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 5

    def _get_cached_icon(self, name: str, color: str) -> QIcon:
        key = (name, color)
        if key not in self._icon_cache:
            self._icon_cache[key] = qta.icon(name, color=color)
        return self._icon_cache[key]

    def _get_status_icon(self, status: str) -> QIcon:
        if status == "downloading":
            return self._get_cached_icon("fa5s.download", "#FFFFFF")
        elif status == "finished":
            return self._get_cached_icon("fa5s.check-circle", "#4CAF50")
        elif status == "error":
            return self._get_cached_icon("fa5s.exclamation-circle", "#FFFFFF")
        elif status == "merging":
            return self._get_cached_icon("fa5s.layer-group", "#FFFFFF")
        elif status == "cancelled":
            return self._get_cached_icon("fa5s.stop-circle", "#FFFFFF")
        return self._get_cached_icon("fa5s.clock", "#FFFFFF")

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None

        task = self._tasks[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return task.title or task.url
            elif col == 1:
                return task.status
            elif col == 2:
                return task.progress
            elif col == 3:
                return task.speed or "--"
            elif col == 4:
                return task.eta or "--"

        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 0:
                icon_name = "fa5s.file-video" if task.status == "finished" else "fa5s.video"
                icon_color = "#4CAF50" if task.status == "finished" else "#FFFFFF"
                return self._get_cached_icon(icon_name, icon_color)
            elif col == 1:
                return self._get_status_icon(task.status)

        elif role == Qt.ItemDataRole.UserRole:
            return task.id

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (1, 3, 4):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = ["名称", "状态", "进度", "速度", "剩余时间"]
            if 0 <= section < len(headers):
                return headers[section]
        return None

    def find_row_by_id(self, task_id: int) -> int | None:
        for idx, task in enumerate(self._tasks):
            if task.id == task_id:
                return idx
        return None

    def add_task(self, task: DownloadTask) -> None:
        row = len(self._tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tasks.append(task)
        self.endInsertRows()

    def remove_task(self, task_id: int) -> None:
        row = self.find_row_by_id(task_id)
        if row is not None:
            self.beginRemoveRows(QModelIndex(), row, row)
            self._tasks.pop(row)
            self.endRemoveRows()

    def update_task_data(self, task_id: int, updates: dict[str, Any]) -> None:
        row = self.find_row_by_id(task_id)
        if row is None:
            return
        task = self._tasks[row]
        for key, value in updates.items():
            setattr(task, key, value)

        start_index = self.index(row, 0)
        end_index = self.index(row, 4)
        self.dataChanged.emit(
            start_index, end_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.DecorationRole]
        )

    def set_tasks(self, tasks: list[DownloadTask]) -> None:
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()
