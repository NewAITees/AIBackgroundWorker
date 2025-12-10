"""LLM prompt for synthesizing multiple search results."""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは情報統合の専門家です。
複数の検索結果から重要な情報を抽出し、構造化された要約を作成してください。

【重要】この統合分析は統合情報収集パイプラインの第2段階（深掘り調査）の最終ステップです。
- 第1段階で「高スコア」と判定された記事を、DDG検索で深掘りした結果を統合します
- この結果は第3段階のレポート生成で使用されます
- 元の記事がなぜ重要と判断されたかを踏まえた要約を作成してください

統合の原則:
1. 事実と推測を明確に区別
2. 複数ソースで確認された情報を優先
3. 矛盾する情報は両論併記
4. 出典URLを必ず記録
5. 元の分析スコアを踏まえた統合（なぜ深掘りする価値があったか）

出力形式:
{
    "key_findings": [
        "主要な発見1",
        "主要な発見2",
        "主要な発見3"
    ],
    "detailed_summary": "詳細な要約（200-300文字）",
    "conflicting_info": "矛盾する情報があれば記載",
    "deep_research_value": "この深掘り調査で得られた価値・新規性",
    "sources": [
        {"url": "URL1", "title": "タイトル1", "relevance": "関連度の説明"},
        {"url": "URL2", "title": "タイトル2", "relevance": "関連度の説明"}
    ],
    "confidence_score": 0.0-1.0の範囲で情報の信頼度
}

必ずJSON形式のみを出力してください。"""

USER_PROMPT_TEMPLATE = """以下の検索結果を統合して要約してください。

【元のテーマ】
{theme}

【検索クエリ】
{search_query}

【検索結果】
{search_results}

上記の出力形式に従ってJSON出力してください。"""


def build_prompt(theme: str, search_query: str, search_results: list[dict[str, str]]) -> dict[str, str]:
    """
    検索結果統合プロンプトを構築.

    Args:
        search_results: [{"title": str, "snippet": str, "url": str}, ...]
    """
    results_text = ""
    for i, result in enumerate(search_results[:10], 1):
        results_text += f"\n--- 結果 {i} ---\n"
        results_text += f"タイトル: {result.get('title', 'N/A')}\n"
        results_text += f"要約: {result.get('snippet', 'N/A')}\n"
        results_text += f"URL: {result.get('url', 'N/A')}\n"

    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            theme=theme,
            search_query=search_query,
            search_results=results_text,
        ),
    }
