"""APScheduler の初期化とアプリ全体で使うシングルトン管理。"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..config import config
from ..services.worker_control_service import worker_control_service
from .activity_worker import activity_worker
from .analysis_pipeline_worker import analysis_pipeline_worker
from .browser_worker import browser_worker
from .daily_digest_worker import daily_digest_worker
from .hourly_summary_worker import hourly_summary_worker
from .info_worker import info_worker
from .windows_foreground_worker import windows_foreground_worker

_scheduler: AsyncIOScheduler | None = None


def _configure_scheduler_logging() -> None:
    """定常の job 実行ログを抑えて重要な警告だけ見えるようにする。"""
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)


def _guarded(worker_id: str, fn: Any):
    """worker_control_service の enabled フラグを確認してから実行するラッパー。"""

    async def _inner() -> None:
        if worker_control_service.is_enabled(worker_id):
            await fn()

    _inner.__name__ = f"{worker_id}_guarded"
    return _inner


def get_scheduler() -> AsyncIOScheduler:
    """AsyncIOScheduler のシングルトンを返す。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    """未起動なら scheduler を開始する。"""
    _configure_scheduler_logging()
    scheduler = get_scheduler()
    if scheduler.get_job("activity-sync") is None:
        scheduler.add_job(
            _guarded("activity", activity_worker.sync_once),
            "interval",
            seconds=config.lifelog.activity_sync_seconds,
            id="activity-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=config.lifelog.activity_sync_seconds,
        )
    if scheduler.get_job("browser-sync") is None:
        scheduler.add_job(
            _guarded("browser", browser_worker.sync_once),
            "interval",
            seconds=config.lifelog.browser_import_seconds,
            id="browser-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=config.lifelog.browser_import_seconds,
        )
    if scheduler.get_job("info-sync") is None:
        scheduler.add_job(
            _guarded("info", info_worker.sync_once),
            "interval",
            seconds=config.lifelog.info_collect_seconds,
            id="info-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=config.lifelog.info_collect_seconds,
        )
    if scheduler.get_job("analysis-pipeline-sync") is None:
        scheduler.add_job(
            _guarded("analysis", analysis_pipeline_worker.sync_once),
            "interval",
            seconds=config.lifelog.analysis_pipeline_seconds,
            id="analysis-pipeline-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=config.lifelog.analysis_pipeline_seconds,
        )
    if scheduler.get_job("hourly-summary-sync") is None:
        scheduler.add_job(
            _guarded("hourly_summary", hourly_summary_worker.sync_once),
            "interval",
            seconds=config.lifelog.hourly_summary_seconds,
            id="hourly-summary-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=config.lifelog.hourly_summary_seconds,
        )
    if scheduler.get_job("daily-digest-sync") is None:
        scheduler.add_job(
            _guarded("daily_digest", daily_digest_worker.sync_once),
            "cron",
            hour=config.lifelog.daily_digest_hour,
            minute=config.lifelog.daily_digest_minute,
            id="daily-digest-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=3600,
        )
    if scheduler.get_job("windows-foreground-merge") is None:
        scheduler.add_job(
            _guarded("windows", windows_foreground_worker.sync_once),
            "interval",
            seconds=config.lifelog.windows_foreground_merge_seconds,
            id="windows-foreground-merge",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            misfire_grace_time=config.lifelog.windows_foreground_merge_seconds,
        )
    if not scheduler.running:
        scheduler.start()
    return scheduler


def shutdown_scheduler() -> None:
    """起動済み scheduler を停止する。"""
    global _scheduler
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=True)
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
