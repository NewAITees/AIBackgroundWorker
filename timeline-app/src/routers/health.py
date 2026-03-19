from fastapi import APIRouter

from ..ai.ollama_client import OllamaClient
from ..config import config
from ..routers.workspace import peek_workspace
from ..services.ai_control import ai_control_service
from ..workers.activity_worker import activity_worker
from ..workers.analysis_pipeline_worker import analysis_pipeline_worker
from ..workers.browser_worker import browser_worker
from ..workers.daily_digest_worker import daily_digest_worker
from ..workers.hourly_summary_worker import hourly_summary_worker
from ..workers.info_worker import info_worker
from ..workers.scheduler import get_scheduler_status

router = APIRouter()


@router.get("/health")
async def health():
    import asyncio

    workspace = peek_workspace()
    ollama = await asyncio.to_thread(OllamaClient(config.ai).check_health)
    ollama["paused"] = ai_control_service.get_status()["paused"]
    return {
        "status": "ok",
        "workspace": {
            "opened": bool(workspace),
            "path": workspace["path"] if workspace else None,
            "mode": workspace["mode"] if workspace else None,
            "subdirs": workspace.get("subdirs", {}) if workspace else {},
        },
        "ollama": ollama,
        "workers": {
            "scheduler": get_scheduler_status(),
            "activity": activity_worker.get_status(),
            "browser": browser_worker.get_status(),
            "info": info_worker.get_status(),
            "analysis_pipeline": analysis_pipeline_worker.get_status(),
            "hourly_summary": hourly_summary_worker.get_status(),
            "daily_digest": daily_digest_worker.get_status(),
        },
    }
