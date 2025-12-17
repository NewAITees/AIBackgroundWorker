"""LLM prompt for daily report generation."""

from __future__ import annotations

from typing import Optional

__version__ = "1.0.0"

SYSTEM_PROMPT = """あなたは技術ライターです。
収集・分析された情報とユーザーの日々の活動データから、読みやすく構造化されたMarkdownレポートを作成してください。

【重要】このレポートは統合情報収集パイプラインの最終段階（第3段階）です。
- 第1段階：記事分析（importance/relevance スコア + 判断理由）
- 第2段階：深掘り調査（DDG検索 + 統合分析）
- 第3段階：レポート生成（本段階）

レポートには以下を含めてください：
- なぜその記事が重要と判断されたか（第1段階の判断理由）
- 深掘り調査で何が明らかになったか（第2段階の成果）
- 各段階での判断プロセスの透明性
- **ユーザーの日々の活動状況**（ライフログデータ、ブラウザ履歴、システムイベントが提供されている場合）

レポートの構成:
1. 概要（全体を3-4文で要約、活動状況も含める）
2. 日々の活動サマリー（ライフログデータが提供されている場合）
   - 時間帯別の活動パターン（重複除外後の時間を表示）
   - Windows環境とWSL環境の区別（両方が動作している場合は明示）
   - 主なアプリケーション使用状況（環境別に分けて表示）
   - ブラウザアクセスパターン
   - システムイベント（エラー、警告など）
   - **重要**: WindowsとWSLが同時に動作している場合、活動時間が重複するため、重複除外後の時間を表示すること
3. 主要トピック（重要度順に整理、判断理由を含む）
4. 各トピックの詳細（深掘り結果を含む）
   - 元の分析スコアと理由
   - 深掘り調査で得られた新規情報
   - **参考URL**（深掘り調査で取得したURLを必ず含める）
   - 統合的な考察
5. 活動と情報収集の関連性（活動データが提供されている場合）
   - どの時間帯にどのような情報を収集したか
   - 活動パターンと情報収集の相関関係
6. まとめと考察
7. 参考ソース一覧（**URLを必ず含める**）

文体の原則:
- 簡潔で分かりやすい日本語
- 専門用語には簡単な説明を付ける
- 箇条書きは最小限に（本文は段落で構成）
- 見出しは階層的に使用（##, ###）
- 判断プロセスの透明性を重視
- 活動データと情報収集結果を統合的に分析

必ずMarkdown形式で出力してください。"""

USER_PROMPT_TEMPLATE = """以下の情報から、日次レポートを作成してください。

【レポート対象日】
{report_date}

【日々の活動データ】
{lifelog_summary}

【ブラウザ履歴】
{browser_summary}

【システムイベント】
{events_summary}

【分析済み記事数】
{article_count}件

【カテゴリ別内訳】
{category_breakdown}

【重要トピック】
{important_topics}

【深掘り調査結果】
{deep_research_results}

上記の構成に従ってMarkdownレポートを生成してください。
活動データが提供されている場合は、活動パターンと情報収集結果の関連性も分析してください。"""


def build_prompt(
    report_date: str,
    articles: list[dict],
    deep_research: list[dict],
    lifelog_data: Optional[list[dict]] = None,
    browser_history: Optional[list[dict]] = None,
    events: Optional[list[dict]] = None,
) -> dict[str, str]:
    """レポート生成プロンプトを構築."""
    category_count: dict[str, int] = {}
    for article in articles:
        cat = article.get("category", "その他")
        category_count[cat] = category_count.get(cat, 0) + 1

    category_breakdown = "\n".join([f"- {cat}: {count}件" for cat, count in category_count.items()])

    important = [a for a in articles if a.get("importance_score", 0) >= 0.7]
    important_topics = "\n".join(
        [
            f"- {a.get('summary', a.get('title', 'N/A'))} (重要度: {a.get('importance_score', 0):.2f})"
            for a in important[:10]
        ]
    )

    deep_research_text = ""
    for dr in deep_research:
        theme = dr.get("theme", "N/A")
        synthesized = dr.get("synthesized_content", "")

        # URLを抽出（search_resultsとsourcesから）
        urls = []
        try:
            import json

            # search_resultsからURLを抽出
            search_results_str = dr.get("search_results", "[]")
            if isinstance(search_results_str, str):
                search_results = json.loads(search_results_str)
            else:
                search_results = search_results_str or []

            for result in search_results[:5]:  # 上位5件
                if isinstance(result, dict) and result.get("url"):
                    urls.append(result["url"])

            # sourcesからURLを抽出
            sources_str = dr.get("sources", "[]")
            if isinstance(sources_str, str):
                sources = json.loads(sources_str)
            else:
                sources = sources_str or []

            for source in sources[:5]:  # 上位5件
                if isinstance(source, dict) and source.get("url"):
                    if source["url"] not in urls:  # 重複を避ける
                        urls.append(source["url"])
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

        deep_research_text += f"\n### {theme}\n"
        deep_research_text += f"{synthesized}\n"
        if urls:
            deep_research_text += "\n**参考URL:**\n"
            for url in urls[:10]:  # 最大10件
                deep_research_text += f"- {url}\n"

    # ライフログデータの要約
    lifelog_summary = "データなし"
    if lifelog_data:
        from collections import defaultdict
        from datetime import datetime

        # Windows/WSLの区別（process_nameで判断）
        # WSL特有のプロセス: wsl, bash, zsh, sh, python (WSL環境), uv, rsync, docker (WSL内), etc.
        # Windows特有のプロセス: explorer.exe, chrome.exe, brave.exe, StartMenu, etc.
        wsl_processes = {
            "wsl",
            "bash",
            "zsh",
            "sh",
            "fish",
            "uv",
            "python3",
            "python",
            "rsync",
            "docker",
        }
        windows_processes = {
            ".exe",
            "explorer",
            "brave",
            "chrome",
            "claude",
            "cursor",
            "startmenu",
            "obs64",
            "steam",
            "duckov",
            "neeview",
        }

        hourly_activity = defaultdict(int)
        app_usage = defaultdict(int)
        wsl_app_usage = defaultdict(int)
        windows_app_usage = defaultdict(int)
        total_active = 0
        wsl_active = 0
        windows_active = 0

        # 重複時間を考慮した集計（時間帯ごとに最大値を取る）
        time_slots = {}  # {(hour, minute_slot): max_duration}

        for entry in lifelog_data:
            timestamp_str = entry.get("timestamp") or entry.get("start_ts")
            process_name = entry.get("process_name", "Unknown")
            duration = entry.get("duration_seconds", 0)
            is_idle = entry.get("is_idle", False)

            if timestamp_str:
                try:
                    if isinstance(timestamp_str, str):
                        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    else:
                        ts = timestamp_str
                    hour = ts.hour
                    minute_slot = (ts.minute // 15) * 15  # 15分単位でスロット化
                    slot_key = (hour, minute_slot)

                    if not is_idle:
                        # 重複時間を考慮：同じ時間スロットで最大値を保持
                        if slot_key not in time_slots or duration > time_slots[slot_key]:
                            time_slots[slot_key] = duration
                        hourly_activity[hour] += duration
                except (ValueError, AttributeError):
                    pass

            app_usage[process_name] += duration

            # Windows/WSLの区別
            process_lower = process_name.lower()
            # WSL判定: WSL特有のプロセス名を含む、かつ.exeがついていない
            is_wsl = any(
                wsl_proc in process_lower for wsl_proc in wsl_processes
            ) and not process_name.endswith(".exe")
            # Windows判定: .exeがついている、またはWindows特有のプロセス名を含む
            is_windows = process_name.endswith(".exe") or any(
                proc in process_lower for proc in windows_processes
            )

            if not is_idle:
                total_active += duration
                if is_wsl:
                    wsl_app_usage[process_name] += duration
                    wsl_active += duration
                elif is_windows:
                    windows_app_usage[process_name] += duration
                    windows_active += duration
                else:
                    # どちらでもない場合は、process_nameから推測
                    # デフォルトではWindowsとして扱う（.exeがない場合もWindowsアプリの可能性）
                    if "docker" in process_lower or "wsl" in process_lower:
                        wsl_app_usage[process_name] += duration
                        wsl_active += duration
                    else:
                        # その他はWindowsとして扱う
                        windows_app_usage[process_name] += duration
                        windows_active += duration

        # 重複を考慮した実際の活動時間（15分スロットの合計）
        deduplicated_active = sum(time_slots.values())

        # 時間帯別の集計（重複考慮後）
        morning_active = sum(d for (h, _), d in time_slots.items() if 6 <= h < 12)
        day_active = sum(d for (h, _), d in time_slots.items() if 12 <= h < 18)
        evening_active = sum(d for (h, _), d in time_slots.items() if 18 <= h < 22)
        night_active = sum(d for (h, _), d in time_slots.items() if h >= 22 or h < 6)

        lifelog_summary = f"ライフログデータ: {len(lifelog_data)} 件のインターバル\n"
        lifelog_summary += (
            f"総活動時間（重複除外後）: {deduplicated_active // 3600}時間{(deduplicated_active % 3600) // 60}分\n"
        )
        if wsl_active > 0 or windows_active > 0:
            lifelog_summary += f"  - WSL環境: {wsl_active // 3600}時間{(wsl_active % 3600) // 60}分\n"
            lifelog_summary += (
                f"  - Windows環境: {windows_active // 3600}時間{(windows_active % 3600) // 60}分\n"
            )
            if wsl_active > 0 and windows_active > 0:
                lifelog_summary += "  ※ WindowsとWSLが同時に動作しているため、重複時間を除外して集計しています\n"
        lifelog_summary += f"主なアプリケーション: {', '.join([f'{k} ({v//60}分)' for k, v in sorted(app_usage.items(), key=lambda x: x[1], reverse=True)[:5]])}\n"
        if wsl_app_usage or windows_app_usage:
            if wsl_app_usage:
                top_wsl = sorted(wsl_app_usage.items(), key=lambda x: x[1], reverse=True)[:3]
                lifelog_summary += (
                    f"  - WSL主要アプリ: {', '.join([f'{k} ({v//60}分)' for k, v in top_wsl])}\n"
                )
            if windows_app_usage:
                top_windows = sorted(windows_app_usage.items(), key=lambda x: x[1], reverse=True)[
                    :3
                ]
                lifelog_summary += (
                    f"  - Windows主要アプリ: {', '.join([f'{k} ({v//60}分)' for k, v in top_windows])}\n"
                )
        lifelog_summary += f"時間帯別活動（重複除外後）: 朝({morning_active//3600}時間), 昼({day_active//3600}時間), 夕方({evening_active//3600}時間), 夜({night_active//3600}時間)"

    # ブラウザ履歴の要約
    browser_summary = "データなし"
    if browser_history:
        from collections import defaultdict

        domain_count = defaultdict(int)
        for entry in browser_history:
            url = entry.get("url", "")
            if url:
                try:
                    from urllib.parse import urlparse

                    domain = urlparse(url).netloc
                    domain_count[domain] += 1
                except Exception:
                    pass

        browser_summary = f"ブラウザ履歴: {len(browser_history)} 件\n"
        browser_summary += f"主なアクセス先: {', '.join([f'{k} ({v}回)' for k, v in sorted(domain_count.items(), key=lambda x: x[1], reverse=True)[:10]])}"

    # イベントの要約
    events_summary = "データなし"
    if events:
        events_summary = f"システムイベント: {len(events)} 件\n"
        for event in events[:10]:
            event_type = event.get("event_type", "Unknown")
            severity = event.get("severity", "Unknown")
            message = event.get("message", "")[:100]
            events_summary += f"- [{severity}] {event_type}: {message}\n"

    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            report_date=report_date,
            lifelog_summary=lifelog_summary,
            browser_summary=browser_summary,
            events_summary=events_summary,
            article_count=len(articles),
            category_breakdown=category_breakdown or "データなし",
            important_topics=important_topics or "該当なし",
            deep_research_results=deep_research_text or "深掘り結果はありません。",
        ),
    }
