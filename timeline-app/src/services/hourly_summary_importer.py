"""既存 lifelog DB から 1時間単位 summary entry を生成する共通処理。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from ..ai.ollama_client import OllamaClient, OllamaClientError
from ..config import config, to_local_path
from ..models.entry import Entry, EntryMeta, EntrySource, EntryType
from ..storage.daily_reader import read_daily_entries
from ..storage.persistence import persist_entry

HOURLY_SUFFIXES = ("activity", "browser", "news", "system")


@dataclass
class ImportContext:
    workspace_path: Path
    lifelog_db: Path
    info_db: Path


def resolve_context(workspace_path: str | Path) -> ImportContext:
    workspace_root = Path(workspace_path).resolve()
    return ImportContext(
        workspace_path=workspace_root,
        lifelog_db=_resolve_repo_path(config.lifelog.db_path),
        info_db=_resolve_repo_path(config.lifelog.info_db_path),
    )


def import_range(ctx: ImportContext, start_date: date, end_date: date) -> int:
    total = 0
    client = OllamaClient(config.ai)
    with sqlite3.connect(ctx.lifelog_db) as lifelog_conn, sqlite3.connect(ctx.info_db) as info_conn:
        current = start_date
        while current <= end_date:
            for hour in range(24):
                for entry in build_entries_for_hour(lifelog_conn, info_conn, current, hour, client):
                    persist_entry(str(ctx.workspace_path), entry)
                    total += 1
            current += timedelta(days=1)
    return total


def import_missing_hours(ctx: ImportContext, start_hour: datetime, end_hour: datetime) -> int:
    if end_hour < start_hour:
        return 0

    start_hour = _normalize_hour(start_hour)
    end_hour = _normalize_hour(end_hour)
    client = OllamaClient(config.ai)
    total = 0
    cached_ids: dict[date, set[str]] = {}

    with sqlite3.connect(ctx.lifelog_db) as lifelog_conn, sqlite3.connect(ctx.info_db) as info_conn:
        current = start_hour
        while current <= end_hour:
            target_date = current.date()
            hour = current.hour
            existing_ids = cached_ids.setdefault(
                target_date,
                {
                    entry.id
                    for entry in read_daily_entries(
                        str(ctx.workspace_path), config.workspace.dirs.daily, target_date
                    )
                },
            )
            missing_suffixes = [
                suffix
                for suffix in HOURLY_SUFFIXES
                if make_entry_id(target_date, hour, suffix) not in existing_ids
            ]
            if missing_suffixes:
                for entry in build_entries_for_hour(
                    lifelog_conn,
                    info_conn,
                    target_date,
                    hour,
                    client,
                    allowed_suffixes=set(missing_suffixes),
                    existing_ids=existing_ids,
                ):
                    persist_entry(str(ctx.workspace_path), entry)
                    existing_ids.add(entry.id)
                    total += 1
            current += timedelta(hours=1)
    return total


def build_entries_for_hour(
    lifelog_conn: sqlite3.Connection,
    info_conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
    *,
    allowed_suffixes: set[str] | None = None,
    existing_ids: set[str] | None = None,
) -> list[Entry]:
    entries: list[Entry] = []
    if _allow("activity", allowed_suffixes):
        activity = summarize_activity(lifelog_conn, target_date, hour, client)
        if activity:
            entries.append(activity)
    if _allow("system", allowed_suffixes):
        system = summarize_system(lifelog_conn, target_date, hour, client)
        if system:
            entries.append(system)
    if _allow("browser", allowed_suffixes):
        browser = summarize_browser(info_conn, target_date, hour, client)
        if browser:
            entries.append(browser)
    if _allow("news", allowed_suffixes):
        news = summarize_news(info_conn, target_date, hour)
        if news:
            entries.append(news)
    entries.extend(summarize_reports(info_conn, target_date, hour, existing_ids=existing_ids))
    return entries


def summarize_activity(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
) -> Entry | None:
    rows = conn.execute(
        """
        SELECT COALESCE(process_name, '') AS process_name
        FROM unified_timeline
        WHERE date(datetime(timestamp, 'localtime')) = ?
          AND strftime('%H', datetime(timestamp, 'localtime')) = ?
          AND event_source = 'activity'
        """,
        (target_date.isoformat(), f"{hour:02d}"),
    ).fetchall()

    if not rows:
        return None

    counts: dict[str, int] = {}
    for (process_name,) in rows:
        name = process_name or "unknown"
        counts[name] = counts.get(name, 0) + 1

    top_processes = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
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
    if not should_create:
        return None
    return build_entry(
        target_date=target_date,
        hour=hour,
        suffix="activity",
        entry_type=EntryType.system_log,
        title=title,
        content=content,
        source_path="lifelog-system/data/lifelog.db",
    )


def summarize_system(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
) -> Entry | None:
    rows = conn.execute(
        """
        SELECT COALESCE(event_type, '') AS event_type,
               COALESCE(severity, 0) AS severity,
               COALESCE(process_name, '') AS process_name,
               COALESCE(message, '') AS message
        FROM system_events
        WHERE date(datetime(event_timestamp, 'localtime')) = ?
          AND strftime('%H', datetime(event_timestamp, 'localtime')) = ?
        ORDER BY event_timestamp DESC
        """,
        (target_date.isoformat(), f"{hour:02d}"),
    ).fetchall()
    important_rows = filter_important_system_rows(rows)
    if not important_rows:
        return None

    type_counts: dict[str, int] = {}
    for event_type, _, _, _ in important_rows:
        type_counts[event_type] = type_counts.get(event_type, 0) + 1
    lines = [
        f"{hour:02d}時台の重要 system event {len(important_rows)} 件。",
        "",
        "event type counts:",
    ]
    for event_type, count in sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))[:5]:
        lines.append(f"- {event_type}: {count}件")
    lines.append("")
    lines.append("sample messages:")
    for event_type, severity, process_name, message in important_rows[:12]:
        compact = " ".join(message.split())[:180] if message else "(messageなし)"
        lines.append(f"- [{event_type}/{severity}] {process_name}: {compact}")
    raw_summary = "\n".join(lines)
    fallback_content = "\n".join(
        [
            f"{hour:02d}時台に重要な system event が {len(important_rows)} 件あった。",
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
    if not should_create:
        return None
    return build_entry(
        target_date=target_date,
        hour=hour,
        suffix="system",
        entry_type=EntryType.system_log,
        title=title,
        content=content,
        source_path="lifelog-system/data/lifelog.db",
    )


def summarize_browser(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    client: OllamaClient,
) -> Entry | None:
    rows = conn.execute(
        """
        SELECT COALESCE(title, ''), url
        FROM browser_history
        WHERE date(datetime(visit_time, 'localtime')) = ?
          AND strftime('%H', datetime(visit_time, 'localtime')) = ?
        ORDER BY visit_time DESC
        LIMIT 12
        """,
        (target_date.isoformat(), f"{hour:02d}"),
    ).fetchall()
    if not rows:
        return None

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
        return None
    return build_entry(
        target_date=target_date,
        hour=hour,
        suffix="browser",
        entry_type=EntryType.memo,
        title=title,
        content=content,
        source_path="lifelog-system/data/ai_secretary.db",
    )


def summarize_reports(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
    *,
    existing_ids: set[str] | None = None,
) -> list[Entry]:
    rows = conn.execute(
        """
        SELECT id, title, content, category, created_at
        FROM reports
        WHERE date(datetime(created_at, 'localtime')) = ?
          AND strftime('%H', datetime(created_at, 'localtime')) = ?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (target_date.isoformat(), f"{hour:02d}"),
    ).fetchall()
    if not rows:
        return []

    entries: list[Entry] = []
    for report_id, title, content, category, created_at in rows:
        entry_id = f"report-{report_id}"
        if existing_ids and entry_id in existing_ids:
            continue
        created_at_dt = datetime.fromisoformat(str(created_at)).astimezone(UTC)
        category_label = str(category or "report").strip()
        body = (content or "").strip()
        if not body:
            continue
        entries.append(
            Entry(
                id=entry_id,
                type=EntryType.news,
                title=(str(title or "レポート")[:120]),
                summary=f"{category_label} レポート",
                content=body,
                timestamp=created_at_dt,
                source=EntrySource.imported,
                workspace_path=str(Path(to_local_path(config.workspace.default_path)).resolve()),
                meta=EntryMeta(source_path="lifelog-system/data/ai_secretary.db"),
            )
        )
    return entries


def summarize_news(
    conn: sqlite3.Connection,
    target_date: date,
    hour: int,
) -> Entry | None:
    rows = conn.execute(
        """
        SELECT id, COALESCE(title, ''), url, COALESCE(source_name, ''), COALESCE(snippet, '')
        FROM collected_info
        WHERE date(datetime(fetched_at, 'localtime')) = ?
          AND strftime('%H', datetime(fetched_at, 'localtime')) = ?
        ORDER BY fetched_at DESC
        LIMIT 20
        """,
        (target_date.isoformat(), f"{hour:02d}"),
    ).fetchall()
    if not rows:
        return None

    lines = [f"{hour:02d}時台に取得したニュース一覧 ({len(rows)}件)", ""]
    related_ids: list[str] = []
    for row_id, title, url, source_name, snippet in rows:
        label = str(title).strip() or str(url)
        source = f" ({source_name})" if source_name else ""
        lines.append(f"- [{label}]({url}){source}")
        if snippet:
            lines.append(f"  - {' '.join(str(snippet).split())[:180]}")
        related_ids.append(f"collected-info-{row_id}")

    return Entry(
        id=make_entry_id(target_date, hour, "news"),
        type=EntryType.news,
        title=f"{target_date.isoformat()} {hour:02d}時のニュース",
        summary=f"{hour:02d}時台に取得したニュース {len(rows)} 件",
        content="\n".join(lines),
        timestamp=make_timestamp(target_date, hour),
        source=EntrySource.imported,
        workspace_path=str(Path(to_local_path(config.workspace.default_path)).resolve()),
        related_ids=related_ids,
        meta=EntryMeta(source_path="lifelog-system/data/ai_secretary.db"),
    )


def make_timestamp(target_date: date, hour: int) -> datetime:
    local_tz = datetime.now().astimezone().tzinfo
    return datetime.combine(target_date, time(hour=hour, minute=30), tzinfo=local_tz)


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
            caller="hourly_summary_worker",
        )
        should_create = result.should_create if source_type == "system_event" else True
        return result.title, result.content, should_create
    except OllamaClientError:
        return fallback_title, fallback_content, True


def filter_important_system_rows(
    rows: list[tuple[str, int, str, str]],
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


def _resolve_repo_path(raw_path: str) -> Path:
    path = Path(to_local_path(raw_path))
    if path.is_absolute():
        return path.resolve()
    return (Path(__file__).resolve().parents[3] / path).resolve()


def _normalize_hour(value: datetime) -> datetime:
    return value.astimezone().replace(minute=0, second=0, microsecond=0)


def _allow(suffix: str, allowed_suffixes: set[str] | None) -> bool:
    return allowed_suffixes is None or suffix in allowed_suffixes
