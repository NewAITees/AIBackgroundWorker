"""
プロンプト生成関数で判断理由が正しく含まれることを確認するテスト
"""

import pytest

from src.info_collector.prompts import search_query_gen, result_synthesis, theme_report


def test_search_query_gen_includes_reasons():
    """search_query_gen.build_prompt()で判断理由がプロンプトに含まれることを確認."""
    prompt = search_query_gen.build_prompt(
        theme="AI技術の最新動向",
        keywords=["AI", "LLM"],
        category="AI",
        summary="AI技術に関する記事",
        importance_reason="重要な技術動向",
        relevance_reason="ユーザーの興味分野と関連",
    )

    assert "system" in prompt
    assert "user" in prompt
    user_prompt = prompt["user"]
    
    # 判断理由が含まれていることを確認
    assert "重要な技術動向" in user_prompt
    assert "ユーザーの興味分野と関連" in user_prompt
    assert "重要度判断理由" in user_prompt
    assert "関連度判断理由" in user_prompt
    assert "深掘りすべきポイント" in user_prompt


def test_search_query_gen_without_reasons():
    """判断理由なしでsearch_query_gen.build_prompt()を呼び出した場合、デフォルトメッセージが使用されることを確認."""
    prompt = search_query_gen.build_prompt(
        theme="AI技術の最新動向",
        keywords=["AI", "LLM"],
        category="AI",
        summary="AI技術に関する記事",
    )

    assert "system" in prompt
    assert "user" in prompt
    user_prompt = prompt["user"]
    
    # デフォルトメッセージが含まれていることを確認
    assert "判断理由が記録されていません" in user_prompt


def test_result_synthesis_includes_reasons():
    """result_synthesis.build_prompt()で判断理由がプロンプトに含まれることを確認."""
    search_results = [
        {"title": "結果1", "snippet": "スニペット1", "url": "http://example.com/1"},
        {"title": "結果2", "snippet": "スニペット2", "url": "http://example.com/2"},
    ]

    prompt = result_synthesis.build_prompt(
        theme="AI技術の最新動向",
        search_query="AI 検索",
        search_results=search_results,
        article_summary="AI技術に関する記事の要約",
        importance_score=0.85,
        relevance_score=0.90,
        importance_reason="重要な技術動向",
        relevance_reason="ユーザーの興味分野と関連",
    )

    assert "system" in prompt
    assert "user" in prompt
    user_prompt = prompt["user"]
    
    # 判断理由が含まれていることを確認
    assert "重要な技術動向" in user_prompt
    assert "ユーザーの興味分野と関連" in user_prompt
    assert "重要度・関連度スコア" in user_prompt
    assert "統合の観点" in user_prompt
    assert "0.85" in user_prompt
    assert "0.9" in user_prompt or "0.90" in user_prompt


def test_result_synthesis_without_reasons():
    """判断理由なしでresult_synthesis.build_prompt()を呼び出した場合、デフォルトメッセージが使用されることを確認."""
    search_results = [
        {"title": "結果1", "snippet": "スニペット1", "url": "http://example.com/1"},
    ]

    prompt = result_synthesis.build_prompt(
        theme="AI技術の最新動向",
        search_query="AI 検索",
        search_results=search_results,
    )

    assert "system" in prompt
    assert "user" in prompt
    user_prompt = prompt["user"]
    
    # デフォルトメッセージが含まれていることを確認
    assert "判断理由が記録されていません" in user_prompt


def test_theme_report_includes_reasons():
    """theme_report.build_prompt()で判断理由がプロンプトに含まれることを確認."""
    articles = [
        {
            "article_title": "記事1",
            "article_url": "http://example.com/1",
            "importance_score": 0.85,
            "relevance_score": 0.90,
            "importance_reason": "重要な技術動向",
            "relevance_reason": "ユーザーの興味分野と関連",
            "category": "AI",
            "keywords": '["AI", "LLM"]',
            "article_content": "記事の内容",
        },
    ]

    prompt = theme_report.build_prompt(
        theme="AI技術の最新動向",
        articles=articles,
        report_date="2025-12-11",
    )

    assert "system" in prompt
    assert "user" in prompt
    user_prompt = prompt["user"]
    
    # 判断理由が含まれていることを確認
    assert "重要な技術動向" in user_prompt
    assert "ユーザーの興味分野と関連" in user_prompt
    assert "判断理由" in user_prompt


def test_theme_report_without_reasons():
    """判断理由なしでtheme_report.build_prompt()を呼び出した場合、エラーにならないことを確認."""
    articles = [
        {
            "article_title": "記事1",
            "article_url": "http://example.com/1",
            "importance_score": 0.85,
            "relevance_score": 0.90,
            "category": "AI",
            "keywords": '["AI", "LLM"]',
            "article_content": "記事の内容",
        },
    ]

    prompt = theme_report.build_prompt(
        theme="AI技術の最新動向",
        articles=articles,
        report_date="2025-12-11",
    )

    assert "system" in prompt
    assert "user" in prompt
    # 判断理由がなくてもエラーにならないことを確認
    assert "記事1" in prompt["user"]

