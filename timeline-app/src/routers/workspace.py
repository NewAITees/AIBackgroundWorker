"""
ワークスペース管理 API
対象フォルダ（Obsidian Vault または通常フォルダ）を開く・確認する

- config.yaml の workspace.default_path をデフォルトワークスペースとして使う
- 開発中は YellowMable を汚さないよう、config.yaml で dev 用パスを指定する
- WSL / Windows パス変換は config.to_local_path() を通す
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import config, to_local_path

router = APIRouter()

# 起動中のワークスペース状態（インメモリ、後でDB等に移す）
_workspace: dict = {}


def _subdirs_state(base_path: Path) -> dict[str, bool]:
    return {
        "daily": (base_path / config.workspace.dirs.daily).exists(),
        "articles": (base_path / config.workspace.dirs.articles).exists(),
    }


def _ensure_workspace_subdirs(base_path: Path) -> None:
    (base_path / config.workspace.dirs.daily).mkdir(parents=True, exist_ok=True)
    (base_path / config.workspace.dirs.articles).mkdir(parents=True, exist_ok=True)


def _workspace_payload(base_path: Path, mode: str) -> dict:
    return {
        "opened": True,
        "path": str(base_path.resolve()),
        "mode": mode,
        "subdirs": _subdirs_state(base_path),
    }


def _init_default_workspace() -> None:
    """config.yaml の default_path が設定されていれば初期値として使う"""
    raw = config.workspace.default_path
    if not raw:
        return
    local = to_local_path(raw)
    p = Path(local)
    if p.exists() and p.is_dir():
        mode = "obsidian" if (p / ".obsidian").exists() else "standalone"
        _ensure_workspace_subdirs(p)
        _workspace.update(_workspace_payload(p, mode))


_init_default_workspace()


class WorkspaceOpenRequest(BaseModel):
    path: str


def get_open_workspace() -> dict:
    """他APIから使うワークスペース情報。未設定時は 400 を返す。"""
    if not _workspace:
        raise HTTPException(status_code=400, detail="ワークスペースが未設定です")
    return _workspace


def peek_workspace() -> dict | None:
    """health などから使う現在のワークスペース状態。未設定時は None。"""
    return _workspace or None


def resolve_workspace_path() -> str | None:
    """workers から使うワークスペースパス取得。未設定時は default_path を使う。"""
    workspace = peek_workspace()
    if workspace:
        return workspace["path"]
    if config.workspace.default_path:
        return str(Path(to_local_path(config.workspace.default_path)).resolve())
    return None


@router.get("/workspace")
async def get_workspace():
    """現在開いているワークスペース情報を返す"""
    if not _workspace:
        return {"opened": False, "path": None, "mode": None, "subdirs": {}}
    return _workspace


@router.post("/workspace/open")
async def open_workspace(req: WorkspaceOpenRequest):
    """ワークスペースを開く。Obsidian Vault なら連携モード、通常フォルダなら独立モード"""
    local = to_local_path(req.path)
    p = Path(local)

    if not p.exists():
        raise HTTPException(status_code=404, detail=f"パスが存在しません: {req.path}")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="ディレクトリを指定してください")

    mode = "obsidian" if (p / ".obsidian").exists() else "standalone"
    _ensure_workspace_subdirs(p)
    _workspace.clear()
    _workspace.update(_workspace_payload(p, mode))
    return _workspace
