"""
既存 lifelog-system の DB から timeline-app 用 entry を時間帯単位で取り込む。

取り込む対象:
- lifelog.db / unified_timeline       -> system_log
- ai_secretary.db / browser_history   -> memo
- ai_secretary.db / reports           -> news

方針:
- 1時間ごとに source 別 summary entry を作る
- entry id は決定的にし、再実行時は同じ時間帯の summary を上書きする
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_APP_DIR = _SCRIPT_DIR.parent
_ROOT_DIR = _APP_DIR.parent
sys.path.insert(0, str(_APP_DIR))

from src.ai.ollama_client import OllamaClient, OllamaClientError  # noqa: E402
from src.config import config, to_local_path  # noqa: E402
from src.models.entry import Entry, EntryMeta, EntrySource, EntryType  # noqa: E402
from src.storage.daily_writer import upsert_entry_in_daily  # noqa: E402
from src.storage.entry_writer import write_entry  # noqa: E402


@dataclass
class ImportContext:
    workspace_path: Path
    lifelog_db: Path
    info_db: Path


def make_timestamp(target_date: date, hour: int) -> datetime:
    return datetime.combine(target_date, time(hour=hour, minute=30, tzinfo=timezone.utc))


def make_entry_id(target_date: date, hour: int, suffix: str) -> str:
    return f"import-{target_date.isoformat()}-{hour:02d}-{suffix}"


def build_entry(
    *,
    target_date: date,
    hour: int,
    suffix: str,
    entry_type: EntryType,
    title: str,
    content: str,
    source_path: str,
) -> Entry:
    workspace_path = str(Path(to_local_path(config.workspace.default_path)).resolve())
    return Entry(
        id=make_entry_id(target_date, hour, suffix),
        type=entry_type,
        title=title,
        content=content,
        timestamp=make_timestamp(target_date, hour),
        source=EntrySource.imported,
        workspace_path=workspace_path,
        meta=EntryMeta(source_path=source_path),
    )


def summarize_with_llm(
    client: OllamaClient,
    *,
    source_type: str,
    target_label: str,
    raw_summary: str,
    fallback_title: str,
    fallback_content: str,
) -> tuple[str, str, bool]:
    try:
        result = client.summarize_import_source(
            source_type=source_type,
            target_label=target_label,
            raw_summary=raw_summary,
        )
        should_create = result.should_create if source_type == "system_event" else True
        return result.title, result.content, should_create
    except OllamaClientError:
        return fallback_title, fallback_content, True


def summarize_activity_and_system(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
) -> list[Entry]:
    day = target_date.isoformat()
    hour_str = f"{hour:02d}"
    activity_rows = conn.execute(
        """
        SELECT COALESCE(process_name, '') AS process_name
        FROM unified_timeline
        WHERE date(timestamp) = ?
          AND strftime('%H', timestamp) = ?
          AND event_source = 'activity'
        """,
        (day, hour_str),
    ).fetchall()

    activity_processes: dict[str, int] = {}
    for (process_name,) in activity_rows:
        name = process_name or "unknown"
        activity_processes[name] = activity_processes.get(name, 0) + 1

    system_rows = conn.execute(
        """
        SELECT COALESCE(event_type, '') AS event_type,
               COALESCE(severity, 0) AS severity,
               COALESCE(process_name, '') AS process_name,
               COALESCE(message, '') AS message
        FROM system_events
        WHERE date(event_timestamp) = ?
          AND strftime('%H', event_timestamp) = ?
        ORDER BY event_timestamp DESC
        """,
        (day, hour_str),
    ).fetchall()

    entries: list[Entry] = []

    if activity_processes:
        top_processes = sorted(activity_processes.items(), key=lambda item: (-item[1], item[0]))[:5]
        lines = [f"{hour:02d}時台の活動ログ素材", ""]
        for process_name, count in top_processes:
            lines.append(f"- {process_name}: {count}件")
        raw_summary = "\n".join(lines)
        fallback_content = "\n".join(
            [
                f"{hour:02d}時台は次のアプリでの活動が中心。",
                " / ".join(f"{process_name}({count})" for process_name, count in top_processes),
            ]
        )
        title, content, should_create = summarize_with_llm(
            client,
            source_type="activity",
            target_label=f"{target_date.isoformat()} {hour:02d}時の活動",
            raw_summary=raw_summary,
            fallback_title=f"{target_date.isoformat()} {hour:02d}時の活動",
            fallback_content=fallback_content,
        )
        if should_create:
            entries.append(
                build_entry(
                    target_date=target_date,
                    hour=hour,
                    suffix="activity",
                    entry_type=EntryType.system_log,
                    title=title,
                    content=content,
                    source_path="lifelog-system/data/lifelog.db",
                )
            )

    important_system_rows = filter_important_system_rows(system_rows)
    if important_system_rows:
        type_counts: dict[str, int] = {}
        for event_type, _, _, _ in important_system_rows:
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
        lines = [
            f"{hour:02d}時台の重要 system event {len(important_system_rows)} 件。",
            "",
            "event type counts:",
        ]
        for event_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))[
            :5
        ]:
            lines.append(f"- {event_type}: {count}件")
        lines.append("")
        lines.append("sample messages:")
        for event_type, severity, process_name, message in important_system_rows[:12]:
            compact = " ".join(message.split())[:180] if message else "(messageなし)"
            lines.append(f"- [{event_type}/{severity}] {process_name}: {compact}")
        raw_summary = "\n".join(lines)
        fallback_content = "\n".join(
            [
                f"{hour:02d}時台に重要な system event が {len(important_system_rows)} 件あった。",
                "失敗や警告が中心なので右ペインで詳細を確認してください。",
            ]
        )
        title, content, should_create = summarize_with_llm(
            client,
            source_type="system_event",
            target_label=f"{target_date.isoformat()} {hour:02d}時のシステムイベント",
            raw_summary=raw_summary,
            fallback_title=f"{target_date.isoformat()} {hour:02d}時のシステムイベント",
            fallback_content=fallback_content,
        )
        if should_create:
            entries.append(
                build_entry(
                    target_date=target_date,
                    hour=hour,
                    suffix="system",
                    entry_type=EntryType.system_log,
                    title=title,
                    content=content,
                    source_path="lifelog-system/data/lifelog.db",
                )
            )

    return entries


def filter_important_system_rows(
    rows: list[tuple[str, int, str, str]]
) -> list[tuple[str, int, str, str]]:
    important_keywords = (
        "failed",
        "error",
        "exception",
        "traceback",
        "forbidden",
        "exit-code",
        "main process exited",
        "ニュース取得エラー",
        "ollama json generation failed",
    )
    important_services = (
        "info-integrated.service",
        "merge-windows-logs.service",
        "obsidian-conscierge-sync.service",
    )
    kept: list[tuple[str, int, str, str]] = []
    for event_type, severity, process_name, message in rows:
        text = f"{event_type} {process_name} {message}".lower()
        if severity >= 70 or event_type.lower() in {"error", "critical"}:
            kept.append((event_type, severity, process_name, message))
            continue
        if any(keyword in text for keyword in important_keywords):
            kept.append((event_type, severity, process_name, message))
            continue
        if any(service in text for service in important_services) and (
            "starting " in text or "finished " in text or "deactivated successfully" in text
        ):
            kept.append((event_type, severity, process_name, message))
    return kept


def summarize_browser(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
) -> list[Entry]:
    day = target_date.isoformat()
    hour_str = f"{hour:02d}"
    rows = conn.execute(
        """
        SELECT COALESCE(title, ''), url
        FROM browser_history
        WHERE date(visit_time) = ?
          AND strftime('%H', visit_time) = ?
        ORDER BY visit_time DESC
        LIMIT 12
        """,
        (day, hour_str),
    ).fetchall()

    if not rows:
        return []

    lines = [f"{hour:02d}時台のブラウザ履歴 {len(rows)} 件。", ""]
    for title, url in rows[:6]:
        label = title.strip() or url
        lines.append(f"- {label}")
    raw_summary = "\n".join(lines)
    fallback_content = "\n".join(
        [
            f"{hour:02d}時台は次のページを見ていた。",
            " / ".join((title.strip() or url) for title, url in rows[:4]),
        ]
    )
    title, content, should_create = summarize_with_llm(
        client,
        source_type="browser",
        target_label=f"{target_date.isoformat()} {hour:02d}時の閲覧履歴",
        raw_summary=raw_summary,
        fallback_title=f"{target_date.isoformat()} {hour:02d}時の閲覧履歴",
        fallback_content=fallback_content,
    )
    if not should_create:
        return []
    return [
        build_entry(
            target_date=target_date,
            hour=hour,
            suffix="browser",
            entry_type=EntryType.memo,
            title=title,
            content=content,
            source_path="lifelog-system/data/ai_secretary.db",
        )
    ]


def summarize_reports(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
) -> list[Entry]:
    day = target_date.isoformat()
    hour_str = f"{hour:02d}"
    rows = conn.execute(
        """
        SELECT title, content
        FROM reports
        WHERE date(created_at) = ?
          AND strftime('%H', created_at) = ?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (day, hour_str),
    ).fetchall()

    if not rows:
        return []

    lines = [f"{hour:02d}時台に生成されたレポート {len(rows)} 件。", ""]
    for title, _ in rows:
        lines.append(f"- {title}")

    first_title, first_content = rows[0]
    preview = " ".join((first_content or "").split())[:400]
    if preview:
        lines.extend(["", "先頭レポート抜粋:", preview])
    raw_summary = "\n".join(lines)
    fallback_content = "\n".join(
        [
            f"{hour:02d}時台にレポート {len(rows)} 件が生成された。",
            "主なタイトル: " + " / ".join(title for title, _ in rows[:3]),
        ]
    )
    title, content, should_create = summarize_with_llm(
        client,
        source_type="reports",
        target_label=f"{target_date.isoformat()} {hour:02d}時のレポート",
        raw_summary=raw_summary,
        fallback_title=f"{target_date.isoformat()} {hour:02d}時のレポート: {first_title}",
        fallback_content=fallback_content,
    )
    if not should_create:
        return []
    return [
        build_entry(
            target_date=target_date,
            hour=hour,
            suffix="reports",
            entry_type=EntryType.news,
            title=title,
            content=content,
            source_path="lifelog-system/data/ai_secretary.db",
        )
    ]


def import_range(ctx: ImportContext, start_date: date, end_date: date) -> int:
    total = 0
    client = OllamaClient(config.ai)
    with sqlite3.connect(ctx.lifelog_db) as lifelog_conn, sqlite3.connect(ctx.info_db) as info_conn:
        current = start_date
        while current <= end_date:
            for hour in range(24):
                entries = []
                entries.extend(summarize_activity_and_system(lifelog_conn, current, hour, client))
                entries.extend(summarize_browser(info_conn, current, hour, client))
                entries.extend(summarize_reports(info_conn, current, hour, client))

                for entry in entries:
                    write_entry(str(ctx.workspace_path), config.workspace.dirs.articles, entry)
                    upsert_entry_in_daily(
                        str(ctx.workspace_path), config.workspace.dirs.daily, entry
                    )
                    total += 1
            current += timedelta(days=1)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="lifelog-system の履歴を timeline-app へ時間帯単位で取り込む")
    parser.add_argument("--start-date", type=str, default=None, help="開始日 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="終了日 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=3, help="終了日から何日分さかのぼるか（デフォルト: 3）")
    args = parser.parse_args()

    workspace_path = Path(to_local_path(config.workspace.default_path)).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / config.workspace.dirs.daily).mkdir(parents=True, exist_ok=True)
    (workspace_path / config.workspace.dirs.articles).mkdir(parents=True, exist_ok=True)

    end_date = (
        date.fromisoformat(args.end_date) if args.end_date else (date.today() - timedelta(days=1))
    )
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
    else:
        start_date = end_date - timedelta(days=args.days - 1)

    ctx = ImportContext(
        workspace_path=workspace_path,
        lifelog_db=_ROOT_DIR / "lifelog-system" / "data" / "lifelog.db",
        info_db=_ROOT_DIR / "lifelog-system" / "data" / "ai_secretary.db",
    )

    count = import_range(ctx, start_date, end_date)
    print(f"Imported {count} hourly summary entries into {workspace_path}")


if __name__ == "__main__":
    main()
