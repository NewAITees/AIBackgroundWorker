"""ブラウザ履歴を ai_secretary.db から timeline へ同期する worker。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Any

from ..config import config
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from ..routers.workspace import resolve_workspace_path
from ..storage.persistence import persist_entry
from .paths import get_latest_sqlite_id, lifelog_src, resolve_lifelog_path


def _load_browser_classes():
    import sys

    src_path = str(lifelog_src())
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from browser_history.importer import BraveHistoryImporter
    from browser_history.repository import BrowserHistoryRepository

    return BraveHistoryImporter, BrowserHistoryRepository


@dataclass
class BrowserWorkerStatus:
    running: bool = False
    db_path: str | None = None
    last_history_id: int | None = None
    last_visit_time: str | None = None
    last_sync_at: str | None = None
    last_import_count: int = 0
    last_error: str | None = None


class BrowserWorker:
    def __init__(self) -> None:
        self._status = BrowserWorkerStatus()
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
        info_db_path = resolve_lifelog_path(config.lifelog.info_db_path)
        self._status.db_path = str(info_db_path)
        BraveHistoryImporter, BrowserHistoryRepository = _load_browser_classes()
        repository = BrowserHistoryRepository(info_db_path)

        if self._status.last_history_id is None:
            self._status.last_history_id = get_latest_sqlite_id(info_db_path, "browser_history")
            self._status.last_visit_time = self._get_latest_visit_time(info_db_path)

        importer = BraveHistoryImporter(repository)
        imported_count = 0
        try:
            since = (
                datetime.fromisoformat(self._status.last_visit_time)
                if self._status.last_visit_time
                else None
            )
            imported_count = importer.import_history(since=since)
        except FileNotFoundError as exc:
            self._status.last_error = str(exc)
        self._status.last_import_count = imported_count

        rows = self._fetch_new_history_rows(info_db_path, self._status.last_history_id or 0)
        if not rows:
            self._status.last_sync_at = datetime.now(UTC).isoformat()
            return 0

        workspace_path = resolve_workspace_path()
        synced = 0
        for row in rows:
            self._status.last_history_id = int(row["id"])
            self._status.last_visit_time = str(row["visit_time"])
            if not workspace_path:
                continue
            entry = self._row_to_entry(workspace_path, row, str(info_db_path))
            persist_entry(workspace_path, entry)
            synced += 1

        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return synced

    def _get_latest_visit_time(self, db_path: Path) -> str | None:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT visit_time FROM browser_history ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return str(row[0]) if row and row[0] else None

    def _fetch_new_history_rows(self, db_path: Path, last_history_id: int) -> list[sqlite3.Row]:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, url, title, visit_time, source_browser, visit_count
            FROM browser_history
            WHERE id > ?
            ORDER BY id ASC
            LIMIT 200
            """,
            (last_history_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def _row_to_entry(self, workspace_path: str, row: sqlite3.Row, db_path: str) -> Entry:
        visited_at = datetime.fromisoformat(str(row["visit_time"])).astimezone(UTC)
        url = str(row["url"])
        title = row["title"] or url
        source_browser = row["source_browser"] or "browser"
        content = f"{title}\n{url}\n閲覧ブラウザ: {source_browser}\n訪問回数: {row['visit_count']}"

        return Entry(
            id=f"browser-history-{row['id']}",
            type=EntryType.memo,
            title=title[:120],
            content=content,
            timestamp=visited_at,
            status=EntryStatus.active,
            source=EntrySource.imported,
            workspace_path=workspace_path,
            meta=EntryMeta(source_path=db_path),
        )


browser_worker = BrowserWorker()
