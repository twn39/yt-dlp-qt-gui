import sqlite3
import os
from typing import Any, List, Dict

class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            config_dir = os.path.expanduser("~/.yt-dlp-gui")
            os.makedirs(config_dir, exist_ok=True)
            self.db_path = os.path.join(config_dir, "downloads.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
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

    def add_task(self, task_data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO tasks (
                url, title, status, save_path, format_preset, proxy,
                concurrent_fragments, write_subs, download_playlist,
                playlist_items, playlist_random, max_downloads
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            task_data['url'],
            task_data.get('title', '正在解析...'),
            'pending',
            task_data['save_path'],
            task_data['format_preset'],
            task_data.get('proxy'),
            task_data.get('concurrent_fragments'),
            task_data.get('write_subs', False),
            task_data.get('download_playlist', False),
            task_data.get('playlist_items'),
            task_data.get('playlist_random', False),
            task_data.get('max_downloads')
        )
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def update_task(self, task_id: int, updates: Dict[str, Any]):
        if not updates:
            return

        columns = [f"{k} = ?" for k in updates.keys()]
        query = f"UPDATE tasks SET {', '.join(columns)} WHERE id = ?"
        params = list(updates.values()) + [task_id]

        with self._get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

    def delete_task(self, task_id: int):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_task(self, task_id: int) -> Dict[str, Any]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
