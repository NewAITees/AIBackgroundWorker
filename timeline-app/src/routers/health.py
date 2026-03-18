from fastapi import APIRouter

from ..ai.ollama_client import OllamaClient
from ..config import config
from ..routers.workspace import peek_workspace

router = APIRouter()


@router.get("/health")
async def health():
    workspace = peek_workspace()
    ollama = OllamaClient(config.ai).check_health()
    return {
        "status": "ok",
        "workspace": {
            "opened": bool(workspace),
            "path": workspace["path"] if workspace else None,
            "mode": workspace["mode"] if workspace else None,
            "subdirs": workspace.get("subdirs", {}) if workspace else {},
        },
        "ollama": ollama,
    }
