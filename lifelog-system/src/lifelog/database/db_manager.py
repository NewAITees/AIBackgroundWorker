"""
Database manager for lifelog-system.

Design: Thread-local connections with WAL mode optimization.
See: doc/design/database_design.md
"""

import sqlite3
import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Optional, List
from pathlib import Path

from .schema import CREATE_TABLES_SQL, MIGRATION_ADD_EVENTS_SQL, get_pragma_settings


logger = logging.getLogger(__name__)

# 明示的にdatetimeを文字列へアダプトして、sqlite3のデフォルト警告を避ける
sqlite3.register_adapter(datetime, lambda d: d.isoformat())


class DatabaseManager:
    """
    SQLiteデータベース管理クラス.

    特徴:
    - WALモードで高頻度書き込みに最適化
    - スレッドローカル接続でスレッドセーフ
    - バルク挿入対応
    """

    def __init__(self, db_path: str = "lifelog.db") -> None:
        """
        初期化.

        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path
        self._local = threading.local()
        # データベースの初期化（新規・既存問わず）
        self._init_database()
        # 既存DBの場合はマイグレーションも実行
        if Path(db_path).exists():
            self.migrate_if_needed()

    def _init_database(self) -> None:
        """データベースの初期化とPRAGMA設定."""
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)

        # PRAGMA設定
        for pragma in get_pragma_settings():
            conn.execute(pragma)

        # テーブル作成
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()
        conn.close()

        logger.info(f"Database initialized: {self.db_path}")

    def migrate_if_needed(self) -> None:
        """
        既存DBへのマイグレーションを実行.
        system_eventsテーブルとビューが存在しない場合に追加する.
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        for pragma in get_pragma_settings():
            conn.execute(pragma)
        cursor = conn.cursor()

        try:
            # system_eventsテーブルの存在確認
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='system_events'
                """
            )
            has_events_table = cursor.fetchone() is not None

            # unified_timelineビューの存在確認
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='view' AND name='unified_timeline'
                """
            )
            has_unified_view = cursor.fetchone() is not None

            # daily_event_summaryビューの存在確認
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='view' AND name='daily_event_summary'
                """
            )
            has_summary_view = cursor.fetchone() is not None

            # マイグレーションが必要な場合
            if not has_events_table or not has_unified_view or not has_summary_view:
                logger.info("Migrating database: adding system_events table and views")
                conn.executescript(MIGRATION_ADD_EVENTS_SQL)
                conn.commit()
                logger.info("Database migration completed")
            else:
                logger.debug("Database is up to date, no migration needed")

        except Exception as e:
            conn.rollback()
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """
        スレッドローカル接続を取得.

        Returns:
            SQLite接続オブジェクト
        """
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            for pragma in get_pragma_settings():
                self._local.conn.execute(pragma)
        return self._local.conn

    def _get_or_create_app_in_tx(
        self, cursor: sqlite3.Cursor, process_name: str, process_path_hash: str
    ) -> int:
        """既存トランザクション内でapp_idを取得/作成する。"""
        cursor.execute(
            """
            SELECT app_id FROM apps
            WHERE process_name = ? AND process_path_hash = ?
        """,
            (process_name, process_path_hash),
        )
        row = cursor.fetchone()
        now = datetime.now()
        if row:
            cursor.execute(
                """
                UPDATE apps SET last_seen = ? WHERE app_id = ?
            """,
                (now, row["app_id"]),
            )
            return row["app_id"]

        cursor.execute(
            """
            INSERT INTO apps (process_name, process_path_hash, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
        """,
            (process_name, process_path_hash, now, now),
        )
        return cursor.lastrowid

    @staticmethod
    def _is_lock_error(exc: Exception) -> bool:
        return isinstance(exc, sqlite3.OperationalError) and "database is locked" in str(exc).lower()

    def _run_with_lock_retry(self, fn, retries: int = 5, base_sleep: float = 0.2):
        for attempt in range(retries + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                if not self._is_lock_error(exc) or attempt >= retries:
                    raise
                time.sleep(base_sleep * (2**attempt))

    def get_or_create_app(self, process_name: str, process_path_hash: str) -> int:
        """
        アプリケーションマスタからIDを取得（なければ作成）.

        Args:
            process_name: プロセス名
            process_path_hash: プロセスパスのハッシュ

        Returns:
            app_id
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        app_id = self._get_or_create_app_in_tx(cursor, process_name, process_path_hash)
        conn.commit()
        return app_id

    def bulk_insert_intervals(self, intervals: list[dict[str, Any]]) -> None:
        """
        区間データのバルク挿入.

        Args:
            intervals: 区間データのリスト
        """
        if not intervals:
            return

        def _op() -> None:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            records = []
            for interval in intervals:
                # app_id を取得または作成（同一トランザクション内）
                app_id = self._get_or_create_app_in_tx(
                    cursor,
                    interval["process_name"], interval["process_path_hash"]
                )

                records.append(
                    (
                        interval["start_ts"],
                        interval["end_ts"],
                        app_id,
                        interval["window_hash"],
                        interval.get("domain"),
                        interval["is_idle"],
                    )
                )

            # バルクINSERT
            cursor.executemany(
                """
                INSERT INTO activity_intervals
                (start_ts, end_ts, app_id, window_hash, domain, is_idle)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                records,
            )

            conn.commit()
            logger.debug(f"Bulk inserted {len(records)} intervals")

        try:
            self._run_with_lock_retry(_op)
        except Exception as e:
            conn = self._get_connection()
            conn.rollback()
            logger.error(f"Bulk insert failed: {e}")
            raise

    def save_health_snapshot(self, metrics: dict[str, Any]) -> None:
        """
        ヘルスメトリクスの保存.

        Args:
            metrics: メトリクスデータ
        """
        def _op() -> None:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO health_snapshots
                (ts, cpu_percent, mem_mb, queue_depth,
                 collection_delay_p50, collection_delay_p95,
                 dropped_events, db_write_time_p95)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics["timestamp"],
                    metrics["cpu_percent"],
                    metrics["mem_mb"],
                    metrics["queue_depth"],
                    metrics["collection_delay_p50"],
                    metrics["collection_delay_p95"],
                    metrics["dropped_events"],
                    metrics["db_write_time_p95"],
                ),
            )
            conn.commit()

        self._run_with_lock_retry(_op)

    def cleanup_old_data(
        self, retention_days: int = 30, event_retention_days: Optional[int] = None
    ) -> None:
        """
        古いデータの削除.

        Args:
            retention_days: アクティビティデータの保持日数（デフォルト: 30日）
            event_retention_days: イベントデータの保持日数（Noneの場合はretention_daysと同じ）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=retention_days)
        health_cutoff = datetime.now() - timedelta(days=7)
        event_cutoff = datetime.now() - timedelta(
            days=event_retention_days if event_retention_days is not None else retention_days
        )

        cursor.execute(
            """
            DELETE FROM activity_intervals WHERE start_ts < ?
        """,
            (cutoff_date,),
        )

        cursor.execute(
            """
            DELETE FROM health_snapshots WHERE ts < ?
        """,
            (health_cutoff,),
        )

        # system_eventsテーブルのクリーンアップ（テーブルが存在する場合のみ）
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='system_events'
            """
        )
        if cursor.fetchone():
            cursor.execute(
                """
                DELETE FROM system_events WHERE event_timestamp < ?
            """,
                (event_cutoff,),
            )
            deleted_events = cursor.rowcount
            if deleted_events > 0:
                logger.info(
                    f"Cleaned up {deleted_events} system events older than {event_retention_days or retention_days} days"
                )

        # 使用されなくなったアプリの削除
        cursor.execute(
            """
            DELETE FROM apps
            WHERE app_id NOT IN (SELECT DISTINCT app_id FROM activity_intervals)
        """
        )

        conn.commit()
        logger.info(f"Cleaned up data older than {retention_days} days")

    def bulk_insert_events(self, events: list[dict[str, Any]]) -> None:
        """
        イベントデータのバルク挿入.

        Args:
            events: イベントデータのリスト
        """
        if not events:
            return

        def _op() -> None:
            conn = self._get_connection()
            cursor = conn.cursor()
            records = []
            for event in events:
                records.append(
                    (
                        event["event_timestamp"],
                        event["event_type"],
                        event["severity"],
                        event["source"],
                        event.get("category"),
                        event.get("event_id"),
                        event.get("message"),
                        event.get("message_hash"),
                        event.get("raw_data_json"),
                        event.get("process_name"),
                        event.get("user_name"),
                        event.get("machine_name", ""),
                    )
                )

            # バルクINSERT
            cursor.executemany(
                """
                INSERT INTO system_events
                (event_timestamp, event_type, severity, source, category,
                 event_id, message, message_hash, raw_data_json,
                 process_name, user_name, machine_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                records,
            )

            conn.commit()
            logger.debug(f"Bulk inserted {len(records)} events")

        try:
            self._run_with_lock_retry(_op)
        except Exception as e:
            conn = self._get_connection()
            conn.rollback()
            logger.error(f"Bulk insert events failed: {e}")
            raise

    def get_events_by_date_range(
        self,
        start: datetime,
        end: datetime,
        event_types: Optional[List[str]] = None,
        min_severity: Optional[int] = None,
    ) -> List[dict[str, Any]]:
        """
        指定期間のイベントを取得.

        Args:
            start: 開始時刻
            end: 終了時刻
            event_types: イベントタイプのフィルタ（Noneの場合はすべて）
            min_severity: 最小重要度（Noneの場合はすべて）

        Returns:
            イベントデータのリスト
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT * FROM system_events
            WHERE event_timestamp >= ? AND event_timestamp < ?
        """
        params = [start, end]

        if event_types:
            placeholders = ",".join(["?"] * len(event_types))
            query += f" AND event_type IN ({placeholders})"
            params.extend(event_types)

        if min_severity is not None:
            query += " AND severity >= ?"
            params.append(min_severity)

        query += " ORDER BY event_timestamp DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_events_with_activity(
        self,
        start: datetime,
        end: datetime,
    ) -> List[dict[str, Any]]:
        """
        activity_intervalsと統合したイベントデータを取得.

        Args:
            start: 開始時刻
            end: 終了時刻

        Returns:
            統合時系列データのリスト
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM unified_timeline
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp DESC
        """,
            (start, end),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        """データベース接続をクローズ."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            delattr(self._local, "conn")
