"""Generate Markdown report from recent analysis/deep-research results."""

from __future__ import annotations

import argparse
import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.prompts import report_generation
from src.info_collector.repository import InfoCollectorRepository
from src.info_collector.data_aggregator import DailyReportDataAggregator

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data/ai_secretary.db")
DEFAULT_LIFELOG_DB = Path("data/lifelog.db")
DEFAULT_YELLOWMABLE_DIR = Path(os.getenv("YELLOWMABLE_DIR", "/mnt/c/YellowMable"))
DEFAULT_REPORT_DIR = DEFAULT_YELLOWMABLE_DIR / "00_Raw"
MIN_REPORT_CHARS = 800


def _fmt_seconds(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}時間{minutes}分"


def _build_fallback_report(
    report_date: str,
    analyses: list[dict],
    deep: list[dict],
    lifelog_data: Optional[list[dict]],
    browser_history: Optional[list[dict]],
    events: Optional[list[dict]],
) -> str:
    """LLM失敗時の最低品質を担保する構造化レポートを生成する."""
    lines = [
        f"# {report_date} 情報収集レポート（フォールバック）",
        "",
        "## 概要",
        "LLM応答が不安定だったため、収集済みデータから自動で構造化したレポートを出力しています。",
        "",
    ]

    lines.extend(
        [
            "## 収集データ件数",
            f"- 分析記事: {len(analyses)}件",
            f"- 深掘り調査: {len(deep)}件",
            f"- ライフログ: {len(lifelog_data or [])}件",
            f"- ブラウザ履歴: {len(browser_history or [])}件",
            f"- イベント: {len(events or [])}件",
            "",
        ]
    )

    if analyses:
        category_counter = Counter(a.get("category", "その他") for a in analyses)
        lines.append("## 主要カテゴリ")
        for cat, count in category_counter.most_common(8):
            lines.append(f"- {cat}: {count}件")
        lines.append("")

        lines.append("## 重要トピック")
        important = sorted(analyses, key=lambda a: a.get("importance_score", 0), reverse=True)[:8]
        for item in important:
            title = item.get("title") or item.get("summary") or "N/A"
            importance = item.get("importance_score", 0)
            relevance = item.get("relevance_score", 0)
            lines.append(f"- {title}（重要度 {importance:.2f} / 関連度 {relevance:.2f}）")
        lines.append("")

    if deep:
        lines.append("## 深掘り調査の要点")
        for item in deep[:6]:
            theme = item.get("theme", "N/A")
            summary = (item.get("synthesized_content") or "").strip()
            if len(summary) > 180:
                summary = summary[:180] + "..."
            lines.append(f"### {theme}")
            lines.append(summary or "要約なし")
            lines.append("")

    if lifelog_data:
        active_seconds = sum(
            int(e.get("duration_seconds", 0) or 0) for e in lifelog_data if not e.get("is_idle")
        )
        app_counter = Counter(e.get("process_name", "unknown") for e in lifelog_data)
        lines.extend(
            [
                "## 活動サマリー",
                f"- アクティブ時間（概算）: {_fmt_seconds(active_seconds)}",
                "- 主なアプリ利用:",
            ]
        )
        for app, count in app_counter.most_common(8):
            lines.append(f"  - {app}: {count}件")
        lines.append("")

    if browser_history:
        domain_counter = Counter()
        for row in browser_history:
            url = str(row.get("url", ""))
            domain = url.split("/")[2] if "://" in url and len(url.split("/")) > 2 else url
            if domain:
                domain_counter[domain] += 1
        lines.append("## ブラウザアクセス上位")
        for domain, count in domain_counter.most_common(10):
            lines.append(f"- {domain}: {count}回")
        lines.append("")

    if events:
        lines.append("## 主要イベント")
        top_events = sorted(events, key=lambda e: e.get("severity", 0), reverse=True)[:10]
        for e in top_events:
            lines.append(
                f"- [{e.get('event_type', 'unknown')}] {e.get('message', '')} (severity={e.get('severity', 0)})"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_data_appendix(
    report_date: str,
    analyses: list[dict],
    deep: list[dict],
    lifelog_data: Optional[list[dict]],
    browser_history: Optional[list[dict]],
    events: Optional[list[dict]],
) -> str:
    """短文レポートに追記するための付録セクション."""
    lines = [
        "## 収集データ付録",
        f"- 対象日: {report_date}",
        f"- 分析記事: {len(analyses)}件 / 深掘り: {len(deep)}件",
        f"- ライフログ: {len(lifelog_data or [])}件 / ブラウザ履歴: {len(browser_history or [])}件 / イベント: {len(events or [])}件",
        "",
    ]
    if analyses:
        lines.append("### 重要トピック")
        for item in sorted(analyses, key=lambda a: a.get("importance_score", 0), reverse=True)[:6]:
            title = item.get("title") or item.get("summary") or "N/A"
            lines.append(f"- {title}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _generate_report_text(ollama: OllamaClient, prompts: dict[str, str]) -> str:
    """LLM出力を再試行付きで取得."""
    content = ""
    for attempt in range(1, 3):
        try:
            content = ollama.generate(
                prompt=prompts["user"],
                system=prompts["system"],
                options={"temperature": 0.5},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Report generation failed (attempt %d/2): %s", attempt, exc)
            continue

        if content and len(content.strip()) >= MIN_REPORT_CHARS:
            return content

        logger.warning(
            "Report output too short on attempt %d/2 (chars=%d)", attempt, len(content or "")
        )
    return content


def generate_daily_report(
    db_path: Path = DEFAULT_DB,
    lifelog_db_path: Optional[Path] = None,
    output_dir: Path = DEFAULT_REPORT_DIR,
    hours: int = 24,
    include_lifelog: bool = True,
    target_date: Optional[str] = None,
) -> Path | None:
    """
    直近hours時間の分析・深掘り結果から日次レポートを生成.
    ライフログデータも含める（オプション）.

    Args:
        target_date: レポート対象日（YYYY-MM-DD）。Noneの場合は自動判定:
            - 実行時刻が朝6時以降なら前日
            - 実行時刻が朝6時以前なら当日
    """
    now = datetime.now()
    # レポート対象日の決定（明示指定があれば優先）
    if target_date:
        report_date = target_date
        logger.info("Using specified target date: %s", report_date)
        target_datetime = datetime.strptime(report_date, "%Y-%m-%d")
        target_date_start = target_datetime
        target_date_end = target_datetime + timedelta(days=1)
        since = target_date_start.isoformat()
    else:
        # hours ベースの取得（従来挙動）を復活
        report_date = now.strftime("%Y-%m-%d")
        since = (now - timedelta(hours=hours)).isoformat()
        target_date_start = None
        target_date_end = None
        logger.info("Using recent window: past %d hours (since %s)", hours, since)

    repo = InfoCollectorRepository(str(db_path))

    # 分析・深掘り結果を取得
    analyses = repo.fetch_recent_analysis(since)
    deep = repo.fetch_recent_deep_research(since)
    if target_date_start and target_date_end:

        def is_in_target_date(record: dict) -> bool:
            """レコードが対象日の範囲内かどうかを判定"""
            timestamp_str = record.get("analyzed_at") or record.get("researched_at")
            if not timestamp_str:
                return False
            try:
                if isinstance(timestamp_str, str):
                    if "T" in timestamp_str:
                        timestamp_str = timestamp_str.split("+")[0].split("Z")[0]
                        if "." in timestamp_str:
                            timestamp_str = timestamp_str.split(".")[0]
                    timestamp = datetime.fromisoformat(timestamp_str)
                else:
                    timestamp = timestamp_str
                if timestamp.tzinfo:
                    timestamp = timestamp.replace(tzinfo=None)
                return target_date_start <= timestamp < target_date_end
            except (ValueError, AttributeError, TypeError) as e:
                logger.debug("Failed to parse timestamp %s: %s", timestamp_str, e)
                return False

        all_analyses = analyses
        all_deep = deep
        analyses = [a for a in analyses if is_in_target_date(a)]
        deep = [d for d in deep if is_in_target_date(d)]
        logger.info(
            "Filtered to %d analyses and %d deep research entries for %s (from %d total analyses, %d total deep)",
            len(analyses),
            len(deep),
            report_date,
            len(all_analyses),
            len(all_deep),
        )

    # 記事分析データがない場合でも、ライフログデータがあればレポートを生成
    if not analyses:
        if include_lifelog:
            # ライフログデータを先に取得して確認
            try:
                if lifelog_db_path is None:
                    default_lifelog = Path("data/lifelog.db")
                    if default_lifelog.exists():
                        lifelog_db_path = default_lifelog
                    else:
                        lifelog_db_path = db_path.parent / "lifelog.db"

                if lifelog_db_path and lifelog_db_path.exists():
                    aggregator = DailyReportDataAggregator(lifelog_db_path, db_path)
                    data = aggregator.aggregate_daily_data(report_date, detail_level="summary")
                    if data.lifelog_data:
                        logger.info(
                            "No analyzed articles for %s, but lifelog data exists. Generating report with lifelog only.",
                            report_date,
                        )
                        # 空のリストで続行（ライフログデータのみのレポート）
                    else:
                        logger.info(
                            "No analyzed articles or lifelog data for %s to include in report.",
                            report_date,
                        )
                        return None
                else:
                    logger.info("No analyzed articles for %s to include in report.", report_date)
                    return None
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to check lifelog data: %s", exc)
                logger.info("No analyzed articles for %s to include in report.", report_date)
                return None
        else:
            logger.info("No analyzed articles for %s to include in report.", report_date)
            return None

    ollama = OllamaClient()

    # ライフログデータを取得（オプション）
    lifelog_data = None
    browser_history = None
    events = None

    if include_lifelog:
        try:
            if lifelog_db_path is None:
                # デフォルトパスを試行（相対パス）
                default_lifelog = Path("data/lifelog.db")
                if default_lifelog.exists():
                    lifelog_db_path = default_lifelog
                else:
                    # db_pathと同じディレクトリを試行
                    lifelog_db_path = db_path.parent / "lifelog.db"

            if lifelog_db_path and lifelog_db_path.exists():
                aggregator = DailyReportDataAggregator(lifelog_db_path, db_path)
                data = aggregator.aggregate_daily_data(report_date, detail_level="summary")
                lifelog_data = data.lifelog_data
                browser_history = data.browser_history
                events = data.events
                logger.info(
                    "Including lifelog data in report: %d intervals, %d browser entries",
                    len(lifelog_data),
                    len(browser_history),
                )
            else:
                logger.warning(
                    "Lifelog database not found at %s, skipping lifelog data", lifelog_db_path
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load lifelog data: %s, continuing without it", exc)

    prompts = report_generation.build_prompt(
        report_date=report_date,
        articles=analyses,
        deep_research=deep,
        lifelog_data=lifelog_data,
        browser_history=browser_history,
        events=events,
    )

    content = _generate_report_text(ollama, prompts)

    if not content:
        content = _build_fallback_report(
            report_date=report_date,
            analyses=analyses,
            deep=deep,
            lifelog_data=lifelog_data,
            browser_history=browser_history,
            events=events,
        )
    elif len(content.strip()) < MIN_REPORT_CHARS:
        content = (
            content.rstrip()
            + "\n\n"
            + _build_data_appendix(
                report_date=report_date,
                analyses=analyses,
                deep=deep,
                lifelog_data=lifelog_data,
                browser_history=browser_history,
                events=events,
            )
        )

    # DB保存
    repo.save_report(
        title=f"{report_date} 情報収集レポート",
        report_date=report_date,
        content=content,
        article_count=len(analyses),
        category="daily",
        created_at=datetime.now(),
    )

    # ファイル保存
    output_dir.mkdir(parents=True, exist_ok=True)

    # Obsidianリンクセクションを追加
    from src.info_collector.jobs.obsidian_links import (
        build_obsidian_links_section,
        ensure_diary_report_link,
        resolve_vault_root,
        update_raw_reports_moc,
    )

    vault_root = resolve_vault_root(output_dir)
    ensure_diary_report_link(vault_root, report_date)
    update_raw_reports_moc(output_dir)
    links_section = build_obsidian_links_section(output_dir, report_date)
    content += links_section

    report_path = output_dir / f"report_{report_date}.md"
    report_path.write_text(content, encoding="utf-8")
    logger.info("Report written to %s", report_path)
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily report from analysis results.")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument(
        "--lifelog-db-path", type=str, default=None, help="Path to lifelog database (optional)"
    )
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_REPORT_DIR))
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours (used when --date is not specified)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date for report (YYYY-MM-DD). If omitted, a rolling window using --hours is used",
    )
    parser.add_argument(
        "--no-lifelog", action="store_true", help="Exclude lifelog data from report"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_daily_report(
        db_path=Path(args.db_path),
        lifelog_db_path=Path(args.lifelog_db_path) if args.lifelog_db_path else None,
        output_dir=Path(args.output_dir),
        hours=args.hours,
        include_lifelog=not args.no_lifelog,
        target_date=args.date,
    )


if __name__ == "__main__":
    main()
