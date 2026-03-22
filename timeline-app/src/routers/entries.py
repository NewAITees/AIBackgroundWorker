"""entry CRUD API。Markdown ファイルを正本として扱う。"""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException

from ..config import config
from ..models.entry import Entry, EntryCreate, EntryType, EntryUpdate
from ..routers.workspace import get_open_workspace
from ..storage.entry_reader import read_entry
from ..storage.persistence import persist_entry

router = APIRouter()
TODO_FUTURE_OFFSET = timedelta(minutes=5)


@router.post("/entries", response_model=Entry, status_code=201)
async def create_entry(req: EntryCreate):
    """entry を新規作成する"""
    workspace = get_open_workspace()
    workspace_path = workspace["path"]

    entry_id = f"{datetime.now(timezone.utc).isoformat()}-{req.type.value}-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    if req.timestamp:
        timestamp = req.timestamp
    elif req.type.value == "todo":
        timestamp = now + TODO_FUTURE_OFFSET
    else:
        timestamp = now

    entry = Entry(
        id=entry_id,
        type=req.type,
        title=req.title,
        summary=req.summary,
        content=req.content,
        timestamp=timestamp,
        source=req.source,
        workspace_path=workspace_path,
        links=req.links,
        related_ids=req.related_ids,
        meta=req.meta,
    )
    persist_entry(workspace_path, entry)
    return entry


@router.get("/entries/{entry_id}", response_model=Entry)
async def get_entry(entry_id: str):
    """右ペイン用の entry 詳細を返す"""
    workspace = get_open_workspace()
    try:
        return read_entry(workspace["path"], config.workspace.dirs.articles, entry_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/entries/{entry_id}", response_model=Entry)
async def update_entry(entry_id: str, req: EntryUpdate):
    """entry を更新する"""
    workspace = get_open_workspace()
    workspace_path = workspace["path"]

    try:
        entry = read_entry(workspace_path, config.workspace.dirs.articles, entry_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    update_data = req.model_dump(exclude_none=True)

    # meta はフィールド単位でマージする（全置換しない）
    if req.meta is not None:
        merged_meta = entry.meta.model_copy(update=req.meta.model_dump(exclude_none=True))
        update_data["meta"] = merged_meta

    # todo → todo_done 完了時は timestamp を完了時刻へ更新（手動指定がなければ）
    if req.type == EntryType.todo_done and req.timestamp is None:
        update_data["timestamp"] = datetime.now(timezone.utc)

    updated = entry.model_copy(update=update_data)
    persist_entry(workspace_path, updated)
    return updated
