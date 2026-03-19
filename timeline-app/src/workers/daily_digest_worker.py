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
from ..storage.daily_reader import read_daily_entries
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
        if ai_control_service.is_paused():
            self._status.last_saved = 0
            return 0

        workspace_path = resolve_workspace_path()
        if not workspace_path:
            self._status.last_saved = 0
            return 0
        total_saved = 0
        target_dates = self._target_dates()
        client = OllamaClient(config.ai)
        for target_date in target_dates:
            self._status.last_target_date = target_date.isoformat()
            total_saved += self._generate_for_date(client, workspace_path, target_date)

        self._status.last_saved = total_saved
        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return total_saved

    def _target_dates(self) -> list[date]:
        yesterday = date.today() - timedelta(days=1)
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


daily_digest_worker = DailyDigestWorker()
