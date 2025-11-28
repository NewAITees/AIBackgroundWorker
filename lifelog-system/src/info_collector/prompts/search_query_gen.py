"""LLM prompt for generating search queries."""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは検索の専門家です。
与えられたテーマから、DuckDuckGo検索で関連性の高い情報を得られるクエリを生成してください。

クエリ設計の原則:
1. 簡潔で具体的（3-6ワード）
2. 専門用語と一般用語のバランス
3. 日本語記事が対象なら日本語クエリ、英語なら英語クエリ
4. 複数の角度から調査するため、2-3個のクエリを生成

出力形式:
{
    "queries": [
        {"query": "検索クエリ1", "purpose": "この検索の目的"},
        {"query": "検索クエリ2", "purpose": "この検索の目的"}
    ],
    "language": "ja" | "en"
}

必ずJSON形式のみを出力してください。"""

USER_PROMPT_TEMPLATE = """以下のテーマについて、深掘り調査用の検索クエリを生成してください。

【テーマ】
{theme}

【キーワード】
{keywords}

【カテゴリ】
{category}

【記事要約】
{summary}

上記の出力形式に従ってJSON出力してください。"""


def build_prompt(theme: str, keywords: list[str], category: str, summary: str) -> dict[str, str]:
    """検索クエリ生成プロンプトを構築."""
    keywords_str = ", ".join(keywords)
    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            theme=theme,
            keywords=keywords_str,
            category=category,
            summary=summary,
        ),
    }
