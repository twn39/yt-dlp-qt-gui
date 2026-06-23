"""数据库访问层

使用单一持久 SQLite 连接 + WAL 日志模式 + 队列工作线程，
彻底解决多线程高频写入下的连接开销和数据库锁竞争 (database is locked) 问题。
"""

import os
import queue
import sqlite3
import sys
import threading
from typing import Any, Callable, Optional

from .models import DownloadTask


class DbTask:
    """封装数据库任务以及用于返回结果的线程安全队列"""

    def __init__(self, func: Callable[[sqlite3.Connection], Any], sync: bool = True) -> None:
        self.func = func
        self.sync = sync
        # 结果队列，对于同步任务是必要的，异步任务无需创建以减少开销
        self.result_queue = queue.Queue[tuple[bool, Any]](maxsize=1) if sync else None


class Database:
    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            config_dir = os.path.expanduser("~/.yt-dlp-gui")
            os.makedirs(config_dir, exist_ok=True)
            self.db_path = os.path.join(config_dir, "downloads.db")
        else:
            self.db_path = db_path

        # 任务队列，用于传递 DbTask 或用于停止的 None (毒丸)
        self._queue = queue.Queue[Optional[DbTask]]()

        # 启动后台持久化数据库工作线程
        self._worker_thread = threading.Thread(target=self._db_worker, daemon=True)
        self._worker_thread.start()

        self._init_db()

    def _db_worker(self) -> None:
        """后台数据库工作线程的主循环，保证所有 SQL 操作都在单线程内顺序执行"""
        # 在此后台线程中开启连接，确保 check_same_thread 安全
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # WAL 模式与同步级别优化
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        while True:
            task = self._queue.get()
            if task is None:  # 收到毒丸，准备关闭
                self._queue.task_done()
                break

            try:
                # 执行具体 closure 并返回结果
                result = task.func(conn)
                if task.sync and task.result_queue is not None:
                    task.result_queue.put((True, result))
            except Exception as e:
                if task.sync and task.result_queue is not None:
                    task.result_queue.put((False, e))
                else:
                    # 异步任务出错时，记录日志到 stderr 以免程序崩溃
                    print(f"Database background write error: {e}", file=sys.stderr)
            finally:
                self._queue.task_done()

        conn.close()

    def _execute_sync(self, func: Callable[[sqlite3.Connection], Any]) -> Any:
        """同步执行任务：向队列投递任务并阻塞等待后台线程返回结果"""
        task = DbTask(func, sync=True)
        self._queue.put(task)
        assert task.result_queue is not None
        success, result = task.result_queue.get()
        if not success:
            raise result
        return result

    def _execute_async(self, func: Callable[[sqlite3.Connection], Any]) -> None:
        """异步执行任务：向队列投递任务，直接返回不阻塞调用方（火及忘记模式）"""
        task = DbTask(func, sync=False)
        self._queue.put(task)

    def close(self) -> None:
        """显式关闭数据库连接"""
        self._queue.put(None)
        self._worker_thread.join(timeout=3)

    def _init_db(self) -> None:
        def init_func(conn: sqlite3.Connection) -> None:
            conn.execute("""
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
            conn.commit()

        self._execute_sync(init_func)

    def add_task(self, task: DownloadTask) -> int:
        def add_func(conn: sqlite3.Connection) -> int:
            query = """
                INSERT INTO tasks (
                    url, title, status, save_path, format_preset, proxy,
                    concurrent_fragments, write_subs, download_playlist,
                    playlist_items, playlist_random, max_downloads
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                task.url,
                task.title or "正在解析...",
                "pending",
                task.save_path,
                task.format_preset,
                task.proxy,
                task.concurrent_fragments,
                task.write_subs,
                task.download_playlist,
                task.playlist_items,
                task.playlist_random,
                task.max_downloads,
            )
            cursor = conn.execute(query, params)
            conn.commit()
            assert cursor.lastrowid is not None
            return cursor.lastrowid

        return self._execute_sync(add_func)

    def update_task(self, task_id: int, updates: dict[str, Any]) -> None:
        if not updates:
            return

        def update_func(conn: sqlite3.Connection) -> None:
            columns = [f"{k} = ?" for k in updates.keys()]
            query = f"UPDATE tasks SET {', '.join(columns)} WHERE id = ?"
            params = list(updates.values()) + [task_id]
            conn.execute(query, params)
            conn.commit()

        self._execute_async(update_func)

    def delete_task(self, task_id: int) -> None:
        def delete_func(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

        self._execute_async(delete_func)

    # 允许排序的列白名单，防止 SQL 注入
    _SORT_COLS = frozenset({"created_at", "title", "status", "progress"})
    _SORT_DIRS = frozenset({"ASC", "DESC"})

    def get_all_tasks(
        self,
        sort_col: str = "created_at",
        sort_dir: str = "DESC",
    ) -> list[DownloadTask]:
        """返回所有任务，支持 DB 层排序（代替 QTableWidget 的列排序）。

        Args:
            sort_col: 排序列，必须在 _SORT_COLS 白名单中。
            sort_dir: 排序方向，"ASC" 或 "DESC"。
        """
        col = sort_col if sort_col in self._SORT_COLS else "created_at"
        direction = sort_dir if sort_dir in self._SORT_DIRS else "DESC"

        def get_all_func(conn: sqlite3.Connection) -> list[DownloadTask]:
            cursor = conn.execute(f"SELECT * FROM tasks ORDER BY {col} {direction}")  # noqa: S608
            return [DownloadTask.from_dict(dict(row)) for row in cursor.fetchall()]

        return self._execute_sync(get_all_func)

    def get_task(self, task_id: int) -> Optional[DownloadTask]:
        def get_func(conn: sqlite3.Connection) -> Optional[DownloadTask]:
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return DownloadTask.from_dict(dict(row)) if row else None

        return self._execute_sync(get_func)
