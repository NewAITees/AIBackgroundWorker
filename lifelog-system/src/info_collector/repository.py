"""
情報収集データのリポジトリ層

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/models.py - データモデル
- src/info_collector/collectors/ - データ収集器
- src/info_collector/repositories/ - ドメイン別操作ミックスイン

クラス構成（ミックスイン）:
- ArticleMixin  : collected_info / info_summaries の CRUD
- AnalysisMixin : article_analysis / deep_research の操作
- ReportMixin   : reports の操作
- FeedbackMixin : article_feedback / article_feedback_events の操作
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from src.common.db_mixin import SqliteLockRetryMixin, apply_wal_pragmas

from .repositories.analysis_mixin import AnalysisMixin
from .repositories.article_mixin import ArticleMixin
from .repositories.feedback_mixin import FeedbackMixin
from .repositories.report_mixin import ReportMixin


class InfoCollectorRepository(
    ArticleMixin,
    AnalysisMixin,
    ReportMixin,
    FeedbackMixin,
    SqliteLockRetryMixin,
):
    """情報収集データのCRUD操作を提供するリポジトリ。

    各ドメインの操作はミックスインに委譲する。
    このクラスはスキーマ管理（テーブル作成・マイグレーション）のみを担う。
    """

    def __init__(self, db_path: str = "data/ai_secretary.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        DB接続を取得するコンテキストマネージャ.
        競合時の `database is locked` を避けるため timeout/busy_timeout を長めに設定する。
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        apply_wal_pragmas(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self) -> None:
        """テーブル初期化（存在しない場合のみ作成）"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collected_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content TEXT,
                    snippet TEXT,
                    published_at TEXT,
                    fetched_at TEXT NOT NULL,
                    source_name TEXT,
                    metadata_json TEXT,
                    UNIQUE(source_type, url)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_info_source_type
                ON collected_info(source_type)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_info_fetched_at
                ON collected_info(fetched_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_info_published_at
                ON collected_info(published_at DESC)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS info_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    source_info_ids TEXT,
                    created_at TEXT NOT NULL,
                    query TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_summary_created_at
                ON info_summaries(created_at DESC)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS article_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL UNIQUE,
                    importance_score REAL,
                    relevance_score REAL,
                    llm_importance_score REAL,
                    llm_relevance_score REAL,
                    source_bonus REAL,
                    category_bonus REAL,
                    category TEXT,
                    keywords TEXT,
                    summary TEXT,
                    model TEXT,
                    analyzed_at TEXT NOT NULL,
                    FOREIGN KEY(article_id) REFERENCES collected_info(id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_scores
                ON article_analysis(importance_score DESC, relevance_score DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_date
                ON article_analysis(analyzed_at DESC)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deep_research (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL UNIQUE,
                    search_query TEXT NOT NULL,
                    search_results TEXT NOT NULL,
                    synthesized_content TEXT,
                    sources TEXT,
                    researched_at TEXT NOT NULL,
                    FOREIGN KEY(article_id) REFERENCES collected_info(id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_research_date
                ON deep_research(researched_at DESC)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    article_count INTEGER,
                    category TEXT,
                    article_ids_hash TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS article_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL UNIQUE REFERENCES collected_info(id),
                    feedback_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_feedback_article_id
                ON article_feedback(article_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS article_feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL REFERENCES collected_info(id),
                    event_type TEXT NOT NULL,
                    sentiment TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_feedback_events_article_id
                ON article_feedback_events(article_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_feedback_events_created_at
                ON article_feedback_events(created_at DESC)
                """
            )

            self._migrate_schema(conn)

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_date
                ON reports(report_date DESC)
                """
            )
            try:
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_reports_hash
                    ON reports(article_ids_hash)
                    """
                )
            except sqlite3.OperationalError:
                # カラムがない既存DBの場合に備えて無視（_migrate_schemaが後続で追加する）
                pass

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """
        既存DBで不足しているカラムを追加する軽量マイグレーション.
        安全にALTER TABLEを試行し、存在していれば無視する。
        """
        cursor = conn.cursor()

        def has_column(table: str, column: str) -> bool:
            cursor.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cursor.fetchall())

        # reports.article_ids_hash がなければ追加
        if not has_column("reports", "article_ids_hash"):
            try:
                conn.execute("ALTER TABLE reports ADD COLUMN article_ids_hash TEXT")
            except sqlite3.OperationalError:
                pass

        # reports.source_article_id がなければ追加（記事単位の重複チェック用）
        if not has_column("reports", "source_article_id"):
            try:
                conn.execute("ALTER TABLE reports ADD COLUMN source_article_id INTEGER")
            except sqlite3.OperationalError:
                pass

        # article_analysis の判断理由カラムを追加
        for col in (
            "importance_reason",
            "relevance_reason",
            "llm_importance_score",
            "llm_relevance_score",
            "source_bonus",
            "category_bonus",
        ):
            if not has_column("article_analysis", col):
                col_type = "TEXT" if col.endswith("_reason") else "REAL"
                try:
                    conn.execute(f"ALTER TABLE article_analysis ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass

        # article_feedback の状態管理カラムを追加
        for col, definition in [
            ("sentiment", "TEXT"),
            ("report_status", "TEXT NOT NULL DEFAULT 'none'"),
            ("report_entry_id", "TEXT"),
            ("updated_at", "TEXT"),
        ]:
            if not has_column("article_feedback", col):
                try:
                    conn.execute(f"ALTER TABLE article_feedback ADD COLUMN {col} {definition}")
                except sqlite3.OperationalError:
                    pass

        # 旧 feedback_type から新状態カラムへ移行
        if has_column("article_feedback", "feedback_type"):
            conn.execute(
                """
                UPDATE article_feedback
                SET sentiment = CASE
                        WHEN sentiment IS NOT NULL THEN sentiment
                        WHEN feedback_type = 'positive' THEN 'positive'
                        WHEN feedback_type = 'negative' THEN 'negative'
                        WHEN feedback_type = 'report_requested' THEN 'positive'
                        ELSE NULL
                    END,
                    report_status = CASE
                        WHEN report_status IS NOT NULL AND report_status <> '' THEN report_status
                        WHEN feedback_type = 'report_requested' THEN 'requested'
                        ELSE 'none'
                    END,
                    updated_at = COALESCE(updated_at, created_at, ?)
                """,
                (datetime.now().isoformat(),),
            )

        # article_feedback_events がなければ作成
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS article_feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES collected_info(id),
                event_type TEXT NOT NULL,
                sentiment TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feedback_events_article_id
            ON article_feedback_events(article_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feedback_events_created_at
            ON article_feedback_events(created_at DESC)
            """
        )
        self._backfill_feedback_events(conn)

    def _backfill_feedback_events(self, conn: sqlite3.Connection) -> None:
        """既存 article_feedback から履歴イベントを最低限復元する。"""
        cursor = conn.cursor()
        feedback_count = cursor.execute("SELECT COUNT(*) FROM article_feedback").fetchone()[0]
        if feedback_count == 0:
            return

        event_count = cursor.execute("SELECT COUNT(*) FROM article_feedback_events").fetchone()[0]
        if event_count > 0:
            return

        cursor.execute(
            """
            SELECT article_id, sentiment, report_status, created_at, updated_at
            FROM article_feedback
            ORDER BY COALESCE(updated_at, created_at, ?) ASC, article_id ASC
            """,
            (datetime.now().isoformat(),),
        )
        rows = cursor.fetchall()
        for article_id, sentiment, report_status, created_at, updated_at in rows:
            event_time = updated_at or created_at or datetime.now().isoformat()
            if sentiment == "positive":
                conn.execute(
                    """
                    INSERT INTO article_feedback_events (article_id, event_type, sentiment, created_at)
                    VALUES (?, 'feedback_positive', 'positive', ?)
                    """,
                    (article_id, event_time),
                )
            elif sentiment == "negative":
                conn.execute(
                    """
                    INSERT INTO article_feedback_events (article_id, event_type, sentiment, created_at)
                    VALUES (?, 'feedback_negative', 'negative', ?)
                    """,
                    (article_id, event_time),
                )

            if report_status in {"requested", "running", "done", "failed"}:
                conn.execute(
                    """
                    INSERT INTO article_feedback_events (article_id, event_type, sentiment, created_at)
                    VALUES (?, 'report_requested', 'positive', ?)
                    """,
                    (article_id, event_time),
                )
