"""
記事分析・深掘り操作ミックスイン

article_analysis テーブルと deep_research テーブルを操作するメソッド群。
InfoCollectorRepository に mix-in して使用する。
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional


class AnalysisMixin:
    """article_analysis / deep_research の操作を提供するミックスイン。"""

    def fetch_unanalyzed(self, limit: int = 20) -> list[sqlite3.Row]:
        """
        未分析の記事を取得.

        Returns:
            collected_info行を含むRowリスト
        """
        with self._connect() as conn:
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
            return cursor.fetchall()

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
        importance_reason: Optional[str] = None,
        relevance_reason: Optional[str] = None,
        llm_importance: Optional[float] = None,
        llm_relevance: Optional[float] = None,
        source_bonus: float = 0.0,
        category_bonus: float = 0.0,
    ) -> None:
        """
        分析結果を保存.

        Args:
            article_id: 記事ID
            importance: 重要度スコア
            relevance: 関連度スコア
            category: カテゴリ
            keywords: キーワードリスト
            summary: 要約
            model: 使用モデル
            analyzed_at: 分析日時
            importance_reason: 重要度の判断理由（オプション）
            relevance_reason: 関連度の判断理由（オプション）
            llm_importance: 補正前のLLM重要度（オプション）
            llm_relevance: 補正前のLLM関連度（オプション）
            source_bonus: source由来の補正値
            category_bonus: category由来の補正値
        """

        def _op() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO article_analysis
                    (article_id, importance_score, relevance_score, category,
                     keywords, summary, model, analyzed_at, importance_reason, relevance_reason,
                     llm_importance_score, llm_relevance_score, source_bonus, category_bonus)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        importance_reason or "",
                        relevance_reason or "",
                        llm_importance,
                        llm_relevance,
                        source_bonus,
                        category_bonus,
                    ),
                )

        self._run_with_lock_retry(_op, retries=8, base_sleep=0.3)

    def fetch_deep_research_targets(
        self, min_importance: float = 0.7, min_relevance: float = 0.6, limit: int = 5
    ) -> list[sqlite3.Row]:
        """
        深掘り対象の記事を取得.

        Returns:
            article_analysis と collected_info を結合したRowリスト
            （importance_reason と relevance_reason を含む）
        """
        with self._connect() as conn:
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
            return cursor.fetchall()

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

        def _op() -> None:
            with self._connect() as conn:
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

        self._run_with_lock_retry(_op)

    def fetch_recent_analysis(self, since_iso: str) -> list[dict[str, Any]]:
        """指定日時以降の分析結果を取得."""
        with self._connect() as conn:
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
            return [dict(r) for r in cursor.fetchall()]

    def fetch_recent_deep_research(self, since_iso: str) -> list[dict[str, Any]]:
        """指定日時以降の深掘り結果を取得."""
        with self._connect() as conn:
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
            return [dict(r) for r in cursor.fetchall()]

    def fetch_deep_research_by_theme(
        self, min_articles: int = 1
    ) -> dict[str, list[dict[str, Any]]]:
        """
        深掘り済み記事をテーマ（summary）ごとにグループ化して取得.

        Args:
            min_articles: テーマごとの最小記事数（この数以上の記事があるテーマのみ返す）

        Returns:
            テーマ（summary）をキー、深掘り結果のリストを値とする辞書
            （importance_reason と relevance_reason を含む）
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    d.*,
                    a.summary AS theme,
                    a.importance_score,
                    a.relevance_score,
                    a.importance_reason,
                    a.relevance_reason,
                    a.category,
                    a.keywords,
                    c.title AS article_title,
                    c.url AS article_url,
                    c.content AS article_content,
                    c.published_at AS article_published_at,
                    c.fetched_at AS article_fetched_at
                FROM deep_research d
                JOIN article_analysis a ON d.article_id = a.article_id
                JOIN collected_info c ON d.article_id = c.id
                WHERE a.summary IS NOT NULL AND a.summary != ''
                ORDER BY d.researched_at DESC
                """,
            )
            rows = [dict(r) for r in cursor.fetchall()]

        # テーマごとにグループ化
        theme_groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            theme = row.get("theme", "その他")
            if theme not in theme_groups:
                theme_groups[theme] = []
            theme_groups[theme].append(row)

        # 最小記事数以上のテーマのみ返す
        return {
            theme: articles
            for theme, articles in theme_groups.items()
            if len(articles) >= min_articles
        }

    def fetch_deep_research_per_article(
        self, article_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """深掘り済み記事を記事単位のフラットリストで取得.

        Args:
            article_id: 指定した場合はその記事のみ返す
        """
        params: list[Any] = []
        where_extra = ""
        if article_id is not None:
            where_extra = "AND d.article_id = ?"
            params.append(article_id)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"""
                SELECT
                    d.*,
                    a.summary AS theme,
                    a.importance_score,
                    a.relevance_score,
                    a.importance_reason,
                    a.relevance_reason,
                    a.category,
                    a.keywords,
                    c.title AS article_title,
                    c.url AS article_url,
                    c.content AS article_content,
                    c.published_at AS article_published_at,
                    c.fetched_at AS article_fetched_at
                FROM deep_research d
                JOIN article_analysis a ON d.article_id = a.article_id
                JOIN collected_info c ON d.article_id = c.id
                WHERE a.summary IS NOT NULL AND a.summary != ''
                {where_extra}
                ORDER BY a.importance_score DESC, d.researched_at DESC
                """,
                params,
            )
            return [dict(r) for r in cursor.fetchall()]

    def fetch_article_analysis_by_id(self, article_id: int) -> Optional[sqlite3.Row]:
        """指定 article_id の分析結果を取得（deep_research 単体実行用）."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT a.*, c.title AS collected_title, c.content AS collected_content
                FROM article_analysis a
                JOIN collected_info c ON a.article_id = c.id
                WHERE a.article_id = ?
                """,
                (article_id,),
            )
            return cursor.fetchone()

    def get_article_analysis_map(self, article_ids: list[int]) -> dict[int, dict[str, Any]]:
        """指定した記事IDの分析・補正説明データをまとめて返す。"""
        if not article_ids:
            return {}
        placeholders = ",".join("?" * len(article_ids))
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                    article_id,
                    category,
                    importance_score,
                    relevance_score,
                    llm_importance_score,
                    llm_relevance_score,
                    source_bonus,
                    category_bonus,
                    importance_reason,
                    relevance_reason
                FROM article_analysis
                WHERE article_id IN ({placeholders})
                """,
                article_ids,
            ).fetchall()

        analysis_map: dict[int, dict[str, Any]] = {}
        for row in rows:
            total_bonus = float(row["source_bonus"] or 0.0) + float(row["category_bonus"] or 0.0)
            analysis_map[row["article_id"]] = {
                "category": row["category"] or "未分類",
                "importance_score": float(row["importance_score"] or 0.0),
                "relevance_score": float(row["relevance_score"] or 0.0),
                "llm_importance_score": float(row["llm_importance_score"] or 0.0),
                "llm_relevance_score": float(row["llm_relevance_score"] or 0.0),
                "source_bonus": float(row["source_bonus"] or 0.0),
                "category_bonus": float(row["category_bonus"] or 0.0),
                "total_bonus": total_bonus,
                "importance_reason": row["importance_reason"] or "",
                "relevance_reason": row["relevance_reason"] or "",
            }
        return analysis_map

    def force_article_for_research(self, article_id: int) -> None:
        """ユーザー要求によりレポート生成対象に強制追加する（importance=1.0に設定）。"""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO article_analysis
                    (article_id, importance_score, relevance_score, category, keywords,
                     summary, model, analyzed_at)
                VALUES (?, 1.0, 1.0, 'user_requested', '', '', 'user', ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    importance_score = 1.0,
                    relevance_score  = 1.0,
                    analyzed_at      = excluded.analyzed_at
                """,
                (article_id, now),
            )
            # deep_research が存在する場合は削除して再実行させる
            conn.execute("DELETE FROM deep_research WHERE article_id = ?", (article_id,))
