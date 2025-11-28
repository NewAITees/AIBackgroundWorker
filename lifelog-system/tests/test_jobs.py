import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.info_collector.jobs import analyze_pending, deep_research, generate_report
from src.info_collector.repository import InfoCollectorRepository


def _insert_collected(conn: sqlite3.Connection, title: str = "test title", content: str = "body") -> int:
    """Helper to insert a collected_info row."""
    now = datetime.now().isoformat()
    cur = conn.execute(
        """
        INSERT INTO collected_info (source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("rss", title, f"http://example.com/{now}", content, "snippet", now, now, "test", None),
    )
    conn.commit()
    return cur.lastrowid


def test_analyze_pending_inserts_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "ai_secretary.db"
    repo = InfoCollectorRepository(str(db_path))

    # Arrange: insert one collected article
    conn = sqlite3.connect(db_path)
    _insert_collected(conn, title="重要ニュース", content="生成AIが普及している。")

    # Stub OllamaClient to return deterministic JSON
    class StubClient:
        model = "stub-model"

        def generate(self, prompt, system=None, options=None):
            return json.dumps(
                {
                    "theme": "AI普及",
                    "keywords": ["AI", "生成AI"],
                    "category": "AI",
                    "importance_score": 0.9,
                    "relevance_score": 0.8,
                    "one_line_summary": "AIが普及",
                    "should_deep_research": True,
                }
            )

    monkeypatch.setattr(analyze_pending, "OllamaClient", lambda: StubClient())

    # Act
    processed = analyze_pending.analyze_pending_articles(db_path=db_path, batch_size=5)

    # Assert
    assert processed == 1
    cur = conn.execute("SELECT importance_score, relevance_score, category FROM article_analysis")
    row = cur.fetchone()
    assert row is not None
    assert row[0] == pytest.approx(0.9)
    assert row[1] == pytest.approx(0.8)
    assert row[2] == "AI"
    conn.close()


def test_deep_research_creates_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "ai_secretary.db"
    repo = InfoCollectorRepository(str(db_path))
    conn = sqlite3.connect(db_path)
    article_id = _insert_collected(conn, title="深掘り対象", content="AIに関する重要な記事")

    # Insert analysis with high scores
    repo.save_analysis(
        article_id=article_id,
        importance=0.9,
        relevance=0.85,
        category="AI",
        keywords=["AI", "LLM"],
        summary="AI記事の要約",
        model="test",
        analyzed_at=datetime.now(),
    )

    # Stub OllamaClient to return queries first, then synthesis
    class StubClient:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt, system=None, options=None):
            self.calls += 1
            if self.calls == 1:
                return json.dumps({"queries": [{"query": "AI トレンド", "purpose": "調査"}], "language": "ja"})
            return json.dumps(
                {
                    "key_findings": ["要約"],
                    "detailed_summary": "統合結果",
                    "sources": [{"url": "http://example.com", "title": "Example", "relevance": "high"}],
                }
            )

    class StubDDG:
        def __init__(self, max_results=10):
            pass

        def batch_search(self, queries, delay=1.5):
            return {
                queries[0]: [
                    {"title": "Result", "snippet": "詳細なスニペット" * 10, "url": "http://example.com"}
                ]
            }

    monkeypatch.setattr(deep_research, "OllamaClient", lambda: StubClient())
    monkeypatch.setattr(deep_research, "DDGSearchClient", StubDDG)

    processed = deep_research.deep_research_articles(db_path=db_path, batch_size=5)

    assert processed == 1
    cur = conn.execute("SELECT search_query, synthesized_content FROM deep_research")
    row = cur.fetchone()
    assert row is not None
    assert "AI トレンド" in row[0]
    assert row[1] == "統合結果"
    conn.close()


def test_generate_report_creates_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "ai_secretary.db"
    reports_dir = tmp_path / "reports"
    repo = InfoCollectorRepository(str(db_path))
    conn = sqlite3.connect(db_path)
    article_id = _insert_collected(conn, title="レポート記事", content="内容")

    repo.save_analysis(
        article_id=article_id,
        importance=0.8,
        relevance=0.7,
        category="AI",
        keywords=["AI"],
        summary="記事サマリ",
        model="test",
        analyzed_at=datetime.now(),
    )
    repo.save_deep_research(
        article_id=article_id,
        search_query="AI クエリ",
        search_results=[{"title": "Result", "snippet": "snip", "url": "http://example.com"}],
        synthesized_content="深掘り結果",
        sources=[{"url": "http://example.com"}],
        researched_at=datetime.now(),
    )

    class StubClient:
        def generate(self, prompt, system=None, options=None):
            return "## Report\nGenerated content"

    monkeypatch.setattr(generate_report, "OllamaClient", lambda: StubClient())

    report_path = generate_report.generate_daily_report(db_path=db_path, output_dir=reports_dir, hours=48)

    assert report_path is not None
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Generated content" in content

    cur = conn.execute("SELECT COUNT(*) FROM reports")
    assert cur.fetchone()[0] == 1
    conn.close()
