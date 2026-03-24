"""前日の diary を振り返る AI コメントを 1 日 1 回生成する worker。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from ..ai.ollama_client import OllamaClient, OllamaClientError
from ..config import config
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from ..routers.workspace import resolve_workspace_path
from ..services.ai_control import ai_control_service
from ..services.behavior_review import build_daily_review_bundle, build_weekly_review_bundle
from ..storage.daily_reader import read_daily_entries
from ..storage.entry_reader import read_entry, read_entries
from ..storage.daily_writer import ensure_future_daily_files
from ..storage.persistence import persist_entry

_DIGEST_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_daily_digest",
        "description": "前日の diary entry をもとに、短い振り返りコメントを生成する。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
}


@dataclass
class DailyDigestWorkerStatus:
    running: bool = False
    last_target_date: str | None = None
    last_saved: int = 0
    last_future_daily_created: int = 0
    last_future_daily_end_date: str | None = None
    last_recurring_todo_created: int = 0
    last_behavior_review_saved: int = 0
    last_behavior_tagged: int = 0
    last_weekly_review_saved: int = 0
    last_weekly_review_date: str | None = None
    last_sync_at: str | None = None
    last_error: str | None = None


class DailyDigestWorker:
    def __init__(self) -> None:
        self._status = DailyDigestWorkerStatus()
        self._lock = asyncio.Lock()

    def get_status(self) -> dict[str, Any]:
        return asdict(self._status)

    async def sync_once(self) -> int:
        async with self._lock:
            self._status.running = True
            try:
                return await asyncio.to_thread(self._sync_once_blocking)
            finally:
                self._status.running = False

    def _sync_once_blocking(self) -> int:
        self._status.last_error = None
        workspace_path = resolve_workspace_path()
        if not workspace_path:
            self._status.last_saved = 0
            self._status.last_future_daily_created = 0
            return 0

        created_files = self._ensure_future_daily_files(workspace_path)
        self._status.last_future_daily_created = created_files
        self._status.last_recurring_todo_created = self._ensure_recurring_todos(workspace_path)

        if ai_control_service.is_paused():
            self._status.last_saved = 0
            self._status.last_sync_at = datetime.now(UTC).isoformat()
            return 0

        total_saved = 0
        total_behavior_saved = 0
        total_behavior_tagged = 0
        target_dates = self._target_dates()
        client = OllamaClient(config.ai)
        for target_date in target_dates:
            self._status.last_target_date = target_date.isoformat()
            total_saved += self._generate_for_date(client, workspace_path, target_date)
            behavior_saved, behavior_tagged = self._generate_behavior_review(
                workspace_path, target_date
            )
            total_saved += behavior_saved
            total_behavior_saved += behavior_saved
            total_behavior_tagged += behavior_tagged

        self._status.last_saved = total_saved
        self._status.last_behavior_review_saved = total_behavior_saved
        self._status.last_behavior_tagged = total_behavior_tagged
        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return total_saved

    async def sync_weekly_review_once(self) -> int:
        async with self._lock:
            self._status.running = True
            try:
                return await asyncio.to_thread(self._sync_weekly_review_once_blocking)
            finally:
                self._status.running = False

    def _sync_weekly_review_once_blocking(self) -> int:
        self._status.last_error = None
        workspace_path = resolve_workspace_path()
        if (
            not workspace_path
            or ai_control_service.is_paused()
            or not config.behavior.review_enabled
        ):
            self._status.last_weekly_review_saved = 0
            self._status.last_sync_at = datetime.now(UTC).isoformat()
            return 0
        today = datetime.now().astimezone().date()
        saved = self._generate_weekly_review(workspace_path, today)
        self._status.last_weekly_review_saved = saved
        self._status.last_weekly_review_date = today.isoformat()
        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return saved

    def _ensure_future_daily_files(self, workspace_path: str) -> int:
        base_date = datetime.now().astimezone().date()
        created = ensure_future_daily_files(
            workspace_path,
            config.workspace.dirs.daily,
            config.lifelog.future_daily_days_ahead,
            start_date=base_date,
        )
        horizon_end = base_date + timedelta(days=max(config.lifelog.future_daily_days_ahead, 0))
        self._status.last_future_daily_end_date = horizon_end.isoformat()
        return len(created)

    def _ensure_recurring_todos(self, workspace_path: str) -> int:
        today = datetime.now().astimezone().date()
        entries = read_entries(workspace_path, config.workspace.dirs.articles)
        by_series_and_date = {
            (entry.meta.recurring_series_id, entry.meta.recurring_scheduled_for): entry
            for entry in entries
            if entry.meta.recurring_series_id and entry.meta.recurring_scheduled_for
        }
        created = 0
        active_todos = sorted(
            [
                entry
                for entry in entries
                if entry.type == EntryType.todo
                and entry.status == EntryStatus.active
                and entry.meta.recurring_enabled
            ],
            key=lambda entry: (
                entry.meta.recurring_series_id or "",
                entry.meta.recurring_sequence or 0,
            ),
        )
        for entry in active_todos:
            created += self._generate_recurring_successors(
                workspace_path,
                entry,
                today,
                by_series_and_date,
            )
        return created

    def _generate_recurring_successors(
        self,
        workspace_path: str,
        entry: Entry,
        today: date,
        by_series_and_date: dict[tuple[str | None, str | None], Entry],
    ) -> int:
        meta = entry.meta
        if not meta.recurring_series_id:
            return 0

        current_date = self._scheduled_date(entry)
        current_sequence = meta.recurring_sequence or 1
        created = 0
        while True:
            next_sequence = current_sequence + 1
            if meta.recurring_count is not None and next_sequence > meta.recurring_count:
                break

            next_date = self._next_recurring_date(current_date, meta)
            if next_date is None or next_date > today:
                break

            key = (meta.recurring_series_id, next_date.isoformat())
            existing = by_series_and_date.get(key)
            if existing is not None:
                current_date = next_date
                current_sequence = existing.meta.recurring_sequence or next_sequence
                continue

            new_entry = self._build_recurring_todo_entry(
                workspace_path,
                entry,
                next_date,
                next_sequence,
            )
            persist_entry(workspace_path, new_entry)
            by_series_and_date[key] = new_entry
            current_date = next_date
            current_sequence = next_sequence
            created += 1
        return created

    def _build_recurring_todo_entry(
        self,
        workspace_path: str,
        source_entry: Entry,
        target_date: date,
        sequence: int,
    ) -> Entry:
        meta = source_entry.meta
        series_id = meta.recurring_series_id or f"series-{source_entry.id}"
        suffix = f"{series_id.split('-')[-1][:8]}-{target_date.isoformat()}"
        scheduled_time = source_entry.timestamp.timetz().replace(tzinfo=UTC)
        return Entry(
            id=f"recurring-todo-{suffix}",
            type=EntryType.todo,
            title=source_entry.title,
            content=source_entry.content,
            timestamp=datetime.combine(target_date, scheduled_time),
            status=EntryStatus.active,
            source=source_entry.source,
            workspace_path=workspace_path,
            meta=meta.model_copy(
                update={
                    "recurring_enabled": True,
                    "recurring_series_id": series_id,
                    "recurring_sequence": sequence,
                    "recurring_scheduled_for": target_date.isoformat(),
                }
            ),
        )

    def _scheduled_date(self, entry: Entry) -> date:
        raw = entry.meta.recurring_scheduled_for
        if raw:
            return date.fromisoformat(raw)
        return entry.timestamp.astimezone().date()

    def _next_recurring_date(self, current_date: date, meta: EntryMeta) -> date | None:
        interval = max(meta.recurring_interval or 1, 1)
        rule = meta.recurring_rule or "daily"
        if rule == "daily":
            return current_date + timedelta(days=interval)
        if rule == "weekdays":
            return self._advance_matching_weekday(current_date, set(range(5)), interval)
        if rule == "weekends":
            return self._advance_matching_weekday(current_date, {5, 6}, interval)
        if rule == "weekly":
            return current_date + timedelta(weeks=interval)
        if rule == "custom_weekdays":
            weekdays = {day for day in meta.recurring_weekdays if 0 <= day <= 6}
            if not weekdays:
                return None
            return self._advance_matching_weekday(current_date, weekdays, interval)
        return None

    def _advance_matching_weekday(
        self, current_date: date, weekdays: set[int], interval: int
    ) -> date:
        candidate = current_date + timedelta(days=1)
        matched = 0
        while True:
            if candidate.weekday() in weekdays:
                matched += 1
                if matched >= interval:
                    return candidate
            candidate += timedelta(days=1)

    def _target_dates(self) -> list[date]:
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        lookback = max(config.lifelog.daily_digest_lookback_days, 1)
        start = yesterday - timedelta(days=lookback - 1)
        days: list[date] = []
        current = start
        while current <= yesterday:
            days.append(current)
            current += timedelta(days=1)
        return days

    def _generate_for_date(
        self, client: OllamaClient, workspace_path: str, target_date: date
    ) -> int:
        entry_id = f"daily-digest-{target_date.isoformat()}"
        existing = read_daily_entries(workspace_path, config.workspace.dirs.daily, target_date)
        if any(entry.id == entry_id for entry in existing):
            return 0

        diaries = [entry for entry in existing if entry.type == EntryType.diary]
        if not diaries:
            return 0

        context_lines = []
        for entry in diaries[:20]:
            body = (entry.summary or entry.content).strip()
            context_lines.append(f"- {entry.title or '日記'}: {body[:220]}")

        try:
            args, _ = client._chat_with_tools(
                [
                    {
                        "role": "system",
                        "content": (
                            "あなたはライフログ支援AIです。前日の diary entry を振り返り、"
                            "やさしく短い総括コメントを日本語で生成してください。"
                            "褒める要素と次への軽い示唆を含め、2〜5文にしてください。"
                            "content は Markdown 形式で書くこと。HTML タグは使わないこと。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"対象日: {target_date.isoformat()}\n"
                            "前日の diary entry 一覧:\n" + "\n".join(context_lines)
                        ),
                    },
                ],
                [_DIGEST_TOOL],
                caller="daily_digest_worker",
                purpose="daily_digest",
                context={"target_date": target_date.isoformat()},
            )
        except OllamaClientError as exc:
            self._status.last_error = str(exc)
            return 0

        title = str(args.get("title", "")).strip() or f"{target_date.isoformat()} の振り返り"
        content = str(args.get("content", "")).strip()
        if not content:
            return 0

        persist_entry(
            workspace_path,
            Entry(
                id=entry_id,
                type=EntryType.memo,
                title=title,
                content=content,
                timestamp=datetime.combine(target_date, time(23, 50, tzinfo=UTC)),
                status=EntryStatus.active,
                source=EntrySource.ai,
                workspace_path=workspace_path,
                meta=EntryMeta(),
            ),
        )
        return 1

    def _generate_behavior_review(self, workspace_path: str, target_date: date) -> tuple[int, int]:
        daily_entries = read_daily_entries(workspace_path, config.workspace.dirs.daily, target_date)
        bundle = build_daily_review_bundle(
            workspace_path, target_date, daily_entries, config.behavior
        )

        tagged_count = 0
        for tagged in bundle.tagged_entries:
            base_entry = self._load_article_entry(workspace_path, tagged)
            if (
                base_entry.meta.traits == tagged.meta.traits
                and base_entry.meta.trait_evidence == tagged.meta.trait_evidence
            ):
                continue
            persist_entry(
                workspace_path,
                base_entry.model_copy(
                    update={
                        "meta": base_entry.meta.model_copy(
                            update={
                                "traits": tagged.meta.traits,
                                "trait_evidence": tagged.meta.trait_evidence,
                            }
                        )
                    }
                ),
            )
            tagged_count += 1

        saved = 0
        existing_ids = {
            entry.id for entry in read_entries(workspace_path, config.workspace.dirs.articles)
        }
        for candidate in [bundle.review_entry, bundle.action_entry]:
            if candidate is None or candidate.id in existing_ids:
                continue
            persist_entry(workspace_path, candidate)
            existing_ids.add(candidate.id)
            saved += 1
        return saved, tagged_count

    def _load_article_entry(self, workspace_path: str, entry: Entry) -> Entry:
        try:
            return read_entry(workspace_path, config.workspace.dirs.articles, entry.id)
        except FileNotFoundError:
            return entry

    def _generate_weekly_review(self, workspace_path: str, anchor_date: date) -> int:
        entries = read_entries(workspace_path, config.workspace.dirs.articles)
        bundle = build_weekly_review_bundle(workspace_path, entries, anchor_date, config.behavior)
        if bundle.review_entry is None:
            return 0
        existing = {entry.id for entry in entries}
        if bundle.review_entry.id in existing:
            return 0
        persist_entry(workspace_path, bundle.review_entry)
        return 1


daily_digest_worker = DailyDigestWorker()
