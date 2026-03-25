"""Tests for feedback event history and interest-profile style stats."""

from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

import pytest

from src.info_collector.models import CollectedInfo
from src.info_collector.repository import InfoCollectorRepository


def _add_article(
    repo: InfoCollectorRepository,
    *,
    title: str,
    url: str,
    source_name: str,
    fetched_at: datetime,
) -> int:
    article_id = repo.add_info(
        CollectedInfo(
            source_type="news",
            title=title,
            url=url,
            content="content",
            snippet="snippet",
            fetched_at=fetched_at,
            source_name=source_name,
        )
    )
    assert article_id is not None
    return article_id


def test_feedback_events_and_stats(tmp_path: Path):
    db_path = tmp_path / "info.db"
    repo = InfoCollectorRepository(str(db_path))
    now = datetime.now()

    article_a = _add_article(
        repo,
        title="AI market update",
        url="https://example.com/a",
        source_name="SourceA",
        fetched_at=now,
    )
    article_b = _add_article(
        repo,
        title="Politics digest",
        url="https://example.com/b",
        source_name="SourceB",
        fetched_at=now - timedelta(days=10),
    )

    repo.save_analysis(
        article_id=article_a,
        importance=0.8,
        relevance=0.8,
        category="AI",
        keywords=["ai"],
        summary="AI summary",
        model="test",
        analyzed_at=now,
    )
    repo.save_analysis(
        article_id=article_b,
        importance=0.7,
        relevance=0.5,
        category="日本政治",
        keywords=["politics"],
        summary="Politics summary",
        model="test",
        analyzed_at=now - timedelta(days=10),
    )

    repo.toggle_feedback(article_a, "positive")
    repo.request_report(article_a)
    repo.toggle_feedback(article_b, "negative")

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT article_id, event_type, sentiment
            FROM article_feedback_events
            ORDER BY id ASC
            """
        ).fetchall()

    assert rows == [
        (article_a, "feedback_positive", "positive"),
        (article_a, "report_requested", "positive"),
        (article_b, "feedback_negative", "negative"),
    ]

    stats = repo.get_feedback_stats()
    source_a = next(item for item in stats["source"] if item["name"] == "SourceA")
    source_b = next(item for item in stats["source"] if item["name"] == "SourceB")
    category_ai = next(item for item in stats["category"] if item["name"] == "AI")
    category_politics = next(item for item in stats["category"] if item["name"] == "日本政治")

    assert source_a["positive"] > source_b["positive"]
    assert source_a["report_requested"] == 1.0
    assert source_a["score"] > source_b["score"]
    assert category_ai["score"] > category_politics["score"]
    assert stats["config"]["report_requested_weight"] == 3.0


def test_toggle_feedback_records_clear_event(tmp_path: Path):
    db_path = tmp_path / "info.db"
    repo = InfoCollectorRepository(str(db_path))
    article_id = _add_article(
        repo,
        title="Same article",
        url="https://example.com/clear",
        source_name="SourceC",
        fetched_at=datetime.now(),
    )

    repo.toggle_feedback(article_id, "positive")
    state = repo.toggle_feedback(article_id, "positive")

    assert state["sentiment"] is None

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT event_type, sentiment FROM article_feedback_events ORDER BY id ASC"
        ).fetchall()

    assert rows == [
        ("feedback_positive", "positive"),
        ("feedback_cleared", None),
    ]


def test_get_article_analysis_map_returns_bonus_breakdown(tmp_path: Path):
    db_path = tmp_path / "info.db"
    repo = InfoCollectorRepository(str(db_path))
    article_id = _add_article(
        repo,
        title="Explained article",
        url="https://example.com/explained",
        source_name="SourceX",
        fetched_at=datetime.now(),
    )

    repo.save_analysis(
        article_id=article_id,
        importance=0.72,
        relevance=0.68,
        category="AI",
        keywords=["AI"],
        summary="summary",
        model="test",
        analyzed_at=datetime.now(),
        importance_reason="importance reason",
        relevance_reason="relevance reason",
        llm_importance=0.6,
        llm_relevance=0.55,
        source_bonus=0.07,
        category_bonus=0.05,
    )

    analysis_map = repo.get_article_analysis_map([article_id])

    assert analysis_map[article_id]["llm_importance_score"] == 0.6
    assert analysis_map[article_id]["source_bonus"] == 0.07
    assert analysis_map[article_id]["category_bonus"] == 0.05
    assert analysis_map[article_id]["total_bonus"] == pytest.approx(0.12)
