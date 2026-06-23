from unittest.mock import MagicMock, patch

import pytest

from yt_dlp_gui.database import Database
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

    task_data1 = {
        "url": "https://example.com/v1",
        "save_path": ".",
        "format_preset": "best",
    }
    task_data2 = {
        "url": "https://example.com/v2",
        "save_path": ".",
        "format_preset": "best",
    }

    tid1 = scheduler.add_task(task_data1)
    tid2 = scheduler.add_task(task_data2)

    assert tid1 in scheduler._active_task_ids
    assert tid2 in scheduler._waiting_queue
    assert temp_db.get_task(tid2)["status"] == "queued"
    mock_run.assert_called_once()


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_queue_progression(mock_run, temp_db):
    """测试排队任务的流转，当前任务完成后队列中的下一个任务自动启动"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task_data1 = {"url": "https://example.com/v1", "save_path": ".", "format_preset": "best"}
    task_data2 = {"url": "https://example.com/v2", "save_path": ".", "format_preset": "best"}

    tid1 = scheduler.add_task(task_data1)
    tid2 = scheduler.add_task(task_data2)

    # 模拟任务 1 线程结束清理
    scheduler._cleanup_thread(tid1)

    # 任务 2 应当被自动拉起
    assert tid2 in scheduler._active_task_ids
    assert len(scheduler._waiting_queue) == 0
    assert mock_run.call_count == 2


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_stop_queued_task(mock_run, temp_db):
    """测试停止队列中正在排队的任务，任务应直接出队并标记为 cancelled"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task_data1 = {"url": "https://example.com/v1", "save_path": ".", "format_preset": "best"}
    task_data2 = {"url": "https://example.com/v2", "save_path": ".", "format_preset": "best"}

    scheduler.add_task(task_data1)
    tid2 = scheduler.add_task(task_data2)

    # 停止排队中的任务 2
    scheduler.stop_task(tid2)

    assert tid2 not in scheduler._waiting_queue
    assert temp_db.get_task(tid2)["status"] == "cancelled"


@patch("yt_dlp_gui.scheduler.DownloadScheduler._run_task_thread")
def test_scheduler_delete_task(mock_run, temp_db):
    """测试任务删除逻辑（包括排队中和运行中任务的删除处理）"""
    scheduler = DownloadScheduler(temp_db, max_concurrent_downloads=1)

    task_data1 = {"url": "https://example.com/v1", "save_path": ".", "format_preset": "best"}
    task_data2 = {"url": "https://example.com/v2", "save_path": ".", "format_preset": "best"}

    tid1 = scheduler.add_task(task_data1)
    tid2 = scheduler.add_task(task_data2)

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
