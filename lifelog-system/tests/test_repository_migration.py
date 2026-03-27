"""Tests for InfoCollectorRepository schema migration helpers."""

import sqlite3
from datetime import datetime
from pathlib import Path

from src.info_collector.repository import InfoCollectorRepository


def test_repository_adds_missing_columns(tmp_path: Path):
    """既存DBに不足カラムがある場合に安全に追加されることを確認."""
    db_path = tmp_path / "info.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE reports (
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
        CREATE TABLE article_analysis (
            article_id INTEGER PRIMARY KEY,
            importance_score REAL,
            relevance_score REAL,
            category TEXT,
            keywords TEXT,
            summary TEXT,
            model TEXT,
            analyzed_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    repo = InfoCollectorRepository(str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("PRAGMA table_info(reports)")
        report_cols = {row["name"] for row in cursor.fetchall()}
        cursor = conn.execute("PRAGMA table_info(article_analysis)")
        analysis_cols = {row["name"] for row in cursor.fetchall()}
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}

    assert "article_ids_hash" in report_cols
    assert "importance_reason" in analysis_cols
    assert "relevance_reason" in analysis_cols
    assert "llm_importance_score" in analysis_cols
    assert "llm_relevance_score" in analysis_cols
    assert "source_bonus" in analysis_cols
    assert "category_bonus" in analysis_cols
    assert "article_feedback_events" in tables

    # ensure saving still works after migration
    repo.save_report(
        title="test",
        report_date="2024-01-01",
        content="content",
        article_count=0,
        category="daily",
        created_at=datetime.now(),
    )


def test_repository_backfills_feedback_events_from_feedback_table(tmp_path: Path):
    db_path = tmp_path / "info.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE collected_info (
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
        CREATE TABLE reports (
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
        CREATE TABLE article_analysis (
            article_id INTEGER PRIMARY KEY,
            importance_score REAL,
            relevance_score REAL,
            category TEXT,
            keywords TEXT,
            summary TEXT,
            model TEXT,
            analyzed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE article_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL UNIQUE,
            feedback_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sentiment TEXT,
            report_status TEXT,
            report_entry_id TEXT,
            updated_at TEXT
        )
        """
    )
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO collected_info (id, source_type, title, url, fetched_at, source_name)
        VALUES (1, 'news', 'title', 'https://example.com', ?, 'Source')
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO article_feedback
        (article_id, feedback_type, created_at, sentiment, report_status, updated_at)
        VALUES (1, 'report_requested', ?, 'positive', 'done', ?)
        """,
        (now, now),
    )
    conn.commit()
    conn.close()

    InfoCollectorRepository(str(db_path))

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT event_type, sentiment
            FROM article_feedback_events
            ORDER BY id ASC
            """
        ).fetchall()

    assert rows == [
        ("feedback_positive", "positive"),
        ("report_requested", "positive"),
    ]
