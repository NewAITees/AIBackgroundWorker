"""
リポジトリ層の判断理由保存・取得機能のテスト
"""

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.info_collector.repository import InfoCollectorRepository


@pytest.fixture
def repo():
    """テスト用のリポジトリを作成."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    repo = InfoCollectorRepository(db_path)
    yield repo

    # クリーンアップ
    Path(db_path).unlink(missing_ok=True)


def test_save_analysis_with_reasons(repo: InfoCollectorRepository):
    """save_analysis()で判断理由が正しく保存されることを確認."""
    # テスト用の記事を追加
    conn = sqlite3.connect(repo.db_path)
    cursor = conn.execute(
        """
        INSERT INTO collected_info (source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "rss",
            "テスト記事",
            "http://example.com/test",
            "テスト内容",
            "スニペット",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            "test",
            None,
        ),
    )
    conn.commit()
    article_id = cursor.lastrowid
    conn.close()

    # 判断理由を含む分析結果を保存
    importance_reason = "AI技術の最新動向で、業界に大きな影響を与える可能性がある"
    relevance_reason = "ユーザーの興味分野（AI・機械学習）と直接関連している"

    repo.save_analysis(
        article_id=article_id,
        importance=0.85,
        relevance=0.90,
        category="AI",
        keywords=["AI", "LLM"],
        summary="AI技術の最新動向",
        model="test-model",
        analyzed_at=datetime.now(),
        importance_reason=importance_reason,
        relevance_reason=relevance_reason,
    )

    # 保存されたデータを確認
    conn = sqlite3.connect(repo.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT importance_score, relevance_score, importance_reason, relevance_reason
        FROM article_analysis
        WHERE article_id = ?
        """,
        (article_id,),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["importance_score"] == pytest.approx(0.85)
    assert row["relevance_score"] == pytest.approx(0.90)
    assert row["importance_reason"] == importance_reason
    assert row["relevance_reason"] == relevance_reason


def test_save_analysis_without_reasons(repo: InfoCollectorRepository):
    """判断理由なしでsave_analysis()を呼び出した場合、空文字列が保存されることを確認."""
    # テスト用の記事を追加
    conn = sqlite3.connect(repo.db_path)
    cursor = conn.execute(
        """
        INSERT INTO collected_info (source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "rss",
            "テスト記事2",
            "http://example.com/test2",
            "テスト内容2",
            "スニペット2",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            "test",
            None,
        ),
    )
    conn.commit()
    article_id = cursor.lastrowid
    conn.close()

    # 判断理由なしで分析結果を保存
    repo.save_analysis(
        article_id=article_id,
        importance=0.70,
        relevance=0.65,
        category="その他",
        keywords=["テスト"],
        summary="テスト要約",
        model="test-model",
        analyzed_at=datetime.now(),
    )

    # 保存されたデータを確認
    conn = sqlite3.connect(repo.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT importance_reason, relevance_reason
        FROM article_analysis
        WHERE article_id = ?
        """,
        (article_id,),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["importance_reason"] == ""
    assert row["relevance_reason"] == ""


def test_fetch_deep_research_targets_includes_reasons(repo: InfoCollectorRepository):
    """fetch_deep_research_targets()で判断理由が取得されることを確認."""
    # テスト用の記事と分析結果を追加
    conn = sqlite3.connect(repo.db_path)
    cursor = conn.execute(
        """
        INSERT INTO collected_info (source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "rss",
            "深掘り対象記事",
            "http://example.com/deep",
            "深掘り対象の内容",
            "スニペット",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            "test",
            None,
        ),
    )
    conn.commit()
    article_id = cursor.lastrowid
    conn.close()

    # 判断理由を含む分析結果を保存
    repo.save_analysis(
        article_id=article_id,
        importance=0.85,
        relevance=0.80,
        category="AI",
        keywords=["AI"],
        summary="深掘り対象の要約",
        model="test-model",
        analyzed_at=datetime.now(),
        importance_reason="重要な技術動向",
        relevance_reason="ユーザーの興味分野と関連",
    )

    # 深掘り対象を取得
    targets = repo.fetch_deep_research_targets(min_importance=0.7, min_relevance=0.6, limit=5)

    assert len(targets) == 1
    target = targets[0]
    assert target["article_id"] == article_id
    assert "importance_reason" in target.keys()
    assert "relevance_reason" in target.keys()
    assert target["importance_reason"] == "重要な技術動向"
    assert target["relevance_reason"] == "ユーザーの興味分野と関連"


def test_fetch_deep_research_by_theme_includes_reasons(repo: InfoCollectorRepository):
    """fetch_deep_research_by_theme()で判断理由が取得されることを確認."""
    # テスト用の記事、分析結果、深掘り結果を追加
    conn = sqlite3.connect(repo.db_path)
    cursor = conn.execute(
        """
        INSERT INTO collected_info (source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "rss",
            "レポート記事",
            "http://example.com/report",
            "レポート内容",
            "スニペット",
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            "test",
            None,
        ),
    )
    conn.commit()
    article_id = cursor.lastrowid
    conn.close()

    # 分析結果を保存
    repo.save_analysis(
        article_id=article_id,
        importance=0.90,
        relevance=0.85,
        category="AI",
        keywords=["AI"],
        summary="同じテーマ",
        model="test-model",
        analyzed_at=datetime.now(),
        importance_reason="最新のAI技術",
        relevance_reason="ユーザーの興味分野",
    )

    # 深掘り結果を保存
    repo.save_deep_research(
        article_id=article_id,
        search_query="AI 検索",
        search_results=[{"title": "結果", "snippet": "スニペット", "url": "http://example.com"}],
        synthesized_content="統合結果",
        sources=[{"url": "http://example.com"}],
        researched_at=datetime.now(),
    )

    # テーマごとに取得
    theme_groups = repo.fetch_deep_research_by_theme(min_articles=1)

    assert "同じテーマ" in theme_groups
    articles = theme_groups["同じテーマ"]
    assert len(articles) == 1
    article = articles[0]
    assert article["article_id"] == article_id
    assert article.get("importance_reason") == "最新のAI技術"
    assert article.get("relevance_reason") == "ユーザーの興味分野"


def test_database_migration_adds_reason_columns(repo: InfoCollectorRepository):
    """データベースマイグレーションで判断理由カラムが追加されることを確認."""
    conn = sqlite3.connect(repo.db_path)
    cursor = conn.execute("PRAGMA table_info(article_analysis)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()

    # 判断理由カラムが存在することを確認
    assert "importance_reason" in columns
    assert "relevance_reason" in columns
    assert columns["importance_reason"] == "TEXT"
    assert columns["relevance_reason"] == "TEXT"

