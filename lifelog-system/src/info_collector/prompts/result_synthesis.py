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

【元の記事の要点】
{article_summary}

【重要度・関連度スコア】
- 重要度: {importance_score} ({importance_reason})
- 関連度: {relevance_score} ({relevance_reason})

【検索クエリ】
{search_query}

【検索結果】
{search_results}

【統合の観点】
1. 検索結果が元の記事の主張を裏付けるかどうか
2. 元の記事で不足していた情報が補完されているか
3. 検索結果と元の記事の間に矛盾がないか
4. 深掘り調査で得られた新規性や価値

上記の出力形式に従ってJSON出力してください。"""


def build_prompt(
    theme: str,
    search_query: str,
    search_results: list[dict[str, str]],
    article_summary: str = "",
    importance_score: float = 0.0,
    relevance_score: float = 0.0,
    importance_reason: str = "",
    relevance_reason: str = "",
) -> dict[str, str]:
    """
    検索結果統合プロンプトを構築.

    Args:
        theme: テーマ
        search_query: 検索クエリ
        search_results: [{"title": str, "snippet": str, "url": str}, ...]
        article_summary: 元の記事の要約（オプション）
        importance_score: 重要度スコア（オプション）
        relevance_score: 関連度スコア（オプション）
        importance_reason: 重要度の判断理由（オプション）
        relevance_reason: 関連度の判断理由（オプション）
    """
    results_text = ""
    for i, result in enumerate(search_results[:10], 1):
        results_text += f"\n--- 結果 {i} ---\n"
        results_text += f"タイトル: {result.get('title', 'N/A')}\n"
        results_text += f"要約: {result.get('snippet', 'N/A')}\n"
        results_text += f"URL: {result.get('url', 'N/A')}\n"

    # デフォルト値の設定
    article_summary_display = article_summary or "記事要約が記録されていません"
    importance_reason_display = importance_reason or "判断理由が記録されていません"
    relevance_reason_display = relevance_reason or "判断理由が記録されていません"

    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            theme=theme,
            article_summary=article_summary_display,
            importance_score=importance_score,
            relevance_score=relevance_score,
            importance_reason=importance_reason_display,
            relevance_reason=relevance_reason_display,
            search_query=search_query,
            search_results=results_text,
        ),
    }
