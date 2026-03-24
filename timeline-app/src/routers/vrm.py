"""VRM モデル配信用 API。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import config

router = APIRouter()
_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
_ANIMATION_DIR = _MODELS_DIR / "animation"


def list_vrm_paths() -> list[Path]:
    return sorted(_MODELS_DIR.glob("*.vrm"))


def get_default_vrm_path() -> Path | None:
    candidates = list_vrm_paths()
    return candidates[0] if candidates else None


def get_selected_vrm_path() -> Path | None:
    configured = (config.vrm.model_filename or "").strip()
    if configured:
        path = (_MODELS_DIR / configured).resolve()
        if path.parent == _MODELS_DIR.resolve() and path.suffix.lower() == ".vrm" and path.exists():
            return path
    candidates = sorted(_MODELS_DIR.glob("*.vrm"))
    return candidates[0] if candidates else None


@router.get("/vrm")
async def get_vrm_metadata():
    path = get_selected_vrm_path()
    if path is None:
        raise HTTPException(status_code=404, detail="VRM モデルが見つかりません")
    return {
        "filename": path.name,
        "url": f"/api/vrm/model/{path.name}",
    }


@router.get("/vrm/model/{filename}")
async def get_vrm_model(filename: str):
    path = (_MODELS_DIR / filename).resolve()
    if path.parent != _MODELS_DIR.resolve() or path.suffix.lower() != ".vrm" or not path.exists():
        raise HTTPException(status_code=404, detail="VRM モデルが見つかりません")
    return FileResponse(path, media_type="model/gltf-binary", filename=path.name)


@router.get("/vrm/animation/{filename}")
async def get_vrm_animation(filename: str):
    path = (_ANIMATION_DIR / filename).resolve()
    if (
        path.parent != _ANIMATION_DIR.resolve()
        or path.suffix.lower() != ".fbx"
        or not path.exists()
    ):
        raise HTTPException(status_code=404, detail="VRM アニメーションが見つかりません")
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
