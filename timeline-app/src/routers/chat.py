"""
チャット API
現在地点のチャット入力に対する AI 応答と仮記録候補を返す
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai.ollama_client import OllamaClient, OllamaClientError
from ..config import config
from ..models.entry import Entry, EntryMeta, EntrySource, EntryType
from ..routers.workspace import get_open_workspace
from ..services.ai_control import ai_control_service
from ..storage.persistence import persist_entry

router = APIRouter()
_threads: dict[str, list[dict[str, str]]] = {}


class ChatRequest(BaseModel):
    content: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    entry_candidates: list[dict]  # 仮記録候補（type, title, content）


_ALLOWED_CANDIDATE_TYPES = {
    EntryType.diary.value,
    EntryType.event.value,
    EntryType.todo.value,
    EntryType.memo.value,
}


def _normalize_candidates(raw_candidates: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for item in raw_candidates:
        candidate_type = str(item.get("type", "")).strip()
        content = str(item.get("content", "")).strip()
        title = item.get("title")
        if candidate_type not in _ALLOWED_CANDIDATE_TYPES or not content:
            continue
        candidates.append(
            {
                "type": candidate_type,
                "title": str(title).strip() if title else None,
                "content": content,
            }
        )
    return candidates[:3]


def _save_chat_ai_entry(workspace_path: str, thread_id: str, reply: str) -> Entry:
    entry_id = f"{datetime.now(timezone.utc).isoformat()}-chat_ai-{uuid.uuid4().hex[:6]}"
    entry = Entry(
        id=entry_id,
        type=EntryType.chat_ai,
        title=None,
        content=reply,
        timestamp=datetime.now(timezone.utc),
        source=EntrySource.ai,
        workspace_path=workspace_path,
        meta=EntryMeta(thread_id=thread_id),
    )
    persist_entry(workspace_path, entry)
    return entry


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """チャット入力に AI が応答し、記録候補も返す。"""
    if ai_control_service.is_paused():
        raise HTTPException(status_code=409, detail="AI処理は一時停止中です")

    workspace = get_open_workspace()
    thread_id = req.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    history = _threads.setdefault(thread_id, [])
    history.append({"role": "user", "content": req.content})

    client = OllamaClient(config.ai)
    try:
        result = client.generate_chat_reply(history)
    except OllamaClientError as exc:
        history.pop()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    history.append({"role": "assistant", "content": result.reply})
    _save_chat_ai_entry(workspace["path"], thread_id, result.reply)

    return ChatResponse(
        reply=result.reply,
        thread_id=thread_id,
        entry_candidates=_normalize_candidates(result.entry_candidates),
    )
