"""APScheduler の初期化とアプリ全体で使うシングルトン管理。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """AsyncIOScheduler のシングルトンを返す。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    """未起動なら scheduler を開始する。"""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
    return scheduler


def shutdown_scheduler() -> None:
    """起動済み scheduler を停止する。"""
    global _scheduler
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
    _scheduler = None


def get_scheduler_status() -> Mapping[str, Any]:
    """health 用に scheduler の状態を返す。"""
    scheduler = get_scheduler()
    state = getattr(scheduler.state, "name", str(scheduler.state))
    return {
        "enabled": True,
        "running": scheduler.running,
        "state": state,
        "job_count": len(scheduler.get_jobs()),
    }
