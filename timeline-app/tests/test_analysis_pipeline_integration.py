"""analysis_pipeline_worker の統合テスト。"""

from __future__ import annotations

import asyncio
import importlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.config import config
from src.workers.analysis_pipeline_worker import AnalysisPipelineWorker, _load_pipeline_functions


def _insert_collected_article(db_path: Path) -> None:
    now = datetime(2026, 3, 19, 9, 0, tzinfo=UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO collected_info (
                source_type, title, url, content, snippet,
                published_at, fetched_at, source_name, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rss",
                "生成AIの導入が開発現場で広がっている",
                "https://example.com/ai-adoption",
                (
                    "生成AIの導入が開発現場で広がっている。"
                    "企業はコード補完だけでなく、調査やドキュメント作成にもAIを使い始めた。"
                    "一方で品質保証や監査体制の整備が新たな論点になっている。"
                ),
                "生成AI導入の拡大",
                now,
                now,
                "integration",
                None,
            ),
        )


@pytest.mark.integration
def test_analysis_pipeline_worker_runs_end_to_end_with_real_ollama(tmp_path, monkeypatch):
    db_path = tmp_path / "ai_secretary.db"
    reports_dir = tmp_path / "00_Raw"
    reports_dir.mkdir()

    _load_pipeline_functions()

    repository_module = importlib.import_module("src.info_collector.repository")
    deep_module = importlib.import_module("src.info_collector.jobs.deep_research")

    repository_module.InfoCollectorRepository(str(db_path))
    _insert_collected_article(db_path)

    class StubDDG:
        def __init__(self, max_results=10):
            self.max_results = max_results

        def batch_search(self, queries, delay=1.5):
            return {
                query: [
                    {
                        "title": "生成AI導入の調査",
                        "snippet": ("生成AI導入の効果と課題をまとめた記事。" "品質管理、レビュー体制、業務プロセス再設計が論点になる。"),
                        "url": f"https://example.com/search/{index}",
                    }
                    for index in range(1, 4)
                ]
                for query in queries
            }

    monkeypatch.setattr(deep_module, "DDGSearchClient", StubDDG)
    monkeypatch.setattr(deep_module, "filter_by_relevance", lambda results, **_: results)

    monkeypatch.setattr(config.lifelog, "info_db_path", str(db_path))
    monkeypatch.setattr(config.lifelog, "report_output_dir", str(reports_dir))
    monkeypatch.setattr(config.lifelog, "analyze_batch_size", 1)
    monkeypatch.setattr(config.lifelog, "deep_batch_size", 1)
    monkeypatch.setattr(config.lifelog, "deep_min_importance", 0.0)
    monkeypatch.setattr(config.lifelog, "deep_min_relevance", 0.0)
    monkeypatch.setattr(config.lifelog, "theme_min_articles", 1)
    monkeypatch.setattr(config.lifelog, "theme_skip_existing", False)

    worker = AnalysisPipelineWorker()
    result = asyncio.run(worker.sync_once())
    assert result >= 3

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM article_analysis").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM deep_research").fetchone()[0] == 1
        assert (
            conn.execute("SELECT COUNT(*) FROM reports WHERE category = 'theme'").fetchone()[0] == 1
        )

    report_files = list(reports_dir.glob("article_*.md"))
    assert len(report_files) == 1
    content = report_files[0].read_text(encoding="utf-8")
    assert content
    assert "生成AI" in content

    status = worker.get_status()
    assert status["last_analyzed"] == 1
    assert status["last_deep_researched"] == 1
    assert status["last_reports_generated"] == 1
    assert status["last_error"] is None
