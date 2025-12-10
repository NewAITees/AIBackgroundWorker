"""LLM prompt for theme extraction and importance scoring."""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは情報分析の専門家です。
ニュース記事を分析し、以下の形式で構造化されたJSON出力を生成してください。

【重要】この分析結果は統合情報収集パイプラインの第1段階です。
- 高スコア記事は後続の深掘り調査（DDG検索+統合分析）で使用されます
- 最終的に日次レポートに統合されるため、判断理由を明確にしてください

出力形式:
{
    "theme": "記事の主要テーマ（1文で簡潔に）",
    "keywords": ["キーワード1", "キーワード2", "キーワード3"],
    "category": "AI" | "投資" | "ゲーム" | "日本政治" | "その他",
    "importance_score": 0.0-1.0の範囲で重要度を評価,
    "importance_reason": "スコアの判断理由（簡潔に）",
    "relevance_score": 0.0-1.0の範囲でユーザー興味との関連度,
    "relevance_reason": "関連度の判断理由（簡潔に）",
    "one_line_summary": "1行要約（40文字以内）",
    "should_deep_research": true | false
}

判定基準:
- importance_score: 独自性、影響範囲、時事性を総合評価
- relevance_score: ユーザーの興味分野との一致度
- should_deep_research: importance_score >= 0.7 かつ relevance_score >= 0.6 の場合true
- importance_reason / relevance_reason: 後続の深掘り調査で検索クエリ生成に活用

必ずJSON形式のみを出力してください。説明文は不要です。"""

USER_PROMPT_TEMPLATE = """以下の記事を分析してください。

【ユーザーの興味分野】
- AI・機械学習（特にLLM、生成AI、AI活用事例）
- 投資・暗号資産（市場動向、投資戦略）
- ゲーム（ストーリー重視の作品、ゲーム業界動向）
- 日本の政治・文化（政策、社会問題）

【記事情報】
タイトル: {title}
本文: {content}
公開日: {published_at}

上記の出力形式に従ってJSON出力してください。"""


def build_prompt(title: str, content: str, published_at: str) -> dict[str, str]:
    """
    テーマ抽出プロンプトを構築.

    Returns:
        {"system": str, "user": str}
    """
    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            title=title,
            content=content[:2000],  # 長文は先頭のみ使用
            published_at=published_at,
        ),
    }
