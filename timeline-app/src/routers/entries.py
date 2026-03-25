"""entry CRUD API。Markdown ファイルを正本として扱う。"""

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai.ollama_client import OllamaClient, OllamaClientError
from ..config import config
from ..models.entry import Entry, EntryCreate, EntryMeta, EntryStatus, EntryType, EntryUpdate
from ..routers.workspace import get_open_workspace
from ..services.ai_control import ai_control_service
from ..services.chat_transcript import append_chat_message
from ..storage.common import article_backup_path, article_path, delete_file_if_exists
from ..storage.entry_reader import read_entry
from ..storage.entry_writer import append_entry_content
from ..storage.daily_writer import upsert_entry_in_daily
from ..storage.persistence import persist_entry
from ..storage.todo_control import find_todo, remove_todo, upsert_todo

router = APIRouter()
TODO_FUTURE_OFFSET = timedelta(minutes=5)


class EntryAiEditRequest(BaseModel):
    instruction: str


class EntryAiEditResponse(BaseModel):
    edited_content: str


class EntryAppendMessageRequest(BaseModel):
    role: str
    content: str


class EntryBackupCleanupResponse(BaseModel):
    deleted: bool


def _backup_article_if_needed(workspace_path: str, entry_id: str) -> None:
    source = article_path(workspace_path, config.workspace.dirs.articles, entry_id)
    backup = article_backup_path(workspace_path, config.workspace.dirs.articles, entry_id)
    if backup.exists():
        return
    shutil.copy2(source, backup)


def _delete_ai_backup(workspace_path: str, entry_id: str) -> bool:
    backup = article_backup_path(workspace_path, config.workspace.dirs.articles, entry_id)
    return delete_file_if_exists(backup)


def _normalize_recurring_meta(
    entry_id: str,
    entry_type: EntryType,
    timestamp: datetime,
    meta: EntryMeta,
) -> EntryMeta:
    if entry_type not in {EntryType.todo, EntryType.todo_done}:
        return meta.model_copy(
            update={
                "recurring_enabled": False,
                "recurring_rule": None,
                "recurring_interval": None,
                "recurring_count": None,
                "recurring_weekdays": [],
                "recurring_series_id": None,
                "recurring_sequence": None,
                "recurring_scheduled_for": None,
            }
        )
    if not meta.recurring_enabled:
        return meta.model_copy(
            update={
                "recurring_enabled": False,
                "recurring_rule": None,
                "recurring_interval": None,
                "recurring_count": None,
                "recurring_weekdays": [],
                "recurring_series_id": None,
                "recurring_sequence": None,
                "recurring_scheduled_for": None,
            }
        )

    interval = max(meta.recurring_interval or 1, 1)
    count = max(meta.recurring_count, 1) if meta.recurring_count else None
    weekdays = sorted({day for day in meta.recurring_weekdays if 0 <= day <= 6})
    if meta.recurring_rule != "custom_weekdays":
        weekdays = []

    return meta.model_copy(
        update={
            "recurring_enabled": True,
            "recurring_rule": meta.recurring_rule or "daily",
            "recurring_interval": interval,
            "recurring_count": count,
            "recurring_weekdays": weekdays,
            "recurring_series_id": meta.recurring_series_id or f"series-{entry_id}",
            "recurring_sequence": meta.recurring_sequence or 1,
            "recurring_scheduled_for": meta.recurring_scheduled_for or timestamp.date().isoformat(),
        }
    )


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
    entry = entry.model_copy(
        update={
            "meta": _normalize_recurring_meta(entry.id, entry.type, entry.timestamp, entry.meta)
        }
    )
    if entry.type == EntryType.todo and entry.status == EntryStatus.active:
        upsert_todo(workspace_path, config.workspace.dirs.todo_control, entry)
    else:
        persist_entry(workspace_path, entry)
    return entry


@router.get("/entries/{entry_id}", response_model=Entry)
async def get_entry(entry_id: str):
    """右ペイン用の entry 詳細を返す"""
    workspace = get_open_workspace()
    workspace_path = workspace["path"]
    try:
        entry = find_todo(workspace_path, config.workspace.dirs.todo_control, entry_id)
        if entry is not None:
            return entry
        return read_entry(workspace_path, config.workspace.dirs.articles, entry_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/entries/{entry_id}", response_model=Entry)
async def update_entry(entry_id: str, req: EntryUpdate):
    """entry を更新する"""
    workspace = get_open_workspace()
    workspace_path = workspace["path"]

    in_todo_control = False
    try:
        in_todo_control_entry = find_todo(
            workspace_path, config.workspace.dirs.todo_control, entry_id
        )
        if in_todo_control_entry is not None:
            entry = in_todo_control_entry
            in_todo_control = True
        else:
            entry = read_entry(workspace_path, config.workspace.dirs.articles, entry_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    update_data = req.model_dump(exclude_none=True)

    # meta はフィールド単位でマージする（全置換しない）
    if req.meta is not None:
        merged_meta = entry.meta.model_copy(update=req.meta.model_dump(exclude_unset=True))
        update_data["meta"] = merged_meta

    # todo → todo_done 完了時は timestamp を完了時刻へ更新（手動指定がなければ）
    if req.type == EntryType.todo_done and req.timestamp is None:
        update_data["timestamp"] = datetime.now(timezone.utc)

    updated = entry.model_copy(update=update_data)
    updated = updated.model_copy(
        update={
            "meta": _normalize_recurring_meta(
                updated.id,
                updated.type,
                updated.timestamp,
                updated.meta,
            )
        }
    )

    is_active_todo = updated.type == EntryType.todo and updated.status == EntryStatus.active
    if is_active_todo:
        upsert_todo(workspace_path, config.workspace.dirs.todo_control, updated)
    else:
        if in_todo_control:
            remove_todo(workspace_path, config.workspace.dirs.todo_control, entry_id)
        persist_entry(workspace_path, updated)
        _delete_ai_backup(workspace_path, entry_id)
    return updated


@router.post("/entries/{entry_id}/ai_edit", response_model=EntryAiEditResponse)
async def ai_edit_entry(entry_id: str, req: EntryAiEditRequest):
    """AI に本文編集を依頼し、プレビュー用の編集済み全文を返す。"""
    if ai_control_service.is_paused():
        raise HTTPException(status_code=409, detail="AI処理は一時停止中です")

    instruction = req.instruction.strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction を入力してください")

    workspace = get_open_workspace()
    workspace_path = workspace["path"]

    try:
        entry = find_todo(workspace_path, config.workspace.dirs.todo_control, entry_id)
        if entry is None:
            entry = read_entry(workspace_path, config.workspace.dirs.articles, entry_id)
            _backup_article_if_needed(workspace_path, entry_id)
        edited_content = OllamaClient(config.ai).edit_entry_content(
            current_content=entry.content,
            instruction=instruction,
            context={"entry_id": entry_id},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    except OllamaClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EntryAiEditResponse(edited_content=edited_content)


@router.delete("/entries/{entry_id}/ai_edit_backup", response_model=EntryBackupCleanupResponse)
async def delete_ai_edit_backup(entry_id: str):
    workspace = get_open_workspace()
    deleted = _delete_ai_backup(workspace["path"], entry_id)
    return EntryBackupCleanupResponse(deleted=deleted)


@router.post("/entries/{entry_id}/append_message", response_model=Entry)
async def append_entry_message(entry_id: str, req: EntryAppendMessageRequest):
    """chat entry の本文末尾へ会話メッセージを追記する。"""
    workspace = get_open_workspace()
    workspace_path = workspace["path"]
    role = req.role.strip().lower()
    content = req.content.strip()
    if role not in {"user", "assistant"}:
        raise HTTPException(status_code=400, detail="role は user または assistant を指定してください")
    if not content:
        raise HTTPException(status_code=400, detail="content を入力してください")

    try:
        entry = read_entry(workspace_path, config.workspace.dirs.articles, entry_id)
        if entry.type not in {EntryType.chat_user, EntryType.chat_ai}:
            raise HTTPException(status_code=400, detail="chat entry のみ追記できます")
        appended_content = append_chat_message(entry.content, role, content)
        appended_only = appended_content[len(entry.content.rstrip()) :].strip()
        append_entry_content(
            workspace_path,
            config.workspace.dirs.articles,
            entry_id,
            appended_only,
        )
        updated = read_entry(workspace_path, config.workspace.dirs.articles, entry_id)
        upsert_entry_in_daily(workspace_path, config.workspace.dirs.daily, updated)
        return updated
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="entry が見つかりません")
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class MigrateResult(BaseModel):
    migrated: int
    skipped: int


@router.post("/entries/migrate-todos-to-control", response_model=MigrateResult)
async def migrate_todos_to_control():
    """articles/ 内の active todo を todo_control.md へ移行する。"""
    from ..storage.entry_reader import read_entries

    workspace = get_open_workspace()
    workspace_path = workspace["path"]

    all_entries = read_entries(workspace_path, config.workspace.dirs.articles)
    migrated = 0
    skipped = 0
    for entry in all_entries:
        if entry.type == EntryType.todo and entry.status == EntryStatus.active:
            upsert_todo(workspace_path, config.workspace.dirs.todo_control, entry)
            path = article_path(workspace_path, config.workspace.dirs.articles, entry.id)
            delete_file_if_exists(path)
            migrated += 1
        else:
            skipped += 1
    return MigrateResult(migrated=migrated, skipped=skipped)
