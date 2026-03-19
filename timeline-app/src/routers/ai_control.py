"""AI 一時停止 / 再開 API。"""

import asyncio

from fastapi import APIRouter

from ..services.ai_control import ai_control_service
from ..workers.analysis_pipeline_worker import analysis_pipeline_worker
from ..workers.daily_digest_worker import daily_digest_worker
from ..workers.hourly_summary_worker import hourly_summary_worker

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
    return ai_control_service.pause()


@router.post("/ai/resume")
async def ai_resume():
    status = ai_control_service.resume()
    asyncio.create_task(_catch_up_after_resume())
    return status
