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

    assert "article_ids_hash" in report_cols
    assert "importance_reason" in analysis_cols
    assert "relevance_reason" in analysis_cols

    # ensure saving still works after migration
    repo.save_report(
        title="test",
        report_date="2024-01-01",
        content="content",
        article_count=0,
        category="daily",
        created_at=datetime.now(),
    )
