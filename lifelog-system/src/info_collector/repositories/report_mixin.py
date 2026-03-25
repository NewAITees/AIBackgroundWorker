"""
レポート操作ミックスイン

reports テーブルを操作するメソッド群。
InfoCollectorRepository に mix-in して使用する。
"""

import sqlite3
from datetime import datetime
from typing import Any, Optional


class ReportMixin:
    """reports テーブルの操作を提供するミックスイン。"""

    def save_report(
        self,
        title: str,
        report_date: str,
        content: str,
        article_count: int,
        category: str,
        created_at: datetime,
        article_ids_hash: Optional[str] = None,
        source_article_id: Optional[int] = None,
    ) -> None:
        """
        レポートを保存.

        Args:
            title: レポートタイトル
            report_date: レポート日付
            content: レポート内容（Markdown）
            article_count: 記事数
            category: カテゴリ（daily, theme等）
            created_at: 作成日時
            article_ids_hash: 記事IDセットのハッシュ値（重複チェック用、旧方式）
            source_article_id: 元記事のID（記事単位の重複チェック用、新方式）
        """

        def _op() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO reports
                    (title, report_date, content, article_count, category,
                     article_ids_hash, source_article_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        report_date,
                        content,
                        article_count,
                        category,
                        article_ids_hash,
                        source_article_id,
                        created_at.isoformat(),
                    ),
                )

        self._run_with_lock_retry(_op)

    def get_existing_report_hashes(self) -> list[str]:
        """
        DBに保存されている既存レポートのハッシュ値リストを取得.

        Returns:
            既存レポートのハッシュ値リスト（NULL値は除外）
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT DISTINCT article_ids_hash
                FROM reports
                WHERE article_ids_hash IS NOT NULL AND article_ids_hash != ''
                """
            )
            return [row["article_ids_hash"] for row in cursor.fetchall()]

    def get_existing_report_article_ids(self) -> set[int]:
        """DBに保存されている既存レポートの source_article_id セットを取得."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT DISTINCT source_article_id
                FROM reports
                WHERE source_article_id IS NOT NULL
                """
            )
            return {row["source_article_id"] for row in cursor.fetchall()}

    def fetch_reports_by_date(
        self,
        report_date: str,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        指定日のレポートを取得.

        Args:
            report_date: レポート日付（YYYY-MM-DD）
            category: カテゴリでの絞り込み（例: 'theme', 'integrated_daily'）

        Returns:
            レポートの辞書リスト（新しい順）
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM reports WHERE report_date = ?"
            params: list[Any] = [report_date]
            if category:
                query += " AND category = ?"
                params.append(category)
            query += " ORDER BY created_at DESC"

            cursor = conn.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_latest_report_id(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM reports").fetchone()
        return int(row[0] or 0)

    def get_reports_after_id(self, last_report_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, title, content, category, created_at
                FROM reports
                WHERE id > ?
                ORDER BY id ASC
                """,
                (last_report_id,),
            ).fetchall()
        return [dict(row) for row in rows]
