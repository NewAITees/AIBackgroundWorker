from fastapi import APIRouter

from ..ai.ollama_client import OllamaClient
from ..config import config
from ..routers.workspace import peek_workspace
from ..workers.activity_worker import activity_worker
from ..workers.browser_worker import browser_worker
from ..workers.info_worker import info_worker
from ..workers.report_worker import report_worker
from ..workers.scheduler import get_scheduler_status

router = APIRouter()


@router.get("/health")
async def health():
    import asyncio

    workspace = peek_workspace()
    ollama = await asyncio.to_thread(OllamaClient(config.ai).check_health)
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
            "report": report_worker.get_status(),
        },
    }
