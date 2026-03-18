"""
チャット API
現在地点のチャット入力に対する AI 応答と仮記録候補を返す
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    content: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    entry_candidates: list[dict]  # 仮記録候補（type, title, content）


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """チャット入力に AI が応答し、記録候補も返す（M1 は stub）"""
    import uuid

    thread_id = req.thread_id or f"thread-{uuid.uuid4().hex[:8]}"

    # TODO: AI 接続を実装する
    return ChatResponse(
        reply="（AI未接続）受け取りました：" + req.content,
        thread_id=thread_id,
        entry_candidates=[],
    )
