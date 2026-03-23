"""未生成の時間帯を埋める 1時間単位 summary worker。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..config import config
from ..routers.workspace import resolve_workspace_path
from ..services.ai_control import ai_control_service
from ..services.hourly_summary_importer import (
    get_local_timezone,
    import_missing_hours,
    resolve_context,
)


@dataclass
class HourlySummaryWorkerStatus:
    running: bool = False
    last_range_start: str | None = None
    last_range_end: str | None = None
    last_generated: int = 0
    last_sync_at: str | None = None
    last_error: str | None = None


class HourlySummaryWorker:
    def __init__(self) -> None:
        self._status = HourlySummaryWorkerStatus()
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
            self._status.last_generated = 0
            return 0
        workspace_path = resolve_workspace_path()
        if not workspace_path:
            self._status.last_generated = 0
            return 0

        end_hour = datetime.now(get_local_timezone()).replace(
            minute=0, second=0, microsecond=0
        ) - timedelta(hours=1)
        lookback_hours = max(config.lifelog.hourly_summary_lookback_hours, 1)
        start_hour = end_hour - timedelta(hours=lookback_hours - 1)

        self._status.last_range_start = start_hour.isoformat()
        self._status.last_range_end = end_hour.isoformat()

        if end_hour < start_hour:
            self._status.last_generated = 0
            return 0

        try:
            ctx = resolve_context(workspace_path)
            generated = import_missing_hours(ctx, start_hour, end_hour)
            self._status.last_generated = generated
            self._status.last_sync_at = datetime.now(UTC).isoformat()
            return generated
        except Exception as exc:  # noqa: BLE001
            self._status.last_error = str(exc)
            self._status.last_generated = 0
            raise


hourly_summary_worker = HourlySummaryWorker()
