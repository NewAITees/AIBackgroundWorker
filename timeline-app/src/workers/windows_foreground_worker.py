"""windows_foreground.jsonl を定期的に lifelog.db へマージする worker。

PowerShell の foreground_logger.ps1 が出力する JSONL を読み込み、
lifelog.db の activity_intervals テーブルへ追記する。
マージ済み行は .processed マーカーファイルで追跡するため再実行しても重複しない。

これにより hourly_summary_worker の summarize_activity() が
Windows フォアグラウンドウィンドウ情報を自動的に素材として使用できる。
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import config, to_local_path
from .paths import repo_root, resolve_lifelog_path


def _load_merge_function():
    import sys

    scripts_path = str(repo_root() / "scripts" / "lifelog")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

    # timeline-app/src が 'src' パッケージとしてキャッシュ済みのため、
    # lifelog-system/src を src.__path__ に追加して src.lifelog.* を解決する
    import src  # noqa: PLC0415

    lifelog_src = str(repo_root() / "lifelog-system" / "src")
    if lifelog_src not in src.__path__:
        src.__path__.append(lifelog_src)

    from merge_windows_logs import merge_windows_logs  # type: ignore[import-not-found]

    return merge_windows_logs


@dataclass
class WindowsForegroundWorkerStatus:
    running: bool = False
    source_file: str | None = None
    db_path: str | None = None
    last_processed: int = 0
    last_skipped: int = 0
    last_sync_at: str | None = None
    last_error: str | None = None


class WindowsForegroundWorker:
    """windows_foreground.jsonl → lifelog.db::activity_intervals のマージを担う worker。"""

    def __init__(self) -> None:
        self._status = WindowsForegroundWorkerStatus()
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

        source_file = self._resolve_source_file()
        db_path = resolve_lifelog_path(config.lifelog.db_path)

        self._status.source_file = str(source_file)
        self._status.db_path = str(db_path)

        if not source_file.exists():
            return 0

        try:
            merge_windows_logs = _load_merge_function()
            processed, skipped = merge_windows_logs(source_file, db_path, mark_processed=True)
            self._status.last_processed = processed
            self._status.last_skipped = skipped
            self._status.last_sync_at = datetime.now(UTC).isoformat()
            return processed
        except Exception as exc:  # noqa: BLE001
            self._status.last_error = str(exc)
            return 0

    def _resolve_source_file(self) -> Path:
        raw = config.lifelog.windows_foreground_log_path
        path = Path(to_local_path(raw))
        if path.is_absolute():
            return path.resolve()
        return (repo_root() / path).resolve()


windows_foreground_worker = WindowsForegroundWorker()
