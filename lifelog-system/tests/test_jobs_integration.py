"""
Integration test that exercises the full pipeline with real Ollama + DuckDuckGo.

前提:
- ローカルで Ollama が起動し、モデルがpull済み (例: qwen2.5:20b や llama3)
- ネットワーク経由で DuckDuckGo 検索が可能
"""

import os
import sqlite3
from pathlib import Path

import pytest
import requests

from src.info_collector.jobs import analyze_pending, deep_research, generate_report
from src.info_collector.repository import InfoCollectorRepository


def test_full_pipeline_real_services(tmp_path: Path):
    """収集済み1件を分析→深掘り→レポート生成まで通す."""
    # Windows側のOllamaに127.0.0.1でアクセス（WSLからWindowsのOllamaに接続）
    ollama_url = "http://127.0.0.1:11434"
    
    # OllamaのAPIエンドポイントが利用可能か確認
    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        resp.raise_for_status()
    except (requests.RequestException, requests.Timeout) as e:
        pytest.fail(f"Ollama API not available at {ollama_url}: {e}")
    
    # 環境変数でOllamaの設定を指定（テスト実行中のみ有効）
    original_base_url = os.environ.get("OLLAMA_BASE_URL")
    original_model = os.environ.get("OLLAMA_MODEL")
    
    try:
        os.environ["OLLAMA_BASE_URL"] = ollama_url
        os.environ["OLLAMA_MODEL"] = "gpt-oss:20b"

        db_path = tmp_path / "ai_secretary.db"
        reports_dir = tmp_path / "reports"
        repo = InfoCollectorRepository(str(db_path))

        # 収集データを1件投入
        conn = sqlite3.connect(db_path)
        now = "2025-01-01T00:00:00"
        conn.execute(
            """
            INSERT INTO collected_info (source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "rss",
                "統合テスト用記事",
                "http://example.com/integration",
                "生成AIが広く普及し始めている。",
                "snip",
                now,
                now,
                "integration",
                None,
            ),
        )
        conn.commit()
        conn.close()

        # 分析（LLM①）
        processed = analyze_pending.analyze_pending_articles(db_path=db_path, batch_size=1)
        assert processed >= 1, "分析が1件以上行われていません"

        # 深掘り（LLM②+③+DDG）: 閾値を下げて必ず対象にする
        deep = deep_research.deep_research_articles(
            db_path=db_path, batch_size=1, min_importance=0.0, min_relevance=0.0
        )
        assert deep >= 1, "深掘りが1件以上行われていません"

        # レポート生成（LLM④）
        report_path = generate_report.generate_daily_report(
            db_path=db_path, output_dir=reports_dir, hours=48
        )
        assert report_path is not None and report_path.exists(), "レポートファイルが生成されていません"
    finally:
        # 環境変数を元に戻す
        if original_base_url is None:
            os.environ.pop("OLLAMA_BASE_URL", None)
        else:
            os.environ["OLLAMA_BASE_URL"] = original_base_url
        
        if original_model is None:
            os.environ.pop("OLLAMA_MODEL", None)
        else:
            os.environ["OLLAMA_MODEL"] = original_model
