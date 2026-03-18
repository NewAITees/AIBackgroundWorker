"""entry CRUD API。Markdown ファイルを正本として扱う。"""

import uuid
from datetime import datetime, time, timezone
from fastapi import APIRouter, HTTPException

from ..config import config
from ..models.entry import Entry, EntryCreate, EntryUpdate
from ..routers.workspace import get_open_workspace
from ..storage.daily_writer import upsert_entry_in_daily
from ..storage.entry_reader import read_entry
from ..storage.entry_writer import write_entry

router = APIRouter()


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
        timestamp = datetime.combine(now.date(), time(23, 59), tzinfo=timezone.utc)
    else:
        timestamp = now

    entry = Entry(
        id=entry_id,
        type=req.type,
        title=req.title,
        content=req.content,
        timestamp=timestamp,
        source=req.source,
        workspace_path=workspace_path,
        links=req.links,
        related_ids=req.related_ids,
        meta=req.meta,
    )
    write_entry(workspace_path, config.workspace.dirs.articles, entry)
    upsert_entry_in_daily(workspace_path, config.workspace.dirs.daily, entry)
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
    updated = entry.model_copy(update=update_data)
    write_entry(workspace_path, config.workspace.dirs.articles, updated)
    upsert_entry_in_daily(workspace_path, config.workspace.dirs.daily, updated)
    return updated
