"""各 worker の有効/無効フラグを管理するサービス。"""

from __future__ import annotations

from typing import Any

# worker_id → デフォルト有効フラグ
_WORKER_DEFAULTS: dict[str, bool] = {
    "activity": True,
    "browser": True,
    "info": True,
    "analysis": True,
    "hourly_summary": True,
    "daily_digest": True,
    "windows": True,
}


class WorkerControlService:
    def __init__(self) -> None:
        self._enabled: dict[str, bool] = dict(_WORKER_DEFAULTS)

    def is_enabled(self, worker_id: str) -> bool:
        return self._enabled.get(worker_id, True)

    def set_enabled(self, worker_id: str, enabled: bool) -> None:
        if worker_id in _WORKER_DEFAULTS:
            self._enabled[worker_id] = enabled

    def get_all(self) -> dict[str, Any]:
        return {"workers": {wid: self._enabled.get(wid, True) for wid in _WORKER_DEFAULTS}}

    def update_all(self, states: dict[str, bool]) -> None:
        for wid, val in states.items():
            self.set_enabled(wid, bool(val))


worker_control_service = WorkerControlService()
