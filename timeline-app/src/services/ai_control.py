"""AI 処理の一時停止状態を管理する。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class AIControlState:
    paused: bool = False
    paused_at: str | None = None
    resumed_at: str | None = None


class AIControlService:
    def __init__(self) -> None:
        self._state = AIControlState()

    def pause(self) -> dict[str, Any]:
        if not self._state.paused:
            self._state.paused = True
            self._state.paused_at = datetime.now(UTC).isoformat()
        return self.get_status()

    def resume(self) -> dict[str, Any]:
        self._state.paused = False
        self._state.resumed_at = datetime.now(UTC).isoformat()
        return self.get_status()

    def is_paused(self) -> bool:
        return self._state.paused

    def get_status(self) -> dict[str, Any]:
        return asdict(self._state)


ai_control_service = AIControlService()
