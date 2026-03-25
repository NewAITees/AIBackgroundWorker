"""
SQLite共通ユーティリティ

全リポジトリで共通のロック再試行ロジックとPRAGMA設定を提供する。
"""

import logging
import sqlite3
import time

logger = logging.getLogger(__name__)


def apply_wal_pragmas(conn: sqlite3.Connection) -> None:
    """WALモード用の基本PRAGMA設定を適用する。"""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")


class SqliteLockRetryMixin:
    """
    SQLiteのdatabase is lockedエラーを指数バックオフで再試行するMixin。

    使用方法:
        class MyRepository(SqliteLockRetryMixin):
            def write_data(self, data):
                self._run_with_lock_retry(lambda: self._do_write(data))
    """

    @staticmethod
    def _is_lock_error(exc: Exception) -> bool:
        return (
            isinstance(exc, sqlite3.OperationalError) and "database is locked" in str(exc).lower()
        )

    def _run_with_lock_retry(self, fn, retries: int = 5, base_sleep: float = 0.2):
        """
        database is locked 発生時に指数バックオフで再試行する。

        Args:
            fn: 実行する関数
            retries: 最大再試行回数
            base_sleep: 初回待機秒数（以降は2倍ずつ増加）
        """
        for attempt in range(retries + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                if not self._is_lock_error(exc) or attempt >= retries:
                    raise
                logger.warning(
                    "Database lock detected, retrying (%s/%s): %s",
                    attempt + 1,
                    retries,
                    exc,
                )
                time.sleep(base_sleep * (2**attempt))
