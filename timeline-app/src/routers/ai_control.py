"""AI 一時停止 / 再開 API。"""

import asyncio
import logging

from fastapi import APIRouter

from ..services.ai_control import ai_control_service
from ..workers.analysis_pipeline_worker import analysis_pipeline_worker
from ..workers.daily_digest_worker import daily_digest_worker
from ..workers.hourly_summary_worker import hourly_summary_worker

logger = logging.getLogger(__name__)
router = APIRouter()


async def _catch_up_after_resume() -> None:
    await analysis_pipeline_worker.sync_once()
    await hourly_summary_worker.sync_once()
    await daily_digest_worker.sync_once()


@router.get("/ai/status")
async def ai_status():
    return ai_control_service.get_status()


@router.post("/ai/pause")
async def ai_pause():
    result = ai_control_service.pause()
    logger.info("AI処理を一時停止しました (paused_at=%s)", result.get("paused_at"))
    return result


@router.post("/ai/resume")
async def ai_resume():
    status = ai_control_service.resume()
    logger.info("AI処理を再開しました (resumed_at=%s)", status.get("resumed_at"))
    asyncio.create_task(_catch_up_after_resume())
    return status
