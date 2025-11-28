"""
情報収集データのリポジトリ層

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/models.py - データモデル
- src/info_collector/collectors/ - データ収集器
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Any
from pathlib import Path

from .models import CollectedInfo, InfoSummary


class InfoCollectorRepository:
    """情報収集データのCRUD操作を提供するリポジトリ"""

    def __init__(self, db_path: str = "data/ai_secretary.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_tables()

    def _ensure_db_directory(self) -> None:
        """DBディレクトリの存在確認・作成"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_tables(self) -> None:
        """テーブル初期化（存在しない場合のみ作成）"""
        with sqlite3.connect(self.db_path) as conn:
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

            # 分析結果
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS article_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL UNIQUE,
                    importance_score REAL,
                    relevance_score REAL,
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

            # 深掘り結果
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

            # レポート
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    content TEXT NOT NULL,
                    article_count INTEGER,
                    category TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reports_date
                ON reports(report_date DESC)
                """
            )

    def add_info(self, info: CollectedInfo) -> Optional[int]:
        """
        情報を追加（重複時はスキップ）

        Args:
            info: 追加する情報

        Returns:
            追加されたレコードのID（重複時はNone）
        """
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO collected_info (
                        source_type, title, url, content, snippet,
                        published_at, fetched_at, source_name, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        info.source_type,
                        info.title,
                        info.url,
                        info.content,
                        info.snippet,
                        info.published_at.isoformat()
                        if info.published_at
                        else None,
                        info.fetched_at.isoformat(),
                        info.source_name,
                        json.dumps(info.metadata, ensure_ascii=False)
                        if info.metadata
                        else None,
                    ),
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # 重複時はスキップ
                return None

    def get_info_by_id(self, info_id: int) -> Optional[CollectedInfo]:
        """IDで情報を取得"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collected_info WHERE id = ?", (info_id,)
            )
            row = cursor.fetchone()
            return self._row_to_info(row) if row else None

    def search_info(
        self,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[CollectedInfo]:
        """
        情報を検索

        Args:
            source_type: ソースタイプでフィルタ
            query: タイトル・本文での検索
            start_date: 開始日時
            end_date: 終了日時
            limit: 最大取得件数

        Returns:
            検索結果のリスト
        """
        conditions = []
        params = []

        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)

        if query:
            conditions.append("(title LIKE ? OR content LIKE ? OR snippet LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

        if start_date:
            conditions.append("fetched_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            conditions.append("fetched_at <= ?")
            params.append(end_date.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM collected_info
            WHERE {where_clause}
            ORDER BY fetched_at DESC
            LIMIT ?
        """
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_info(row) for row in cursor.fetchall()]

    def delete_old_info(self, days: int = 30) -> int:
        """
        古い情報を削除

        Args:
            days: 保持期間（日数）

        Returns:
            削除件数
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM collected_info WHERE fetched_at < ?",
                (cutoff_date.isoformat(),),
            )
            return cursor.rowcount

    def add_summary(self, summary: InfoSummary) -> int:
        """要約を追加"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO info_summaries (
                    summary_type, title, summary_text,
                    source_info_ids, created_at, query
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.summary_type,
                    summary.title,
                    summary.summary_text,
                    json.dumps(summary.source_info_ids),
                    summary.created_at.isoformat(),
                    summary.query,
                ),
            )
            return cursor.lastrowid

    def get_summary_by_id(self, summary_id: int) -> Optional[InfoSummary]:
        """IDで要約を取得"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM info_summaries WHERE id = ?", (summary_id,)
            )
            row = cursor.fetchone()
            return self._row_to_summary(row) if row else None

    def list_summaries(
        self, summary_type: Optional[str] = None, limit: int = 20
    ) -> List[InfoSummary]:
        """要約一覧を取得"""
        if summary_type:
            sql = """
                SELECT * FROM info_summaries
                WHERE summary_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (summary_type, limit)
        else:
            sql = """
                SELECT * FROM info_summaries
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (limit,)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_summary(row) for row in cursor.fetchall()]

    def _row_to_info(self, row: sqlite3.Row) -> CollectedInfo:
        """DB行をCollectedInfoに変換"""
        return CollectedInfo(
            id=row["id"],
            source_type=row["source_type"],
            title=row["title"],
            url=row["url"],
            content=row["content"],
            snippet=row["snippet"],
            published_at=datetime.fromisoformat(row["published_at"])
            if row["published_at"]
            else None,
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            source_name=row["source_name"],
            metadata=json.loads(row["metadata_json"])
            if row["metadata_json"]
            else {},
        )

    def _row_to_summary(self, row: sqlite3.Row) -> InfoSummary:
        """DB行をInfoSummaryに変換"""
        return InfoSummary(
            id=row["id"],
            summary_type=row["summary_type"],
            title=row["title"],
            summary_text=row["summary_text"],
            source_info_ids=json.loads(row["source_info_ids"])
            if row["source_info_ids"]
            else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            query=row["query"],
        )

    # --- 拡張機能: 分析/深掘り/レポート用ユーティリティ ---

    def fetch_unanalyzed(self, limit: int = 20) -> list[sqlite3.Row]:
        """
        未分析の記事を取得.

        Returns:
            collected_info行を含むRowリスト
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT c.*
            FROM collected_info c
            LEFT JOIN article_analysis a ON c.id = a.article_id
            WHERE a.id IS NULL
            ORDER BY c.fetched_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def save_analysis(
        self,
        article_id: int,
        importance: float,
        relevance: float,
        category: str,
        keywords: list[str],
        summary: str,
        model: str,
        analyzed_at: datetime,
    ) -> None:
        """分析結果を保存."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO article_analysis
                (article_id, importance_score, relevance_score, category,
                 keywords, summary, model, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    importance,
                    relevance,
                    category,
                    json.dumps(keywords, ensure_ascii=False),
                    summary,
                    model,
                    analyzed_at.isoformat(),
                ),
            )

    def fetch_deep_research_targets(
        self, min_importance: float = 0.7, min_relevance: float = 0.6, limit: int = 5
    ) -> list[sqlite3.Row]:
        """
        深掘り対象の記事を取得.

        Returns:
            article_analysis と collected_info を結合したRowリスト
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT a.*, c.title AS collected_title, c.content AS collected_content
            FROM article_analysis a
            JOIN collected_info c ON a.article_id = c.id
            LEFT JOIN deep_research d ON a.article_id = d.article_id
            WHERE a.importance_score >= ?
              AND a.relevance_score >= ?
              AND d.id IS NULL
            ORDER BY a.importance_score DESC, a.relevance_score DESC
            LIMIT ?
            """,
            (min_importance, min_relevance, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def save_deep_research(
        self,
        article_id: int,
        search_query: str,
        search_results: list[dict[str, str]],
        synthesized_content: str,
        sources: list[dict[str, str]],
        researched_at: datetime,
    ) -> None:
        """深掘り結果を保存."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO deep_research
                (article_id, search_query, search_results,
                 synthesized_content, sources, researched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    search_query,
                    json.dumps(search_results, ensure_ascii=False),
                    synthesized_content,
                    json.dumps(sources, ensure_ascii=False),
                    researched_at.isoformat(),
                ),
            )

    def fetch_recent_analysis(self, since_iso: str) -> list[dict[str, Any]]:
        """指定日時以降の分析結果を取得."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT a.*, c.title, c.url
            FROM article_analysis a
            JOIN collected_info c ON a.article_id = c.id
            WHERE a.analyzed_at >= ?
            ORDER BY a.analyzed_at DESC
            """,
            (since_iso,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def fetch_recent_deep_research(self, since_iso: str) -> list[dict[str, Any]]:
        """指定日時以降の深掘り結果を取得."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT d.*, a.summary AS theme
            FROM deep_research d
            JOIN article_analysis a ON d.article_id = a.article_id
            WHERE d.researched_at >= ?
            ORDER BY d.researched_at DESC
            """,
            (since_iso,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def save_report(
        self,
        title: str,
        report_date: str,
        content: str,
        article_count: int,
        category: str,
        created_at: datetime,
    ) -> None:
        """レポートを保存."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reports
                (title, report_date, content, article_count, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    report_date,
                    content,
                    article_count,
                    category,
                    created_at.isoformat(),
                ),
            )
