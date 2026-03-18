"""lifelog-system の ActivityCollector を timeline-app へ橋渡しする worker。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import logging
import sqlite3
import threading
from typing import Any

from ..config import config, to_local_path
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from ..routers.workspace import peek_workspace
from ..storage.daily_writer import upsert_entry_in_daily
from ..storage.entry_writer import write_entry

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _lifelog_root() -> Path:
    return Path(to_local_path(config.lifelog.root_dir))


def _lifelog_src() -> Path:
    return _lifelog_root() / "src"


def _load_lifelog_classes():
    import sys

    src_path = str(_lifelog_src())
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
    """既存 lifelog 収集と timeline 投影を束ねる最小 worker。"""

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
        return {
            "running": self._status.running,
            "collector_started": self._status.collector_started,
            "db_path": self._status.db_path,
            "last_interval_id": self._status.last_interval_id,
            "last_sync_at": self._status.last_sync_at,
            "last_error": self._status.last_error,
        }

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
        config_path = self._resolve_lifelog_path(config.lifelog.config_path)
        privacy_path = self._resolve_lifelog_path(config.lifelog.privacy_config_path)

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
            self._status.last_interval_id = self._get_latest_interval_id(str(db_path))

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
        db_path = self._status.db_path or str(self._resolve_lifelog_path(config.lifelog.db_path))
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

        workspace = peek_workspace()
        workspace_path = None
        if workspace:
            workspace_path = workspace["path"]
        elif config.workspace.default_path:
            workspace_path = str(Path(to_local_path(config.workspace.default_path)).resolve())

        synced = 0
        for row in rows:
            self._status.last_interval_id = int(row["id"])
            if not workspace_path:
                continue

            entry = self._row_to_entry(workspace_path, row, db_path)
            write_entry(workspace_path, config.workspace.dirs.articles, entry)
            upsert_entry_in_daily(workspace_path, config.workspace.dirs.daily, entry)
            synced += 1

        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return synced

    def _get_latest_interval_id(self, db_path: str) -> int:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM activity_intervals")
        row = cursor.fetchone()
        conn.close()
        return int(row[0] or 0)

    def _resolve_lifelog_path(self, raw_path: str) -> Path:
        path = Path(to_local_path(raw_path))
        if path.is_absolute():
            return path.resolve()
        return (_repo_root() / path).resolve()

    def _resolve_db_path(self, cfg: Any) -> Path:
        configured = self._resolve_lifelog_path(config.lifelog.db_path)
        if configured.exists():
            return configured

        legacy_value = cfg.get("database.path", "data/lifelog.db")
        legacy_path = Path(legacy_value)
        if legacy_path.is_absolute():
            return legacy_path.resolve()
        return (_lifelog_root() / legacy_path).resolve()

    def _row_to_entry(self, workspace_path: str, row: sqlite3.Row, db_path: str) -> Entry:
        process_name = row["process_name"] or "unknown"
        domain = row["domain"]
        duration_seconds = max(int(row["duration_seconds"] or 0), 0)
        is_idle = bool(row["is_idle"])
        started = datetime.fromisoformat(str(row["start_ts"])).astimezone(UTC)
        ended = datetime.fromisoformat(str(row["end_ts"])).astimezone(UTC)

        status_text = "idle" if is_idle else "active"
        title = f"{process_name} の活動"
        if domain:
            title = f"{process_name} / {domain}"
        content = (
            f"{started.isoformat()} から {ended.isoformat()} まで {process_name} を使用。"
            f" 状態は {status_text}、継続時間は {duration_seconds} 秒。"
        )
        if domain:
            content += f" ドメイン: {domain}。"

        return Entry(
            id=f"lifelog-activity-{row['id']}",
            type=EntryType.system_log,
            title=title,
            content=content,
            timestamp=started,
            status=EntryStatus.active,
            source=EntrySource.system,
            workspace_path=workspace_path,
            meta=EntryMeta(source_path=db_path),
        )


activity_worker = ActivityWorker()
