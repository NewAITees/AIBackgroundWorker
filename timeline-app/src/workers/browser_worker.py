"""ブラウザ履歴を ai_secretary.db から timeline へ同期する worker。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Any

from ..config import config, to_local_path
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from ..routers.workspace import peek_workspace
from ..storage.daily_writer import upsert_entry_in_daily
from ..storage.entry_writer import write_entry


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _lifelog_src() -> Path:
    root = Path(to_local_path(config.lifelog.root_dir))
    if not root.is_absolute():
        root = (_repo_root() / root).resolve()
    return root / "src"


def _load_browser_classes():
    import sys

    src_path = str(_lifelog_src())
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
        return {
            "running": self._status.running,
            "db_path": self._status.db_path,
            "last_history_id": self._status.last_history_id,
            "last_visit_time": self._status.last_visit_time,
            "last_sync_at": self._status.last_sync_at,
            "last_import_count": self._status.last_import_count,
            "last_error": self._status.last_error,
        }

    async def sync_once(self) -> int:
        async with self._lock:
            self._status.running = True
            try:
                return await asyncio.to_thread(self._sync_once_blocking)
            finally:
                self._status.running = False

    def _sync_once_blocking(self) -> int:
        self._status.last_error = None
        info_db_path = self._resolve_path(config.lifelog.info_db_path)
        self._status.db_path = str(info_db_path)
        BraveHistoryImporter, BrowserHistoryRepository = _load_browser_classes()
        repository = BrowserHistoryRepository(info_db_path)

        if self._status.last_history_id is None:
            self._status.last_history_id = self._get_latest_history_id(info_db_path)
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

        workspace_path = self._resolve_workspace_path()
        synced = 0
        for row in rows:
            self._status.last_history_id = int(row["id"])
            self._status.last_visit_time = str(row["visit_time"])
            if not workspace_path:
                continue
            entry = self._row_to_entry(workspace_path, row, str(info_db_path))
            write_entry(workspace_path, config.workspace.dirs.articles, entry)
            upsert_entry_in_daily(workspace_path, config.workspace.dirs.daily, entry)
            synced += 1

        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return synced

    def _resolve_path(self, raw_path: str) -> Path:
        path = Path(to_local_path(raw_path))
        if path.is_absolute():
            return path.resolve()
        return (_repo_root() / path).resolve()

    def _resolve_workspace_path(self) -> str | None:
        workspace = peek_workspace()
        if workspace:
            return workspace["path"]
        if config.workspace.default_path:
            return str(Path(to_local_path(config.workspace.default_path)).resolve())
        return None

    def _get_latest_history_id(self, db_path: Path) -> int:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM browser_history")
        row = cursor.fetchone()
        conn.close()
        return int(row[0] or 0)

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
