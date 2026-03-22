"""RSS / ニュース収集を timeline-app に橋渡しする worker。"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import Any

from ..config import config
from .paths import get_latest_sqlite_id, resolve_lifelog_path


@dataclass
class InfoWorkerStatus:
    running: bool = False
    db_path: str | None = None
    config_dir: str | None = None
    last_info_id: int | None = None
    last_sync_at: str | None = None
    last_collect_summary: dict[str, Any] | None = None
    last_error: str | None = None


class InfoWorker:
    def __init__(self) -> None:
        self._status = InfoWorkerStatus()
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
        db_path = resolve_lifelog_path(config.lifelog.info_db_path)
        config_dir = resolve_lifelog_path(config.lifelog.info_config_dir)
        self._status.db_path = str(db_path)
        self._status.config_dir = str(config_dir)

        if self._status.last_info_id is None:
            self._status.last_info_id = get_latest_sqlite_id(db_path, "collected_info")

        summary: dict[str, Any] = {}
        try:
            summary = self._run_info_collection()
        except Exception as exc:  # noqa: BLE001
            self._status.last_error = str(exc)
            summary["error"] = str(exc)
        self._status.last_collect_summary = summary

        rows = self._fetch_new_info_rows(db_path, self._status.last_info_id or 0)
        if not rows:
            self._status.last_sync_at = datetime.now(UTC).isoformat()
            return 0

        for row in rows:
            self._status.last_info_id = int(row["id"])

        self._status.last_sync_at = datetime.now(UTC).isoformat()
        return len(rows)

    def _run_info_collection(self) -> dict[str, Any]:
        lifelog_root = resolve_lifelog_path(config.lifelog.root_dir)
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "src.info_collector.auto_runner",
            "--rss",
            "--news",
            "--limit",
            str(config.lifelog.info_limit),
        ]
        env = {
            **os.environ,
            "PYTHONPATH": str(lifelog_root),
        }
        result = subprocess.run(
            cmd,
            cwd=lifelog_root,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        stdout = result.stdout.strip()
        if not stdout:
            return {}
        return json.loads(stdout)

    def _fetch_new_info_rows(self, db_path: Path, last_info_id: int) -> list[sqlite3.Row]:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, source_type, title, url, content, snippet, published_at, fetched_at, source_name
                FROM collected_info
                WHERE id > ?
                ORDER BY id ASC
                LIMIT 200
                """,
                (last_info_id,),
            )
            return cursor.fetchall()


info_worker = InfoWorker()
