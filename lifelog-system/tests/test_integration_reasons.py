"""
統合テスト: 分析→深掘り→レポート生成の一連の流れで判断理由が伝播されることを確認
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.info_collector.jobs import analyze_pending, deep_research, generate_theme_report
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


def test_end_to_end_reason_propagation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    分析→深掘り→レポート生成の一連の流れで判断理由が正しく伝播されることを確認.
    """
    db_path = tmp_path / "ai_secretary.db"
    reports_dir = tmp_path / "reports"
    repo = InfoCollectorRepository(str(db_path))

    # Step 1: 記事を追加
    conn = sqlite3.connect(db_path)
    article_id = _insert_collected(
        conn,
        title="AI技術の最新動向",
        content="生成AIが急速に普及し、業界に大きな影響を与えている。",
    )
    conn.close()

    # Step 2: 分析処理（判断理由を含む）
    class AnalyzeStubClient:
        model = "stub-model"

        def generate(self, prompt, system=None, options=None):
            return json.dumps(
                {
                    "theme": "AI技術の普及",
                    "keywords": ["AI", "生成AI"],
                    "category": "AI",
                    "importance_score": 0.9,
                    "relevance_score": 0.85,
                    "importance_reason": "AI技術の最新動向で、業界に大きな影響を与える可能性がある",
                    "relevance_reason": "ユーザーの興味分野（AI・機械学習）と直接関連している",
                    "one_line_summary": "AI技術の普及",
                    "should_deep_research": True,
                }
            )

    monkeypatch.setattr(analyze_pending, "OllamaClient", lambda: AnalyzeStubClient())
    processed = analyze_pending.analyze_pending_articles(db_path=db_path, batch_size=5)
    assert processed == 1

    # 判断理由が保存されていることを確認
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT importance_reason, relevance_reason FROM article_analysis WHERE article_id = ?",
        (article_id,),
    )
    analysis_row = cursor.fetchone()
    assert analysis_row is not None
    assert analysis_row["importance_reason"] == "AI技術の最新動向で、業界に大きな影響を与える可能性がある"
    assert analysis_row["relevance_reason"] == "ユーザーの興味分野（AI・機械学習）と直接関連している"
    conn.close()

    # Step 3: 深掘り調査（判断理由がプロンプトに含まれることを確認）
    class DeepResearchStubClient:
        def __init__(self):
            self.calls = 0
            self.prompts = []

        def generate(self, prompt, system=None, options=None):
            self.calls += 1
            self.prompts.append((prompt, system))
            if self.calls == 1:
                # 検索クエリ生成
                return json.dumps(
                    {"queries": [{"query": "AI 技術 動向", "purpose": "調査"}], "language": "ja"}
                )
            # 検索結果統合
            return json.dumps(
                {
                    "key_findings": ["AI技術が急速に普及している"],
                    "detailed_summary": "AI技術の最新動向に関する深掘り調査結果",
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

    deep_research_client = DeepResearchStubClient()
    monkeypatch.setattr(deep_research, "OllamaClient", lambda: deep_research_client)
    monkeypatch.setattr(deep_research, "DDGSearchClient", StubDDG)

    processed = deep_research.deep_research_articles(db_path=db_path, batch_size=5)
    assert processed == 1

    # プロンプトに判断理由が含まれていることを確認
    assert len(deep_research_client.prompts) >= 2
    query_prompt = deep_research_client.prompts[0][0]
    assert "AI技術の最新動向で、業界に大きな影響を与える可能性がある" in query_prompt
    assert "ユーザーの興味分野（AI・機械学習）と直接関連している" in query_prompt

    synthesis_prompt = deep_research_client.prompts[1][0]
    assert "AI技術の最新動向で、業界に大きな影響を与える可能性がある" in synthesis_prompt
    assert "ユーザーの興味分野（AI・機械学習）と直接関連している" in synthesis_prompt

    # Step 4: レポート生成（判断理由がプロンプトに含まれることを確認）
    class ReportStubClient:
        def __init__(self):
            self.prompts = []

        def generate(self, prompt, system=None, options=None):
            self.prompts.append((prompt, system))
            return """# AI技術の普及

## テーマ概要
AI技術が急速に普及している。

## 主要な発見事項
- AI技術の最新動向
- 業界への大きな影響

## 各記事の詳細分析
### 記事 1: AI技術の最新動向
- **重要度**: 0.90
  - **判断理由**: AI技術の最新動向で、業界に大きな影響を与える可能性がある
- **関連度**: 0.85
  - **判断理由**: ユーザーの興味分野（AI・機械学習）と直接関連している
"""

    report_client = ReportStubClient()
    monkeypatch.setattr(generate_theme_report, "OllamaClient", lambda: report_client)

    report_paths = generate_theme_report.generate_theme_reports(
        db_path=db_path, output_dir=reports_dir, min_articles=1, skip_existing=False
    )

    assert len(report_paths) == 1
    assert report_paths[0].exists()

    # レポート生成プロンプトに判断理由が含まれていることを確認
    assert len(report_client.prompts) == 1
    report_prompt = report_client.prompts[0][0]
    assert "AI技術の最新動向で、業界に大きな影響を与える可能性がある" in report_prompt
    assert "ユーザーの興味分野（AI・機械学習）と直接関連している" in report_prompt

    # 生成されたレポートに判断理由が含まれていることを確認
    report_content = report_paths[0].read_text(encoding="utf-8")
    assert "判断理由" in report_content
    assert "AI技術の最新動向で、業界に大きな影響を与える可能性がある" in report_content
    assert "ユーザーの興味分野（AI・機械学習）と直接関連している" in report_content


