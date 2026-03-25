"""
記事・サマリーCRUD操作ミックスイン

collected_info テーブルと info_summaries テーブルを操作するメソッド群。
InfoCollectorRepository に mix-in して使用する。
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from src.info_collector.models import CollectedInfo, InfoSummary


class ArticleMixin:
    """collected_info / info_summaries の CRUD を提供するミックスイン。"""

    def add_info(self, info: CollectedInfo) -> Optional[int]:
        """
        情報を追加（重複時はスキップ）

        Args:
            info: 追加する情報

        Returns:
            追加されたレコードのID（重複時はNone）
        """

        def _op() -> Optional[int]:
            with self._connect() as conn:
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
                            info.published_at.isoformat() if info.published_at else None,
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

        return self._run_with_lock_retry(_op)

    def get_info_by_id(self, info_id: int) -> Optional[CollectedInfo]:
        """IDで情報を取得"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM collected_info WHERE id = ?", (info_id,))
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

        with self._connect() as conn:
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
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM collected_info WHERE fetched_at < ?",
                (cutoff_date.isoformat(),),
            )
            return cursor.rowcount

    def add_summary(self, summary: InfoSummary) -> int:
        """要約を追加"""
        with self._connect() as conn:
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
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM info_summaries WHERE id = ?", (summary_id,))
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

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_summary(row) for row in cursor.fetchall()]

    def get_articles_by_ids(self, article_ids: list[int]) -> list[dict]:
        """指定した記事IDの詳細を返す。"""
        if not article_ids:
            return []
        placeholders = ",".join("?" * len(article_ids))
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, title, url, source_name, snippet, source_type, published_at, fetched_at
                FROM collected_info
                WHERE id IN ({placeholders})
                ORDER BY fetched_at DESC
                """,
                article_ids,
            ).fetchall()
        order_map = {article_id: index for index, article_id in enumerate(article_ids)}
        articles = [dict(r) for r in rows]
        articles.sort(key=lambda article: order_map.get(article["id"], len(order_map)))
        return articles

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
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )

    def _row_to_summary(self, row: sqlite3.Row) -> InfoSummary:
        """DB行をInfoSummaryに変換"""
        return InfoSummary(
            id=row["id"],
            summary_type=row["summary_type"],
            title=row["title"],
            summary_text=row["summary_text"],
            source_info_ids=json.loads(row["source_info_ids"]) if row["source_info_ids"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            query=row["query"],
        )
