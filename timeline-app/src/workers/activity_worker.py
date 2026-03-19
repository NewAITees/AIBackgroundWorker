"""lifelog-system の ActivityCollector を timeline-app へ橋渡しする worker。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import logging
import sqlite3
import threading
from typing import Any

from pathlib import Path

from ..config import config
from .paths import get_latest_sqlite_id, lifelog_src, resolve_lifelog_path

logger = logging.getLogger(__name__)


def _load_lifelog_classes():
    import sys

    src_path = str(lifelog_src())
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from lifelog.collectors.activity_collector import ActivityCollector
    from lifelog.database.db_manager import DatabaseManager
    from lifelog.utils.config import Config, PrivacyConfig

    return ActivityCollector, DatabaseManager, Config, PrivacyConfig


@dataclass
class ActivityWorkerStatus:
    running: bool = False
    collector_started: bool = False
    db_path: str | None = None
    last_interval_id: int | None = None
    last_sync_at: str | None = None
    last_error: str | None = None


class ActivityWorker:
    """既存 lifelog 収集だけを担う worker。"""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = threading.Event()
        self._status = ActivityWorkerStatus()
        self._collector: Any | None = None
        self._poll_seconds = config.lifelog.activity_sync_seconds

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="timeline-activity-worker")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None

    def get_status(self) -> dict[str, Any]:
        return asdict(self._status)

    async def sync_once(self) -> int:
        return await asyncio.to_thread(self._sync_once_blocking)

    async def _run(self) -> None:
        self._status.running = True
        self._status.last_error = None
        try:
            await asyncio.to_thread(self._blocking_loop)
        except Exception as exc:  # noqa: BLE001
            self._status.last_error = str(exc)
            logger.exception("activity worker failed")
        finally:
            self._status.running = False
            self._status.collector_started = False

    def _blocking_loop(self) -> None:
        ActivityCollector, DatabaseManager, Config, PrivacyConfig = _load_lifelog_classes()
        config_path = resolve_lifelog_path(config.lifelog.config_path)
        privacy_path = resolve_lifelog_path(config.lifelog.privacy_config_path)

        cfg = Config(str(config_path))
        privacy_cfg = PrivacyConfig(str(privacy_path))
        db_path = self._resolve_db_path(cfg)
        db_manager = DatabaseManager(str(db_path))
        collector = ActivityCollector(
            db_manager=db_manager,
            config=cfg._config,
            privacy_config=privacy_cfg._config,
        )
        self._collector = collector
        self._status.db_path = str(db_path)
        if self._status.last_interval_id is None:
            self._status.last_interval_id = get_latest_sqlite_id(db_path, "activity_intervals")

        collector.start_collection()
        self._status.collector_started = True

        try:
            while not self._stop_event.is_set():
                self._sync_once_blocking()
                self._stop_event.wait(timeout=self._poll_seconds)
        finally:
            collector.stop_collection()
            self._collector = None

    def _sync_once_blocking(self) -> int:
        db_path = self._status.db_path or str(resolve_lifelog_path(config.lifelog.db_path))
        self._status.db_path = db_path
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        last_seen = self._status.last_interval_id or 0
        cursor.execute(
            """
            SELECT
                i.id,
                i.start_ts,
                i.end_ts,
                a.process_name,
                i.domain,
                i.is_idle,
                i.duration_seconds
            FROM activity_intervals i
            JOIN apps a ON i.app_id = a.app_id
            WHERE i.id > ?
            ORDER BY i.id ASC
            LIMIT 100
            """,
            (last_seen,),
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return 0

        for row in rows:
            self._status.last_interval_id = int(row["id"])

        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return len(rows)

    def _resolve_db_path(self, cfg: Any) -> Path:
        configured = resolve_lifelog_path(config.lifelog.db_path)
        if configured.exists():
            return configured

        legacy_value = cfg.get("database.path", "data/lifelog.db")
        legacy_path = Path(legacy_value)
        if legacy_path.is_absolute():
            return legacy_path.resolve()
        return (resolve_lifelog_path(config.lifelog.root_dir) / legacy_path).resolve()


activity_worker = ActivityWorker()
