"""数据库访问层

使用单一持久 SQLite 连接 + WAL 日志模式 + 线程锁，
解决高频写入（进度更新约 1 次/秒/任务）下的连接开销和线程安全问题。

设计要点：
- WAL 模式：读写并发，读操作无需锁
- 写操作（add/update/delete）使用 threading.Lock 互斥
- 读操作（get/get_all）直接执行，WAL 模式下天然并发安全
- close() 供 MainWindow.closeEvent 显式调用
"""

import os
import sqlite3
import threading
from typing import Any, Optional


class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            config_dir = os.path.expanduser("~/.yt-dlp-gui")
            os.makedirs(config_dir, exist_ok=True)
            self.db_path = os.path.join(config_dir, "downloads.db")
        else:
            self.db_path = db_path

        # 单一持久连接，check_same_thread=False 允许主线程和 Worker 线程共享
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # WAL 模式：写入不阻塞读取，大幅提升高频更新场景性能
        self._conn.execute("PRAGMA journal_mode=WAL")
        # WAL 模式下 NORMAL 级别安全且比 FULL 快
        self._conn.execute("PRAGMA synchronous=NORMAL")

        # 写操作互斥锁（读操作在 WAL 模式下无需锁）
        self._write_lock = threading.Lock()

        self._init_db()

    def close(self) -> None:
        """显式关闭数据库连接（供 MainWindow.closeEvent 调用）"""
        self._conn.close()

    def _init_db(self) -> None:
        with self._write_lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    status TEXT DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    speed TEXT,
                    eta TEXT,
                    save_path TEXT,
                    format_preset TEXT,
                    proxy TEXT,
                    concurrent_fragments INTEGER,
                    write_subs BOOLEAN,
                    download_playlist BOOLEAN,
                    playlist_items TEXT,
                    playlist_random BOOLEAN,
                    max_downloads INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._conn.commit()

    def add_task(self, task_data: dict[str, Any]) -> int:
        query = """
            INSERT INTO tasks (
                url, title, status, save_path, format_preset, proxy,
                concurrent_fragments, write_subs, download_playlist,
                playlist_items, playlist_random, max_downloads
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            task_data["url"],
            task_data.get("title", "正在解析..."),
            "pending",
            task_data["save_path"],
            task_data["format_preset"],
            task_data.get("proxy"),
            task_data.get("concurrent_fragments"),
            task_data.get("write_subs", False),
            task_data.get("download_playlist", False),
            task_data.get("playlist_items"),
            task_data.get("playlist_random", False),
            task_data.get("max_downloads"),
        )
        with self._write_lock:
            cursor = self._conn.execute(query, params)
            self._conn.commit()
            assert cursor.lastrowid is not None  # INSERT 成功后 lastrowid 必不为 None
            return cursor.lastrowid

    def update_task(self, task_id: int, updates: dict[str, Any]) -> None:
        if not updates:
            return
        columns = [f"{k} = ?" for k in updates.keys()]
        query = f"UPDATE tasks SET {', '.join(columns)} WHERE id = ?"
        params = list(updates.values()) + [task_id]
        with self._write_lock:
            self._conn.execute(query, params)
            self._conn.commit()

    def delete_task(self, task_id: int) -> None:
        with self._write_lock:
            self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._conn.commit()

    # 允许排序的列白名单，防止 SQL 注入
    _SORT_COLS = frozenset({"created_at", "title", "status", "progress"})
    _SORT_DIRS = frozenset({"ASC", "DESC"})

    def get_all_tasks(
        self,
        sort_col: str = "created_at",
        sort_dir: str = "DESC",
    ) -> list[dict[str, Any]]:
        """返回所有任务，支持 DB 层排序（代替 QTableWidget 的列排序）。

        Args:
            sort_col: 排序列，必须在 _SORT_COLS 白名单中。
            sort_dir: 排序方向，"ASC" 或 "DESC"。
        """
        # 防御性校验：不在白名单内回退到默认值
        col = sort_col if sort_col in self._SORT_COLS else "created_at"
        direction = sort_dir if sort_dir in self._SORT_DIRS else "DESC"
        # 读操作：WAL 模式下与写操作并发安全，无需加锁
        cursor = self._conn.execute(f"SELECT * FROM tasks ORDER BY {col} {direction}")  # noqa: S608
        return [dict(row) for row in cursor.fetchall()]

    def get_task(self, task_id: int) -> Optional[dict[str, Any]]:
        cursor = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
