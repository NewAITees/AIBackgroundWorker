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


def _init_default_workspace() -> None:
    """config.yaml の default_path が設定されていれば初期値として使う"""
    raw = config.workspace.default_path
    if not raw:
        return
    local = to_local_path(raw)
    p = Path(local)
    if p.exists() and p.is_dir():
        mode = "obsidian" if (p / ".obsidian").exists() else "standalone"
        _workspace.update({"path": str(p.resolve()), "mode": mode})


_init_default_workspace()


class WorkspaceOpenRequest(BaseModel):
    path: str


@router.get("/workspace")
async def get_workspace():
    """現在開いているワークスペース情報を返す"""
    if not _workspace:
        return {"opened": False, "path": None, "mode": None}
    return {"opened": True, **_workspace}


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
    _workspace.update({"path": str(p.resolve()), "mode": mode})
    return {"opened": True, "path": str(p.resolve()), "mode": mode}
