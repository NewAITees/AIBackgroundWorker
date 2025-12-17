"""LLM prompt for generating search queries."""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは検索の専門家です。
与えられたテーマから、DuckDuckGo検索で関連性の高い情報を得られるクエリを生成してください。

【重要】この検索クエリは統合情報収集パイプラインの第2段階です。
- 第1段階の分析で「重要度・関連度が高い」と判定された記事が対象です
- 前段階で得られた判断理由を活用し、深掘りすべきポイントを明確にしてください
- 検索結果は第3段階の統合分析で使用され、最終レポートに含まれます
- **重要**: 元の記事と直接関連する情報を見つけることが目的です。全く関係ない情報を検索しないでください

クエリ設計の原則:
1. **元の記事のテーマ・キーワードを必ず含める**（最重要）
2. 簡潔で具体的（3-8ワード、長すぎると検索精度が下がる）
3. 専門用語と一般用語のバランス
4. 日本語記事が対象なら日本語クエリ、英語なら英語クエリ
5. 複数の角度から調査するため、2-4個のクエリを生成
6. 前段階の判断理由を踏まえた検索クエリを優先
7. **抽象的なクエリは避け、具体的なトピックやキーワードを含める**
8. **元の記事の内容と無関係な一般的な検索は避ける**

悪い例:
- 「最新ニュース」（抽象的すぎる）
- 「技術情報」（広すぎる）
- 「AI」（単語のみ、文脈がない）

良い例:
- 「AI 生成モデル 最新動向 2025」（具体的で文脈がある）
- 「記事タイトルの主要キーワード + 深掘りポイント」（元の記事と関連）

出力形式:
{
    "queries": [
        {"query": "検索クエリ1", "purpose": "この検索の目的（元の記事のどの点を深掘りするか）"},
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

【重要度判断理由】
{importance_reason}

【関連度判断理由】
{relevance_reason}

【深掘りすべきポイント】
上記の判断理由を踏まえ、以下の観点から深掘りすべきポイントを特定してください：
1. 元の記事の主張を裏付ける証拠やデータ
2. 関連する学術論文や公式発表
3. 業界専門家の見解や分析
4. 類似事例や比較対象
5. 今後の動向や影響

【重要な注意事項】
- 検索クエリには必ず元の記事のテーマやキーワードを含めてください
- 元の記事と無関係な一般的な検索は避けてください
- 各クエリは元の記事の特定の側面を深掘りするためのものである必要があります
- 抽象的すぎるクエリ（例：「ニュース」「情報」）は生成しないでください

上記の出力形式に従ってJSON出力してください。"""


def build_prompt(
    theme: str,
    keywords: list[str],
    category: str,
    summary: str,
    importance_reason: str = "",
    relevance_reason: str = "",
) -> dict[str, str]:
    """
    検索クエリ生成プロンプトを構築.
    
    Args:
        theme: テーマ
        keywords: キーワードリスト
        category: カテゴリ
        summary: 記事要約
        importance_reason: 重要度の判断理由（オプション）
        relevance_reason: 関連度の判断理由（オプション）
    """
    keywords_str = ", ".join(keywords)
    # 判断理由が空の場合はデフォルトメッセージを使用
    importance_reason_display = importance_reason or "判断理由が記録されていません"
    relevance_reason_display = relevance_reason or "判断理由が記録されていません"
    
    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            theme=theme,
            keywords=keywords_str,
            category=category,
            summary=summary,
            importance_reason=importance_reason_display,
            relevance_reason=relevance_reason_display,
        ),
    }
