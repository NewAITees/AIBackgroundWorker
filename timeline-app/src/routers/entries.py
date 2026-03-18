"""
entry CRUD API
chat / event / diary / todo の作成・取得・更新
"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from ..models.entry import Entry, EntryCreate, EntryUpdate, EntrySource

router = APIRouter()

# インメモリストア（M1 stub。後で Markdown / DB に置き換える）
_entries: dict[str, Entry] = {}

# ワークスペースパスは後で workspace モジュールから取得する
_DEFAULT_WORKSPACE = ""


@router.post("/entries", response_model=Entry, status_code=201)
async def create_entry(req: EntryCreate):
    """entry を新規作成する"""
    entry_id = f"{datetime.now(timezone.utc).isoformat()}-{req.type.value}-{uuid.uuid4().hex[:6]}"
    entry = Entry(
        id=entry_id,
        type=req.type,
        title=req.title,
        content=req.content,
        timestamp=req.timestamp or datetime.now(timezone.utc),
        source=req.source,
        workspace_path=_DEFAULT_WORKSPACE,
        links=req.links,
        related_ids=req.related_ids,
        meta=req.meta,
    )
    _entries[entry_id] = entry
    return entry


@router.get("/entries/{entry_id}", response_model=Entry)
async def get_entry(entry_id: str):
    """右ペイン用の entry 詳細を返す"""
    entry = _entries.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    return entry


@router.patch("/entries/{entry_id}", response_model=Entry)
async def update_entry(entry_id: str, req: EntryUpdate):
    """entry を更新する"""
    entry = _entries.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="entry が見つかりません")

    update_data = req.model_dump(exclude_none=True)
    updated = entry.model_copy(update=update_data)
    _entries[entry_id] = updated
    return updated
