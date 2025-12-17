"""
統合デイリーレポート生成用LLMプロンプト（実装準備用）

このファイルは実装準備用です。
実装時には実際のプロンプト構築ロジックを実装してください。

設計ドキュメント: docs/INTEGRATED_DAILY_REPORT_DESIGN.md
"""

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは包括的な日次レポート生成アシスタントです。
ユーザーの1日の活動、システムイベント、ブラウザ履歴、情報収集結果を統合して、
読みやすく構造化されたMarkdownレポートを作成してください。

【レポートの目的】
- ユーザーが1日を振り返り、活動パターンや重要な出来事を把握できるようにする
- イベントと活動の相関関係を分析する
- 情報収集結果と実際の活動を関連付ける

【レポート構成】
1. 概要（1日の全体像を3-4文で要約）
2. 時系列サマリー（時間帯別の主要な活動とイベント）
3. 活動パターン分析
   - 時間帯別の活動状況
   - 主なアプリケーション使用状況
   - ブラウザアクセスパターン
4. システムイベント分析
   - 重要なエラーや警告
   - イベントと活動の相関関係
5. 情報収集結果
   - 重要記事の要約
   - 深掘り調査の主要な発見
   - テーマ別の洞察
6. 統合分析
   - 活動と情報収集の関連性
   - 時間帯別のパターン
   - 重要な出来事のまとめ
7. 参考データ一覧

【時間の粒度と意味】
- 各情報のタイムスタンプを統一フォーマット（YYYY-MM-DD HH:MM:SS）で表示
- 時間帯別の活動パターンを可視化（朝/昼/夕方/夜）
- イベントと活動の相関関係を明確に示す

【文体の原則】
- 簡潔で分かりやすい日本語
- 専門用語には簡単な説明を付ける
- 時系列は自然な流れで記述
- 見出しは階層的に使用（##, ###）
- データの出所を明記

必ずMarkdown形式で出力してください。"""

USER_PROMPT_TEMPLATE = """以下の情報から、{report_date}の包括的なデイリーレポートを作成してください。

【ライフログデータ】
{lifelog_summary}

【システムイベント】
{events_summary}

【ブラウザ履歴】
{browser_summary}

【記事分析結果】
{articles_summary}

【深掘り調査結果】
{deep_research_summary}

【テーマレポート】
{theme_reports_summary}

【統合時系列データ】
{timeline_data}

上記の構成に従ってMarkdownレポートを生成してください。"""


def _summarize_lifelog(lifelog_data: list[dict]) -> str:
    """ライフログデータを要約"""
    if not lifelog_data:
        return "データなし"

    from collections import defaultdict
    from datetime import datetime

    # 時間帯別の活動パターン
    hourly_activity = defaultdict(int)
    app_usage = defaultdict(int)
    total_active = 0
    total_idle = 0

    for entry in lifelog_data:
        timestamp_str = entry.get("timestamp") or entry.get("start_ts")
        if timestamp_str:
            try:
                if isinstance(timestamp_str, str):
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    ts = timestamp_str
                hour = ts.hour
                hourly_activity[hour] += entry.get("duration_seconds", 0)
            except (ValueError, AttributeError):
                pass

        process_name = entry.get("process_name", "Unknown")
        duration = entry.get("duration_seconds", 0)
        app_usage[process_name] += duration

        if entry.get("is_idle"):
            total_idle += duration
        else:
            total_active += duration

    # サマリー構築
    summary = f"ライフログデータ: {len(lifelog_data)} 件のインターバル\n\n"
    summary += f"総活動時間: {total_active // 3600}時間{(total_active % 3600) // 60}分\n"
    summary += f"総アイドル時間: {total_idle // 3600}時間{(total_idle % 3600) // 60}分\n\n"

    # 主なアプリケーション使用状況（上位5件）
    top_apps = sorted(app_usage.items(), key=lambda x: x[1], reverse=True)[:5]
    summary += "主なアプリケーション使用状況:\n"
    for app, seconds in top_apps:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        summary += f"- {app}: {hours}時間{minutes}分\n"

    return summary


def _summarize_events(events: list[dict], top_n: int = 10) -> str:
    """イベント情報を要約"""
    if not events:
        return "イベントなし"

    # 重要度順にソート
    sorted_events = sorted(events, key=lambda x: x.get("severity", 0), reverse=True)
    top_events = sorted_events[:top_n]

    summary = f"合計 {len(events)} 件のイベント（重要度上位 {top_n} 件）\n\n"
    for event in top_events:
        summary += f"- [{event.get('event_type', 'unknown')}] {event.get('message', '')[:100]} (重要度: {event.get('severity', 0)})\n"

    return summary


def _summarize_browser(browser_history: list[dict], top_n: int = 20) -> str:
    """ブラウザ履歴を要約"""
    if not browser_history:
        return "ブラウザ履歴なし"

    from collections import defaultdict
    from datetime import datetime
    from urllib.parse import urlparse

    # 時間帯別アクセス
    hourly_access = defaultdict(int)
    domain_counts = defaultdict(int)

    for entry in browser_history:
        visit_time_str = entry.get("visit_time")
        if visit_time_str:
            try:
                if isinstance(visit_time_str, str):
                    ts = datetime.fromisoformat(visit_time_str.replace("Z", "+00:00"))
                else:
                    ts = visit_time_str
                hour = ts.hour
                hourly_access[hour] += 1
            except (ValueError, AttributeError):
                pass

        # ドメイン別集計
        url = entry.get("url", "")
        if url:
            try:
                domain = urlparse(url).netloc
                if domain:
                    domain_counts[domain] += 1
            except Exception:
                pass

    # サマリー構築
    summary = f"ブラウザ履歴: {len(browser_history)} 件\n\n"

    # ドメイン別集計（上位10件）
    top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    if top_domains:
        summary += "アクセスが多いドメイン:\n"
        for domain, count in top_domains:
            summary += f"- {domain}: {count}回\n"

    return summary


def _summarize_articles(articles: list[dict], top_n: int = 5) -> str:
    """記事分析結果を要約"""
    if not articles:
        return "記事分析結果なし"

    # 重要度順にソート
    sorted_articles = sorted(articles, key=lambda x: x.get("importance_score", 0), reverse=True)
    top_articles = sorted_articles[:top_n]

    summary = f"分析済み記事 {len(articles)} 件（重要度上位 {top_n} 件）\n\n"
    for article in top_articles:
        summary += (
            f"- {article.get('title', 'N/A')} (重要度: {article.get('importance_score', 0):.2f})\n"
        )
        summary += f"  {article.get('summary', '')[:200]}...\n\n"

    return summary


def _summarize_deep_research(deep_research: list[dict], top_n: int = 3) -> str:
    """深掘り調査結果を要約"""
    if not deep_research:
        return "深掘り調査結果なし"

    summary = f"深掘り調査 {len(deep_research)} 件\n\n"
    for research in deep_research[:top_n]:
        summary += f"### {research.get('theme', 'N/A')}\n"
        summary += f"{research.get('synthesized_content', '')[:300]}...\n\n"

    return summary


def _format_theme_reports(theme_reports: list[dict]) -> str:
    """テーマレポートをフォーマット"""
    if not theme_reports:
        return "テーマレポートなし"

    summary = f"テーマレポート {len(theme_reports)} 件\n\n"
    for report in theme_reports:
        summary += f"- {report.get('title', 'N/A')}\n"

    return summary


def _summarize_timeline(timeline: list, top_n: int = 30) -> str:
    """
    統合時系列データを要約

    Args:
        timeline: UnifiedTimelineEntryのリストまたはdictのリスト
        top_n: 要約する件数

    Returns:
        要約テキスト
    """
    if not timeline:
        return "時系列データなし"

    # UnifiedTimelineEntry (dataclass) を dict に変換
    timeline_dicts = []
    for entry in timeline:
        if hasattr(entry, "timestamp"):  # dataclassの場合
            timeline_dicts.append(
                {
                    "timestamp": entry.timestamp.isoformat()
                    if hasattr(entry.timestamp, "isoformat")
                    else str(entry.timestamp),
                    "source_type": entry.source_type,
                    "title": entry.title,
                    "category": entry.category,
                    "description": entry.description[:100] if entry.description else "",
                    "importance_score": entry.importance_score,
                }
            )
        else:  # dictの場合
            timeline_dicts.append(entry)

    # 時系列でソート済みと仮定
    summary = f"時系列エントリ {len(timeline_dicts)} 件（主要 {top_n} 件）\n\n"
    for entry in timeline_dicts[:top_n]:
        timestamp = _format_timestamp(entry.get("timestamp"))
        source = entry.get("source_type", "unknown")
        title = entry.get("title", "N/A")[:50]
        category = entry.get("category", "")
        summary += f"- {timestamp} [{source}] {title}"
        if category:
            summary += f" ({category})"
        summary += "\n"

    return summary


def build_integrated_prompt(
    report_date: str,
    lifelog_data: list[dict],
    events: list[dict],
    browser_history: list[dict],
    article_analyses: list[dict],
    deep_research: list[dict],
    theme_reports: list[dict],
    timeline: list,  # UnifiedTimelineEntryのリストまたはdictのリスト
    detail_level: str = "summary",  # 'summary', 'detailed', 'full'
) -> dict[str, str]:
    """
    統合レポート生成プロンプトを構築

    Args:
        report_date: レポート対象日（YYYY-MM-DD）
        lifelog_data: ライフログデータ
        events: システムイベント
        browser_history: ブラウザ履歴
        article_analyses: 記事分析結果
        deep_research: 深掘り調査結果
        theme_reports: テーマレポート
        timeline: 統合時系列データ
        detail_level: 詳細度（'summary', 'detailed', 'full'）

    Returns:
        プロンプト辞書（'system' と 'user' キーを含む）
    """
    # 詳細度に応じてデータを要約
    if detail_level == "summary":
        lifelog_summary = _summarize_lifelog(lifelog_data)
        events_summary = _summarize_events(events, top_n=10)
        browser_summary = _summarize_browser(browser_history, top_n=20)
        articles_summary = _summarize_articles(article_analyses, top_n=5)
        deep_research_summary = _summarize_deep_research(deep_research, top_n=3)
        timeline_data = _summarize_timeline(timeline, top_n=30)
    elif detail_level == "detailed":
        # より詳細な情報を含める
        lifelog_summary = _summarize_lifelog(lifelog_data)
        events_summary = _summarize_events(events, top_n=20)
        browser_summary = _summarize_browser(browser_history, top_n=50)
        articles_summary = _summarize_articles(article_analyses, top_n=10)
        deep_research_summary = _summarize_deep_research(deep_research, top_n=5)
        timeline_data = _summarize_timeline(timeline, top_n=100)
    else:  # full
        # すべての情報を含める（要約なし）
        lifelog_summary = str(lifelog_data)
        events_summary = str(events)
        browser_summary = str(browser_history)
        articles_summary = str(article_analyses)
        deep_research_summary = str(deep_research)
        timeline_data = str(timeline)

    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            report_date=report_date,
            lifelog_summary=lifelog_summary,
            events_summary=events_summary,
            browser_summary=browser_summary,
            articles_summary=articles_summary,
            deep_research_summary=deep_research_summary,
            theme_reports_summary=_format_theme_reports(theme_reports),
            timeline_data=timeline_data,
        ),
    }


def _format_timestamp(value: object) -> str:
    """datetime/str をISO文字列に揃える."""
    if value is None:
        return ""
    try:
        from datetime import datetime

        if isinstance(value, datetime):
            return value.isoformat()
        return datetime.fromisoformat(str(value)).isoformat()
    except Exception:
        return str(value)
