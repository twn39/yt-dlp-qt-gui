from unittest.mock import MagicMock, patch

import pytest

from yt_dlp_gui.database import Database
from yt_dlp_gui.models import DownloadTask
from yt_dlp_gui.scheduler import DownloadScheduler


@pytest.fixture
def temp_db(tmp_path):
    """创建临时数据库的 pytest fixture"""
    db_file = tmp_path / "test_downloads.db"
    db = Database(db_path=str(db_file))
    yield db
    db.close()


def test_scheduler_initialization(temp_db):
    """测试调度器初始化属性"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=2)
    assert scheduler.db == temp_db
    assert scheduler.max_concurrent_downloads == 2
    assert len(scheduler.workers) == 0
    assert len(scheduler.threads) == 0


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_concurrency_limit(mock_run, temp_db):
    """测试并发限制，超出最大并发数后任务自动进入等待队列"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task1 = DownloadTask(
        url="https://example.com/v1",
        save_path=".",
        format_preset="best",
    )
    task2 = DownloadTask(
        url="https://example.com/v2",
        save_path=".",
        format_preset="best",
    )

    tid1 = scheduler.add_task(task1)
    tid2 = scheduler.add_task(task2)

    assert tid1 in scheduler._active_task_ids
    assert tid2 in scheduler._waiting_queue
    task2_db = temp_db.get_task(tid2)
    assert task2_db is not None
    assert task2_db.status == "queued"
    mock_run.assert_called_once()


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_queue_progression(mock_run, temp_db):
    """测试排队任务的流转，当前任务完成后队列中的下一个任务自动启动"""
    from PySide6.QtCore import QCoreApplication

    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task1 = DownloadTask(url="https://example.com/v1", save_path=".", format_preset="best")
    task2 = DownloadTask(url="https://example.com/v2", save_path=".", format_preset="best")

    tid1 = scheduler.add_task(task1)
    tid2 = scheduler.add_task(task2)

    # 模拟任务 1 线程结束清理（由 QTimer.singleShot 异步派发下一次调度）
    scheduler._cleanup_thread(tid1)
    app = QCoreApplication.instance()
    if app is not None:
        app.processEvents()

    # 任务 2 应当被自动拉起
    assert tid2 in scheduler._active_task_ids
    assert len(scheduler._waiting_queue) == 0
    assert mock_run.call_count == 2


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_slot_filling_multi_concurrency(mock_run, temp_db):
    """测试槽位饱和填充引擎：当有多个空闲槽位时，一次调度应填满所有可用并发槽位"""
    from PySide6.QtCore import QCoreApplication

    # 最大并发设为 3
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=3)

    tasks = [
        DownloadTask(url=f"https://example.com/v{i}", save_path=".", format_preset="best")
        for i in range(5)
    ]
    tids = [scheduler.add_task(t) for t in tasks]

    # 前 3 个任务应该直接并发启动，后 2 个进入等待队列
    assert len(scheduler._active_task_ids) == 3
    assert set(tids[:3]) == scheduler._active_task_ids
    assert scheduler._waiting_queue == tids[3:]
    assert mock_run.call_count == 3

    # 当任务 1 结束并清理时，队列中的第 4 个任务应立即被填补
    scheduler._cleanup_thread(tids[0])
    app = QCoreApplication.instance()
    if app is not None:
        app.processEvents()

    assert len(scheduler._active_task_ids) == 3
    assert tids[3] in scheduler._active_task_ids
    assert scheduler._waiting_queue == [tids[4]]
    assert mock_run.call_count == 4


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_dynamic_concurrency_scaling(mock_run, temp_db):
    """测试动态并发调整：增大并发数时自动唤醒排队任务"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task1 = DownloadTask(url="https://example.com/v1", save_path=".", format_preset="best")
    task2 = DownloadTask(url="https://example.com/v2", save_path=".", format_preset="best")
    task3 = DownloadTask(url="https://example.com/v3", save_path=".", format_preset="best")

    tid1 = scheduler.add_task(task1)
    tid2 = scheduler.add_task(task2)
    tid3 = scheduler.add_task(task3)

    assert tid1 in scheduler._active_task_ids
    assert len(scheduler._active_task_ids) == 1
    assert scheduler._waiting_queue == [tid2, tid3]
    assert mock_run.call_count == 1

    # 动态将并发数从 1 提升至 3，等待队列中的 2 个任务应立即被拉起启动
    scheduler.set_max_concurrent_downloads(3)
    assert len(scheduler._active_task_ids) == 3
    assert len(scheduler._waiting_queue) == 0
    assert mock_run.call_count == 3

    # 测试非法并发数异常保护
    with pytest.raises(ValueError, match="最大并发数不能小于 1"):
        scheduler.set_max_concurrent_downloads(0)


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_stop_queued_task(mock_run, temp_db):
    """测试停止队列中正在排队的任务，任务应直接出队并标记为 cancelled"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task1 = DownloadTask(url="https://example.com/v1", save_path=".", format_preset="best")
    task2 = DownloadTask(url="https://example.com/v2", save_path=".", format_preset="best")

    scheduler.add_task(task1)
    tid2 = scheduler.add_task(task2)

    # 停止排队中的任务 2
    scheduler.stop_task(tid2)

    assert tid2 not in scheduler._waiting_queue
    task2_db = temp_db.get_task(tid2)
    assert task2_db is not None
    assert task2_db.status == "cancelled"


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_delete_task(mock_run, temp_db):
    """测试任务删除逻辑（包括排队中和运行中任务的删除处理）"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task1 = DownloadTask(url="https://example.com/v1", save_path=".", format_preset="best")
    task2 = DownloadTask(url="https://example.com/v2", save_path=".", format_preset="best")

    tid1 = scheduler.add_task(task1)
    tid2 = scheduler.add_task(task2)

    # 删除排队中的任务 2
    scheduler.delete_task(tid2)
    assert tid2 not in scheduler._waiting_queue
    assert temp_db.get_task(tid2) is None

    # 删除进行中的任务 1 (应该进入挂起删除 pending_delete，并触发 cancel)
    thread_mock = MagicMock()
    worker_mock = MagicMock()
    scheduler.threads[tid1] = thread_mock
    scheduler.workers[tid1] = worker_mock

    scheduler.delete_task(tid1)
    assert tid1 in scheduler._pending_delete_tids
    worker_mock.cancel.assert_called_once()


def test_task_impersonate_and_no_cookies_db(temp_db):
    """测试任务的浏览器伪装和禁用 Cookies 属性在数据库中的持久化"""
    task = DownloadTask(
        url="https://example.com/v1",
        save_path=".",
        format_preset="best",
        impersonate="chrome",
        no_cookies=True,
    )
    tid = temp_db.add_task(task)
    retrieved = temp_db.get_task(tid)
    assert retrieved is not None
    assert retrieved.impersonate == "chrome"
    assert retrieved.no_cookies is True


def test_task_cookie_browser_db(temp_db):
    """测试任务的从浏览器导入 Cookies 属性在数据库中的持久化"""
    task = DownloadTask(
        url="https://example.com/v2",
        save_path=".",
        format_preset="best",
        cookie_browser="chrome",
    )
    tid = temp_db.add_task(task)
    retrieved = temp_db.get_task(tid)
    assert retrieved is not None
    assert retrieved.cookie_browser == "chrome"


def test_database_concurrent_writes(tmp_path):
    """验证 Database 在高频多线程并发写入时依然稳定、不报 SQLite 锁死错误"""
    import threading

    from yt_dlp_gui.database import Database
    from yt_dlp_gui.models import DownloadTask

    db_file = tmp_path / "concurrent_test.db"
    db = Database(db_path=str(db_file))

    # 1. 初始化添加一个任务
    task_id = db.add_task(DownloadTask(url="http://x.com", save_path=".", format_preset="mp4"))

    # 2. 定义高频并发写入的工作线程
    def worker():
        for i in range(50):
            db.update_task(task_id, {"progress": i, "speed": f"{i}MB/s"})

    # 3. 开启 5 个并发线程，共提交 250 次写入
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 4. 最终验证连接关闭和数据一致性
    db.close()

    # 重新读取数据确认没损坏
    db_check = Database(db_path=str(db_file))
    task = db_check.get_task(task_id)
    assert task is not None
    assert task.progress == 49
    db_check.close()


def test_database_defaults_and_migration(tmp_path, monkeypatch):
    """测试 Database 默认路径初始化以及旧数据库结构迁移逻辑"""
    import os
    import sqlite3

    from yt_dlp_gui.database import Database

    # 1. 测试默认路径初始化
    monkeypatch.setattr(
        os.path, "expanduser", lambda path: path.replace("~", str(tmp_path / "user_home"))
    )
    db_default = Database()
    assert os.path.exists(tmp_path / "user_home" / ".yt-dlp-gui" / "downloads.db")
    db_default.close()

    # 2. 模拟旧数据库结构（没有 impersonate 和 no_cookies 字段）
    db_old_file = tmp_path / "old_downloads.db"
    conn = sqlite3.connect(str(db_old_file))
    conn.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            status TEXT DEFAULT 'pending',
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
    conn.close()

    # 3. 初始化并触发迁移
    db_migrated = Database(db_path=str(db_old_file))

    # 4. 验证迁移后列成功创建并可以进行写入 and 读取
    from yt_dlp_gui.models import DownloadTask

    task = DownloadTask(
        url="http://abc.com",
        save_path=".",
        format_preset="best",
        impersonate="chrome",
        no_cookies=True,
    )
    tid = db_migrated.add_task(task)
    retrieved = db_migrated.get_task(tid)
    assert retrieved is not None
    assert retrieved.impersonate == "chrome"
    assert retrieved.no_cookies is True

    # 5. 测试重复 close 不抛错
    db_migrated.close()
    db_migrated.close()


def test_database_exceptions(tmp_path):
    """测试 Database 异常捕获和同步/异步执行逻辑"""
    from yt_dlp_gui.database import Database

    db_file = tmp_path / "ex_test.db"
    db = Database(db_path=str(db_file))

    # 1. 验证同步异常抛出
    def raise_error(conn):
        raise ValueError("Simulated DB error")

    with pytest.raises(ValueError, match="Simulated DB error"):
        db._execute_sync(raise_error)

    # 2. 验证异步异常不抛出，但在后台被处理
    db._execute_async(raise_error)
    db._queue.join()

    # 3. 验证无更新项直接返回
    assert db.update_task(1, {}) is None

    db.close()


def test_remove_task_log_exceptions(tmp_path, monkeypatch):
    """测试日志文件删除以及异常被捕获的逻辑"""
    import os

    from yt_dlp_gui.config import get_task_log_path, remove_task_log

    monkeypatch.setattr(os.path, "expanduser", lambda path: str(tmp_path / "user_home"))
    log_path = get_task_log_path(999)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    with open(log_path, "w") as f:
        f.write("some logs")
    assert os.path.exists(log_path)

    # 成功删除
    remove_task_log(999)
    assert not os.path.exists(log_path)

    # 异常安全保护
    def mock_remove(path):
        raise OSError("Permission denied")

    monkeypatch.setattr(os, "remove", mock_remove)

    with open(log_path, "w") as f:
        f.write("some logs")

    # 应静默捕获并不会抛出 OSError
    remove_task_log(999)


@patch("yt_dlp_gui.scheduler.DownloadWorker.run")
def test_scheduler_real_run_task_thread(mock_run, temp_db, qtbot):
    """测试 Scheduler 创建实际后台 QThread 及 Worker 并发信号的场景"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=2)

    task = DownloadTask(url="http://x.com", save_path=".", format_preset="best")
    task_id = temp_db.add_task(task)
    task.id = task_id

    scheduler._run_task_thread(task)

    assert task_id in scheduler.threads
    assert task_id in scheduler.workers

    worker = scheduler.workers[task_id]

    # 1. 进度通知
    with qtbot.waitSignal(scheduler.task_progress_changed, timeout=1000) as blocker:
        worker.progress.emit(task_id, {"status": "downloading", "info_dict": {"title": "My Title"}})
    assert blocker.args[0] == task_id
    assert blocker.args[1]["status"] == "downloading"
    assert temp_db.get_task(task_id).title == "My Title"

    # 2. 日志通知
    with qtbot.waitSignal(scheduler.task_log_emitted, timeout=1000) as blocker:
        worker.log_message.emit(task_id, "my log line")
    assert blocker.args[0] == task_id
    assert blocker.args[1] == "my log line"

    # 3. 完成通知（正常成功）
    with qtbot.waitSignal(scheduler.task_finished, timeout=1000) as blocker:
        worker.finished.emit(task_id, True, "Completed successfully")
    assert blocker.args[0] == task_id
    assert blocker.args[1] is True
    assert temp_db.get_task(task_id).status == "finished"

    qtbot.waitUntil(lambda: task_id not in scheduler.threads, timeout=2000)
    scheduler.shutdown()


@patch("yt_dlp_gui.scheduler.DownloadWorker.run")
def test_scheduler_worker_finished_failure_and_cancel(mock_run, temp_db, qtbot):
    """测试 Worker 失败或者用户主动取消下载在 Scheduler 里的流转"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=2)

    # 1. 下载失败 (success = False)
    task2 = DownloadTask(url="http://x.com", save_path=".", format_preset="best")
    task2_id = temp_db.add_task(task2)
    task2.id = task2_id

    scheduler._run_task_thread(task2)
    worker2 = scheduler.workers[task2_id]

    with qtbot.waitSignal(scheduler.task_finished, timeout=1000):
        worker2.finished.emit(task2_id, False, "Some error occurred")

    qtbot.waitUntil(lambda: task2_id not in scheduler.threads, timeout=2000)
    assert temp_db.get_task(task2_id).status == "error"

    # 2. 用户取消 (success = False 且包含 用户取消 文本)
    task3 = DownloadTask(url="http://x.com", save_path=".", format_preset="best")
    task3_id = temp_db.add_task(task3)
    task3.id = task3_id

    scheduler._run_task_thread(task3)
    worker3 = scheduler.workers[task3_id]

    with qtbot.waitSignal(scheduler.task_finished, timeout=1000):
        worker3.finished.emit(task3_id, False, "用户取消下载")

    qtbot.waitUntil(lambda: task3_id not in scheduler.threads, timeout=2000)
    assert temp_db.get_task(task3_id).status == "cancelled"

    scheduler.shutdown()


def test_scheduler_state_machine_transition_guards(temp_db):
    """测试状态机守卫：阻断非法跃迁，放行合法跃迁"""
    from yt_dlp_gui.models import DownloadStatus

    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=2)

    # 1. 初始为 pending
    task = DownloadTask(url="http://guard.com", save_path=".", format_preset="best")
    tid = temp_db.add_task(task)

    # pending -> queued (合法)
    assert scheduler._transition_status(tid, DownloadStatus.QUEUED) is True
    assert temp_db.get_task(tid).status == DownloadStatus.QUEUED

    # queued -> downloading (合法)
    assert scheduler._transition_status(tid, DownloadStatus.DOWNLOADING) is True
    assert temp_db.get_task(tid).status == DownloadStatus.DOWNLOADING

    # downloading -> finished (合法)
    assert scheduler._transition_status(tid, DownloadStatus.FINISHED) is True
    assert temp_db.get_task(tid).status == DownloadStatus.FINISHED

    # finished -> merging (非法跃迁，已完成任务不可直接变更为合并中)
    assert scheduler._transition_status(tid, DownloadStatus.MERGING) is False
    # 状态保持 finished
    assert temp_db.get_task(tid).status == DownloadStatus.FINISHED

    # finished -> queued (合法，用户重试)
    assert scheduler._transition_status(tid, DownloadStatus.QUEUED) is True
    assert temp_db.get_task(tid).status == DownloadStatus.QUEUED

    # 针对不存在的 task_id，转移应安全返回 False
    assert scheduler._transition_status(99999, DownloadStatus.DOWNLOADING) is False


def test_scheduler_query_helpers(temp_db):
    """测试 is_task_running, is_task_queued, is_task_active 状态查询 Facade"""
    from unittest.mock import MagicMock

    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=2)

    task1_id = 101
    task2_id = 102
    task3_id = 103

    # task1 模拟处于线程运行中
    scheduler.threads[task1_id] = MagicMock()
    # task2 处于等待队列
    scheduler._waiting_queue.append(task2_id)

    # 验证 is_task_running
    assert scheduler.is_task_running(task1_id) is True
    assert scheduler.is_task_running(task2_id) is False
    assert scheduler.is_task_running(task3_id) is False

    # 验证 is_task_queued
    assert scheduler.is_task_queued(task1_id) is False
    assert scheduler.is_task_queued(task2_id) is True
    assert scheduler.is_task_queued(task3_id) is False

    # 验证 is_task_active (运行中或排队中)
    assert scheduler.is_task_active(task1_id) is True
    assert scheduler.is_task_active(task2_id) is True
    assert scheduler.is_task_active(task3_id) is False


def test_scheduler_start_all_and_stop_all(temp_db):
    """测试全部开始 (start_all_tasks) 与全部停止 (stop_all_tasks)"""
    from unittest.mock import MagicMock

    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=2)

    task1 = DownloadTask(url="http://1.com", save_path=".", format_preset="best")
    task2 = DownloadTask(url="http://2.com", save_path=".", format_preset="best")
    task3 = DownloadTask(url="http://3.com", save_path=".", format_preset="best")

    temp_db.add_task(task1)
    temp_db.add_task(task2)
    temp_db.add_task(task3)

    # 1. 模拟 start_all_tasks
    mock_run = MagicMock()
    scheduler._run_task_thread = mock_run

    scheduler.start_all_tasks()

    # 最大并发是 2，所以应该 2 个运行，1 个排队
    assert len(scheduler._active_task_ids) == 2
    assert len(scheduler._waiting_queue) == 1
    assert mock_run.call_count == 2

    # 2. 模拟 stop_all_tasks
    # 给运行中任务注入 mock worker
    from typing import cast

    from yt_dlp_gui.worker import DownloadWorker

    worker_mocks = {tid: MagicMock() for tid in scheduler._active_task_ids}
    scheduler.workers = cast(dict[int, DownloadWorker], worker_mocks)

    scheduler.stop_all_tasks()

    # 排队队列应已被清空
    assert len(scheduler._waiting_queue) == 0
    # 所有运行中 worker 均被调用 cancel
    for w in worker_mocks.values():
        w.cancel.assert_called_once()


def test_task_ratelimit_db(temp_db):
    """测试任务的限速属性在数据库中的持久化和读取"""
    task = DownloadTask(
        url="https://example.com/ratelimit",
        save_path=".",
        format_preset="best",
        ratelimit="5M",
    )
    tid = temp_db.add_task(task)
    retrieved = temp_db.get_task(tid)
    assert retrieved is not None
    assert retrieved.ratelimit == "5M"
