"""LLM prompt for theme-based report generation."""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは技術ライターです。
特定のテーマに関する深掘り調査結果から、読みやすく構造化されたMarkdownレポートを作成してください。

【重要】このレポートは統合情報収集パイプラインの最終段階（第3段階）で、特定テーマに特化したものです。
- 第1段階：記事分析（importance/relevance スコア + 判断理由）
- 第2段階：深掘り調査（DDG検索 + 統合分析）
- 第3段階：レポート生成（本段階、テーマ特化型）

レポートには以下を含めてください：
- テーマの概要と重要性
- 各記事の分析結果と深掘り調査で得られた知見
- テーマ全体を通じた統合的な考察
- 今後の動向や注目すべきポイント

レポートの構成:
1. テーマ概要（このテーマがなぜ重要か、全体像を3-4文で要約）
2. 主要な発見事項（深掘り調査で明らかになった重要な情報）
3. 各記事の詳細分析
   - 元の記事の要点
   - 深掘り調査で得られた追加情報
   - 重要度・関連度スコアとその理由
4. 統合的な考察（テーマ全体を通じた洞察）
5. 参考ソース一覧（元記事と検索結果のURL）

文体の原則:
- 簡潔で分かりやすい日本語
- 専門用語には簡単な説明を付ける
- 箇条書きは最小限に（本文は段落で構成）
- 見出しは階層的に使用（##, ###）
- 判断プロセスの透明性を重視
- テーマの一貫性を保ち、関連する情報を統合的に記述

必ずMarkdown形式で出力してください。"""

USER_PROMPT_TEMPLATE = """以下のテーマに関する深掘り調査結果から、テーマ特化型レポートを作成してください。

【テーマ】
{theme}

【レポート生成日】
{report_date}

【対象記事数】
{article_count}件

【記事詳細】
{article_details}

【深掘り調査結果】
{deep_research_results}

上記の構成に従って、このテーマに関する包括的なMarkdownレポートを生成してください。"""


def build_prompt(theme: str, articles: list[dict], report_date: str) -> dict[str, str]:
    """
    テーマベースレポート生成プロンプトを構築.
    
    Args:
        theme: テーマ名（summary）
        articles: テーマに関連する深掘り済み記事のリスト
        report_date: レポート生成日
    
    Returns:
        system と user プロンプトを含む辞書
    """
    # 記事詳細をフォーマット
    article_details = ""
    for idx, article in enumerate(articles, 1):
        article_details += f"\n### 記事 {idx}: {article.get('article_title', 'N/A')}\n"
        article_details += f"- **URL**: {article.get('article_url', 'N/A')}\n"
        article_details += f"- **重要度**: {article.get('importance_score', 0):.2f}\n"
        importance_reason = article.get('importance_reason', '') or ''
        if importance_reason:
            article_details += f"  - **判断理由**: {importance_reason}\n"
        article_details += f"- **関連度**: {article.get('relevance_score', 0):.2f}\n"
        relevance_reason = article.get('relevance_reason', '') or ''
        if relevance_reason:
            article_details += f"  - **判断理由**: {relevance_reason}\n"
        article_details += f"- **カテゴリ**: {article.get('category', 'N/A')}\n"
        keywords = article.get('keywords', '[]')
        if isinstance(keywords, str):
            try:
                import json
                keywords = json.loads(keywords)
            except Exception:
                keywords = []
        if keywords:
            article_details += f"- **キーワード**: {', '.join([str(k) for k in keywords[:5]])}\n"
        content = article.get('article_content', '') or article.get('snippet', '')
        if content:
            # 本文の最初の200文字を表示
            article_details += f"- **概要**: {content[:200]}...\n"
    
    # 深掘り調査結果をフォーマット
    deep_research_results = ""
    for idx, article in enumerate(articles, 1):
        synthesized = article.get('synthesized_content', '')
        if synthesized:
            deep_research_results += f"\n### 記事 {idx} の深掘り調査結果\n"
            deep_research_results += f"{synthesized}\n"
            
            # ソース情報
            sources = article.get('sources', '[]')
            if isinstance(sources, str):
                try:
                    import json
                    sources = json.loads(sources)
                except Exception:
                    sources = []
            if sources:
                deep_research_results += "\n**参考ソース**:\n"
                for source in sources[:5]:  # 最大5件
                    url = source.get('url', '') if isinstance(source, dict) else str(source)
                    if url:
                        deep_research_results += f"- {url}\n"
    
    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            theme=theme,
            report_date=report_date,
            article_count=len(articles),
            article_details=article_details or "記事詳細なし",
            deep_research_results=deep_research_results or "深掘り調査結果なし",
        ),
    }
