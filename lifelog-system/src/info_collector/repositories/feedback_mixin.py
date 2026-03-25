"""
フィードバック操作ミックスイン

article_feedback テーブルと article_feedback_events テーブルを操作するメソッド群。
InfoCollectorRepository に mix-in して使用する。
"""

import sqlite3
from datetime import datetime
from typing import Any


class FeedbackMixin:
    """article_feedback / article_feedback_events の操作を提供するミックスイン。"""

    def _get_feedback_state(self, conn: sqlite3.Connection, article_id: int) -> dict[str, Any]:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT article_id, sentiment, report_status, report_entry_id, updated_at
            FROM article_feedback
            WHERE article_id = ?
            """,
            (article_id,),
        ).fetchone()
        if not row:
            return {
                "article_id": article_id,
                "sentiment": None,
                "report_status": "none",
                "report_entry_id": None,
                "updated_at": None,
            }
        return {
            "article_id": row["article_id"],
            "sentiment": row["sentiment"],
            "report_status": row["report_status"] or "none",
            "report_entry_id": row["report_entry_id"],
            "updated_at": row["updated_at"],
        }

    def _append_feedback_event(
        self,
        conn: sqlite3.Connection,
        article_id: int,
        event_type: str,
        *,
        sentiment: str | None,
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO article_feedback_events (article_id, event_type, sentiment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (article_id, event_type, sentiment, created_at),
        )

    def toggle_feedback(self, article_id: int, sentiment: str) -> dict[str, Any]:
        """positive / negative を排他的トグルで保存する。"""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            current = self._get_feedback_state(conn, article_id)
            next_sentiment = None if current["sentiment"] == sentiment else sentiment
            conn.execute(
                """
                INSERT INTO article_feedback (
                    article_id, feedback_type, created_at, sentiment, report_status, report_entry_id, updated_at
                )
                VALUES (?, ?, ?, ?, 'none', NULL, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    feedback_type = excluded.feedback_type,
                    sentiment = excluded.sentiment,
                    updated_at = excluded.updated_at
                """,
                (
                    article_id,
                    next_sentiment or "neutral",
                    now,
                    next_sentiment,
                    now,
                ),
            )
            self._append_feedback_event(
                conn,
                article_id,
                "feedback_cleared" if next_sentiment is None else f"feedback_{next_sentiment}",
                sentiment=next_sentiment,
                created_at=now,
            )
            return self._get_feedback_state(conn, article_id)

    def request_report(self, article_id: int) -> tuple[bool, dict[str, Any]]:
        """レポート生成要求を記録し、多重実行可否と現在状態を返す。"""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            current = self._get_feedback_state(conn, article_id)
            if current["report_status"] in {"requested", "running", "done"}:
                return False, current

            conn.execute(
                """
                INSERT INTO article_feedback (
                    article_id, feedback_type, created_at, sentiment, report_status, report_entry_id, updated_at
                )
                VALUES (?, 'report_requested', ?, 'positive', 'requested', NULL, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    feedback_type = 'report_requested',
                    sentiment = 'positive',
                    report_status = 'requested',
                    report_entry_id = NULL,
                    updated_at = excluded.updated_at
                """,
                (article_id, now, now),
            )
            self._append_feedback_event(
                conn,
                article_id,
                "report_requested",
                sentiment="positive",
                created_at=now,
            )
            return True, self._get_feedback_state(conn, article_id)

    def mark_report_running(self, article_id: int) -> dict[str, Any]:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE article_feedback
                SET report_status = 'running',
                    updated_at = ?
                WHERE article_id = ?
                """,
                (now, article_id),
            )
            self._append_feedback_event(
                conn,
                article_id,
                "report_running",
                sentiment="positive",
                created_at=now,
            )
            return self._get_feedback_state(conn, article_id)

    def mark_report_done(self, article_id: int, report_entry_id: str | None) -> dict[str, Any]:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE article_feedback
                SET sentiment = 'positive',
                    report_status = 'done',
                    report_entry_id = ?,
                    updated_at = ?
                WHERE article_id = ?
                """,
                (report_entry_id, now, article_id),
            )
            self._append_feedback_event(
                conn,
                article_id,
                "report_done",
                sentiment="positive",
                created_at=now,
            )
            return self._get_feedback_state(conn, article_id)

    def mark_report_failed(self, article_id: int) -> dict[str, Any]:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE article_feedback
                SET report_status = 'failed',
                    updated_at = ?
                WHERE article_id = ?
                """,
                (now, article_id),
            )
            self._append_feedback_event(
                conn,
                article_id,
                "report_failed",
                sentiment=current["sentiment"]
                if (current := self._get_feedback_state(conn, article_id))
                else None,
                created_at=now,
            )
            return self._get_feedback_state(conn, article_id)

    def get_feedback_state_map(self, article_ids: list[int]) -> dict[int, dict[str, Any]]:
        """指定した記事IDのフィードバック状態をまとめて返す。"""
        if not article_ids:
            return {}
        placeholders = ",".join("?" * len(article_ids))
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT article_id, sentiment, report_status, report_entry_id, updated_at
                FROM article_feedback
                WHERE article_id IN ({placeholders})
                """,
                article_ids,
            ).fetchall()
        return {
            row["article_id"]: {
                "article_id": row["article_id"],
                "sentiment": row["sentiment"],
                "report_status": row["report_status"] or "none",
                "report_entry_id": row["report_entry_id"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def get_feedback_stats(self) -> dict[str, Any]:
        """source/category ごとの時間減衰つきフィードバック統計を返す。"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    e.article_id,
                    e.event_type,
                    e.sentiment,
                    e.created_at,
                    c.source_name,
                    COALESCE(NULLIF(a.category, ''), '未分類') AS category
                FROM article_feedback_events e
                JOIN collected_info c ON e.article_id = c.id
                LEFT JOIN article_analysis a ON e.article_id = a.article_id
                WHERE e.event_type IN ('feedback_positive', 'feedback_negative', 'report_requested')
                ORDER BY e.created_at DESC, e.id DESC
                """
            ).fetchall()

        now = datetime.now()
        groups = {
            "source": {},
            "category": {},
        }
        prior_alpha = 2.0
        prior_beta = 2.0
        min_samples = 3.0
        report_requested_weight = 3.0
        negative_weight = 1.0

        def _decay_weight(created_at: str | None) -> float:
            if not created_at:
                return 0.2
            try:
                ts = datetime.fromisoformat(created_at)
            except ValueError:
                return 0.2
            age_days = max((now - ts).total_seconds() / 86400.0, 0.0)
            if age_days <= 7:
                return 1.0
            if age_days <= 30:
                return 0.5
            return 0.2

        def _ensure_bucket(kind: str, name: str) -> dict[str, Any]:
            bucket = groups[kind].get(name)
            if bucket is None:
                bucket = {
                    "name": name,
                    "positive": 0.0,
                    "negative": 0.0,
                    "report_requested": 0.0,
                    "samples": 0.0,
                    "score": 0.5,
                    "bonus": 0.0,
                }
                groups[kind][name] = bucket
            return bucket

        def _apply_event(bucket: dict[str, Any], event_type: str, weight: float) -> None:
            if event_type == "feedback_positive":
                bucket["positive"] += weight
                bucket["samples"] += weight
            elif event_type == "feedback_negative":
                bucket["negative"] += negative_weight * weight
                bucket["samples"] += negative_weight * weight
            elif event_type == "report_requested":
                bucket["positive"] += report_requested_weight * weight
                bucket["report_requested"] += weight
                bucket["samples"] += report_requested_weight * weight

        for row in rows:
            weight = _decay_weight(row["created_at"])
            source_name = row["source_name"] or "不明"
            category = row["category"] or "未分類"
            _apply_event(_ensure_bucket("source", source_name), row["event_type"], weight)
            _apply_event(_ensure_bucket("category", category), row["event_type"], weight)

        def _finalize(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = []
            for item in items.values():
                weighted_positive = item["positive"]
                weighted_negative = item["negative"]
                score = (weighted_positive + prior_alpha) / (
                    weighted_positive + weighted_negative + prior_alpha + prior_beta
                )
                confidence = min(item["samples"] / min_samples, 1.0) if min_samples > 0 else 1.0
                bonus = (score - 0.5) * confidence
                result.append(
                    {
                        "name": item["name"],
                        "positive": round(weighted_positive, 3),
                        "negative": round(weighted_negative, 3),
                        "report_requested": round(item["report_requested"], 3),
                        "samples": round(item["samples"], 3),
                        "score": round(score, 4),
                        "bonus": round(bonus, 4),
                    }
                )
            result.sort(key=lambda item: (item["score"], item["samples"]), reverse=True)
            return result

        return {
            "config": {
                "prior_alpha": prior_alpha,
                "prior_beta": prior_beta,
                "min_samples": min_samples,
                "report_requested_weight": report_requested_weight,
                "decay_windows": [
                    {"max_days": 7, "weight": 1.0},
                    {"max_days": 30, "weight": 0.5},
                    {"max_days": None, "weight": 0.2},
                ],
            },
            "source": _finalize(groups["source"]),
            "category": _finalize(groups["category"]),
        }
