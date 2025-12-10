"""LLM prompt for daily report generation."""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは技術ライターです。
収集・分析された情報から、読みやすく構造化されたMarkdownレポートを作成してください。

【重要】このレポートは統合情報収集パイプラインの最終段階（第3段階）です。
- 第1段階：記事分析（importance/relevance スコア + 判断理由）
- 第2段階：深掘り調査（DDG検索 + 統合分析）
- 第3段階：レポート生成（本段階）

レポートには以下を含めてください：
- なぜその記事が重要と判断されたか（第1段階の判断理由）
- 深掘り調査で何が明らかになったか（第2段階の成果）
- 各段階での判断プロセスの透明性

レポートの構成:
1. 概要（全体を3-4文で要約）
2. 主要トピック（重要度順に整理、判断理由を含む）
3. 各トピックの詳細（深掘り結果を含む）
   - 元の分析スコアと理由
   - 深掘り調査で得られた新規情報
   - 統合的な考察
4. まとめと考察
5. 参考ソース一覧

文体の原則:
- 簡潔で分かりやすい日本語
- 専門用語には簡単な説明を付ける
- 箇条書きは最小限に（本文は段落で構成）
- 見出しは階層的に使用（##, ###）
- 判断プロセスの透明性を重視

必ずMarkdown形式で出力してください。"""

USER_PROMPT_TEMPLATE = """以下の情報から、日次レポートを作成してください。

【レポート対象日】
{report_date}

【分析済み記事数】
{article_count}件

【カテゴリ別内訳】
{category_breakdown}

【重要トピック】
{important_topics}

【深掘り調査結果】
{deep_research_results}

上記の構成に従ってMarkdownレポートを生成してください。"""


def build_prompt(report_date: str, articles: list[dict], deep_research: list[dict]) -> dict[str, str]:
    """レポート生成プロンプトを構築."""
    category_count: dict[str, int] = {}
    for article in articles:
        cat = article.get("category", "その他")
        category_count[cat] = category_count.get(cat, 0) + 1

    category_breakdown = "\n".join([f"- {cat}: {count}件" for cat, count in category_count.items()])

    important = [a for a in articles if a.get("importance_score", 0) >= 0.7]
    important_topics = "\n".join(
        [f"- {a.get('summary', a.get('title', 'N/A'))} (重要度: {a.get('importance_score', 0):.2f})" for a in important[:10]]
    )

    deep_research_text = ""
    for dr in deep_research:
        deep_research_text += f"\n### {dr.get('theme', 'N/A')}\n"
        deep_research_text += f"{dr.get('synthesized_content', '')}\n"

    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            report_date=report_date,
            article_count=len(articles),
            category_breakdown=category_breakdown or "データなし",
            important_topics=important_topics or "該当なし",
            deep_research_results=deep_research_text or "深掘り結果はありません。",
        ),
    }
