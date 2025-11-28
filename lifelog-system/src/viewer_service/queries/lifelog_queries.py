"""Lifelog database query functions.

既存のlifelog.dbからデータを読み取り、DTOに変換する。
読み取り専用でWALロックの影響を避ける。
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models import (
    LifelogData,
    AppUsage,
    ActivityInterval,
    HealthMetrics,
)


def _connect_lifelog_db(db_path: Path) -> sqlite3.Connection:
    """ライフログDBに接続（読み取り専用）."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # 読み取り専用モードを明示
    conn.execute("PRAGMA query_only = ON")
    return conn


def get_daily_summary(db_path: Path, date: str) -> LifelogData:
    """指定日の日次サマリーを取得.

    Args:
        db_path: lifelog.dbのパス
        date: 日付文字列 (YYYY-MM-DD)

    Returns:
        LifelogData: 日次サマリー
    """
    conn = _connect_lifelog_db(db_path)
    cursor = conn.cursor()

    # 日付範囲（SQLiteのDATETIME形式に合わせてスペースセパレーター使用）
    start_dt = datetime.strptime(date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=1)
    start_ts_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_ts_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 総アクティブ時間とアイドル時間
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN is_idle = 0 THEN duration_seconds ELSE 0 END) as active_seconds,
            SUM(CASE WHEN is_idle = 1 THEN duration_seconds ELSE 0 END) as idle_seconds
        FROM activity_intervals
        WHERE start_ts >= ? AND start_ts < ?
        """,
        (start_ts_str, end_ts_str),
    )
    row = cursor.fetchone()
    total_active = row["active_seconds"] or 0
    total_idle = row["idle_seconds"] or 0

    # トップアプリ
    cursor.execute(
        """
        SELECT
            a.process_name as process,
            SUM(i.duration_seconds) as total_seconds
        FROM activity_intervals i
        JOIN apps a ON i.app_id = a.app_id
        WHERE i.start_ts >= ? AND i.start_ts < ? AND i.is_idle = 0
        GROUP BY a.process_name
        ORDER BY total_seconds DESC
        LIMIT 10
        """,
        (start_ts_str, end_ts_str),
    )
    top_apps = [
        AppUsage(
            process=row["process"],
            total_seconds=row["total_seconds"],
            percentage=(
                round(row["total_seconds"] / total_active * 100, 1)
                if total_active > 0
                else 0
            ),
        )
        for row in cursor.fetchall()
    ]

    # 直近のインターバル（最新10件）
    cursor.execute(
        """
        SELECT
            i.start_ts,
            a.process_name,
            i.domain,
            i.duration_seconds,
            i.is_idle
        FROM activity_intervals i
        JOIN apps a ON i.app_id = a.app_id
        WHERE i.start_ts >= ? AND i.start_ts < ?
        ORDER BY i.start_ts DESC
        LIMIT 10
        """,
        (start_ts_str, end_ts_str),
    )
    recent_intervals = [
        ActivityInterval(
            timestamp=datetime.fromisoformat(row["start_ts"]),
            process=row["process_name"],
            domain=row["domain"],
            duration=row["duration_seconds"],
            is_idle=bool(row["is_idle"]),
        )
        for row in cursor.fetchall()
    ]

    # 最新のヘルスメトリクス
    cursor.execute(
        """
        SELECT ts, cpu_percent, mem_mb, collection_delay_p95
        FROM health_snapshots
        WHERE ts >= ? AND ts < ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (start_ts_str, end_ts_str),
    )
    health_row = cursor.fetchone()
    health_latest = None
    if health_row:
        health_latest = HealthMetrics(
            timestamp=datetime.fromisoformat(health_row["ts"]),
            cpu_percent=health_row["cpu_percent"],
            memory_mb=health_row["mem_mb"],
            delay_p95=health_row["collection_delay_p95"],
        )

    conn.close()

    return LifelogData(
        date=date,
        total_active_seconds=total_active,
        total_idle_seconds=total_idle,
        top_apps=top_apps,
        recent_intervals=recent_intervals,
        health_latest=health_latest,
    )


def get_recent_timeline(db_path: Path, hours: int = 6) -> List[ActivityInterval]:
    """直近N時間のタイムラインを取得.

    Args:
        db_path: lifelog.dbのパス
        hours: 遡る時間数

    Returns:
        List[ActivityInterval]: アクティビティインターバルリスト
    """
    conn = _connect_lifelog_db(db_path)
    cursor = conn.cursor()

    cutoff_ts_str = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        SELECT
            i.start_ts,
            a.process_name,
            i.domain,
            i.duration_seconds,
            i.is_idle
        FROM activity_intervals i
        JOIN apps a ON i.app_id = a.app_id
        WHERE i.start_ts >= ?
        ORDER BY i.start_ts DESC
        LIMIT 100
        """,
        (cutoff_ts_str,),
    )

    intervals = [
        ActivityInterval(
            timestamp=datetime.fromisoformat(row["start_ts"]),
            process=row["process_name"],
            domain=row["domain"],
            duration=row["duration_seconds"],
            is_idle=bool(row["is_idle"]),
        )
        for row in cursor.fetchall()
    ]

    conn.close()
    return intervals


def get_health_metrics(db_path: Path, hours: int = 24) -> List[HealthMetrics]:
    """直近N時間のヘルスメトリクスを取得.

    Args:
        db_path: lifelog.dbのパス
        hours: 遡る時間数

    Returns:
        List[HealthMetrics]: ヘルスメトリクスリスト
    """
    conn = _connect_lifelog_db(db_path)
    cursor = conn.cursor()

    cutoff_ts_str = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        SELECT ts, cpu_percent, mem_mb, collection_delay_p95
        FROM health_snapshots
        WHERE ts >= ?
        ORDER BY ts DESC
        LIMIT 100
        """,
        (cutoff_ts_str,),
    )

    metrics = [
        HealthMetrics(
            timestamp=datetime.fromisoformat(row["ts"]),
            cpu_percent=row["cpu_percent"],
            memory_mb=row["mem_mb"],
            delay_p95=row["collection_delay_p95"],
        )
        for row in cursor.fetchall()
    ]

    conn.close()
    return metrics
