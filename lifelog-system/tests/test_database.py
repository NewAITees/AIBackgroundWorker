"""
Database tests for lifelog-system.
"""

import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.lifelog.database.db_manager import DatabaseManager


@pytest.fixture
def db_manager():
    """テスト用のインメモリDBマネージャーを作成."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    manager = DatabaseManager(db_path)
    yield manager

    # クリーンアップ
    manager.close()
    Path(db_path).unlink(missing_ok=True)


def test_database_initialization(db_manager):
    """データベース初期化のテスト."""
    conn = db_manager._get_connection()
    cursor = conn.cursor()

    # テーブルが存在するか確認
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "apps" in tables
    assert "activity_intervals" in tables
    assert "health_snapshots" in tables
    assert "system_events" in tables

    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = {row[0] for row in cursor.fetchall()}
    assert "unified_timeline" in views
    assert "daily_event_summary" in views


def test_get_or_create_app(db_manager):
    """アプリマスタのCRUDテスト."""
    # 新規作成
    app_id1 = db_manager.get_or_create_app("chrome.exe", "hash123")
    assert app_id1 > 0

    # 同じアプリは同じIDが返る
    app_id2 = db_manager.get_or_create_app("chrome.exe", "hash123")
    assert app_id1 == app_id2

    # 異なるアプリは異なるIDが返る
    app_id3 = db_manager.get_or_create_app("firefox.exe", "hash456")
    assert app_id3 != app_id1


def test_bulk_insert_intervals(db_manager):
    """バルク挿入のテスト."""
    now = datetime.now()

    intervals = [
        {
            "start_ts": now,
            "end_ts": now,
            "process_name": "test.exe",
            "process_path_hash": "hash_test",
            "window_hash": "title_hash_1",
            "domain": None,
            "is_idle": 0,
        },
        {
            "start_ts": now,
            "end_ts": now,
            "process_name": "test2.exe",
            "process_path_hash": "hash_test2",
            "window_hash": "title_hash_2",
            "domain": "example.com",
            "is_idle": 1,
        },
    ]

    db_manager.bulk_insert_intervals(intervals)

    # 挿入確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activity_intervals")
    count = cursor.fetchone()[0]

    assert count == 2

    # データ内容確認
    cursor.execute("SELECT window_hash, domain, is_idle FROM activity_intervals")
    rows = cursor.fetchall()

    assert rows[0][0] == "title_hash_1"
    assert rows[0][1] is None
    assert rows[0][2] == 0

    assert rows[1][0] == "title_hash_2"
    assert rows[1][1] == "example.com"
    assert rows[1][2] == 1


def test_events_roundtrip(db_manager):
    """system_eventsのCRUDとビューの存在確認."""
    now = datetime.now()
    events = [
        {
            "event_timestamp": now,
            "event_type": "error",
            "severity": 80,
            "source": "linux_syslog",
            "category": "system",
            "event_id": 1001,
            "message": "kernel panic",
            "message_hash": "hash",
            "raw_data_json": "{}",
            "process_name": "kernel",
            "user_name": None,
            "machine_name": "test-machine",
        }
    ]

    db_manager.bulk_insert_events(events)

    fetched = db_manager.get_events_by_date_range(
        now - timedelta(minutes=1), now + timedelta(minutes=1)
    )
    assert len(fetched) == 1
    assert fetched[0]["event_type"] == "error"
    assert fetched[0]["severity"] == 80


def test_save_health_snapshot(db_manager):
    """ヘルススナップショット保存のテスト."""
    metrics = {
        "timestamp": datetime.now(),
        "cpu_percent": 15.5,
        "mem_mb": 50.2,
        "queue_depth": 10,
        "collection_delay_p50": 0.5,
        "collection_delay_p95": 1.2,
        "dropped_events": 0,
        "db_write_time_p95": 25.0,
    }

    db_manager.save_health_snapshot(metrics)

    # 保存確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM health_snapshots")
    count = cursor.fetchone()[0]

    assert count == 1

    # データ内容確認
    cursor.execute("SELECT cpu_percent, mem_mb, queue_depth FROM health_snapshots")
    row = cursor.fetchone()

    assert row[0] == 15.5
    assert row[1] == 50.2
    assert row[2] == 10


def test_cleanup_old_data(db_manager):
    """古いデータ削除のテスト."""
    # テストデータ挿入
    from datetime import timedelta

    old_time = datetime.now() - timedelta(days=40)
    recent_time = datetime.now()

    intervals = [
        {
            "start_ts": old_time,
            "end_ts": old_time,
            "process_name": "old.exe",
            "process_path_hash": "hash_old",
            "window_hash": "title_old",
            "domain": None,
            "is_idle": 0,
        },
        {
            "start_ts": recent_time,
            "end_ts": recent_time,
            "process_name": "recent.exe",
            "process_path_hash": "hash_recent",
            "window_hash": "title_recent",
            "domain": None,
            "is_idle": 0,
        },
    ]

    db_manager.bulk_insert_intervals(intervals)

    # 古いイベントと最近のイベントを追加
    old_event_time = datetime.now() - timedelta(days=40)
    recent_event_time = datetime.now()
    db_manager.bulk_insert_events([
        {
            "event_timestamp": old_event_time,
            "event_type": "error",
            "severity": 80,
            "source": "test",
            "category": "system",
            "message": "old event",
            "machine_name": "test",
        },
        {
            "event_timestamp": recent_event_time,
            "event_type": "info",
            "severity": 50,
            "source": "test",
            "category": "system",
            "message": "recent event",
            "machine_name": "test",
        },
    ])

    # クリーンアップ実行（30日保持）
    db_manager.cleanup_old_data(retention_days=30)

    # 確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activity_intervals")
    count = cursor.fetchone()[0]

    # 古いデータは削除され、最近のデータのみ残る
    assert count == 1

    # イベントも同様にクリーンアップされているか確認
    cursor.execute("SELECT COUNT(*) FROM system_events")
    event_count = cursor.fetchone()[0]
    assert event_count == 1  # 最近のイベントのみ残る


def test_migration_adds_events_table_and_views(tmp_path):
    """既存DBへのマイグレーション機能のテスト."""
    # 既存DBを作成（system_eventsなし）
    db_path = tmp_path / "existing.db"
    conn = sqlite3.connect(str(db_path))
    
    # 基本的なテーブルのみ作成
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apps (
            app_id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_name TEXT NOT NULL,
            process_path_hash TEXT NOT NULL,
            first_seen DATETIME NOT NULL,
            last_seen DATETIME NOT NULL,
            UNIQUE(process_name, process_path_hash)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_intervals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_ts DATETIME NOT NULL,
            end_ts DATETIME NOT NULL,
            app_id INTEGER NOT NULL,
            window_hash TEXT NOT NULL,
            domain TEXT,
            is_idle INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(app_id) REFERENCES apps(app_id)
        )
    """)
    conn.commit()
    conn.close()

    # マイグレーション実行
    manager = DatabaseManager(str(db_path))
    
    # system_eventsテーブルとビューが追加されたか確認
    conn = manager._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_events'")
    assert cursor.fetchone() is not None, "system_events table should exist"
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='unified_timeline'")
    assert cursor.fetchone() is not None, "unified_timeline view should exist"
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='daily_event_summary'")
    assert cursor.fetchone() is not None, "daily_event_summary view should exist"
    
    manager.close()
    Path(db_path).unlink(missing_ok=True)
