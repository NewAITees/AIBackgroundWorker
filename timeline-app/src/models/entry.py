"""
entry モデル定義
要件書 21.1.3 の最小 entry 型を Pydantic で定義する
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class EntryType(str, Enum):
    chat_user = "chat_user"
    chat_ai = "chat_ai"
    event = "event"
    diary = "diary"
    todo = "todo"
    todo_done = "todo_done"
    news = "news"
    system_log = "system_log"
    memo = "memo"


class EntryStatus(str, Enum):
    active = "active"
    done = "done"
    archived = "archived"


class EntrySource(str, Enum):
    user = "user"
    ai = "ai"
    imported = "imported"
    system = "system"


class EntryMeta(BaseModel):
    due_at: Optional[datetime] = None
    thread_id: Optional[str] = None
    source_path: Optional[str] = None
    confidence: Optional[float] = None
    completed_at: Optional[datetime] = None


class Entry(BaseModel):
    id: str
    type: EntryType
    title: Optional[str] = None
    summary: Optional[str] = None
    content: str
    timestamp: datetime
    status: EntryStatus = EntryStatus.active
    source: EntrySource
    workspace_path: str
    links: list[str] = []
    related_ids: list[str] = []
    meta: EntryMeta = EntryMeta()


class EntryCreate(BaseModel):
    type: EntryType
    title: Optional[str] = None
    summary: Optional[str] = None
    content: str
    timestamp: Optional[datetime] = None
    source: EntrySource = EntrySource.user
    links: list[str] = []
    related_ids: list[str] = []
    meta: EntryMeta = EntryMeta()


class EntryUpdate(BaseModel):
    type: Optional[EntryType] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    status: Optional[EntryStatus] = None
    links: Optional[list[str]] = None
    related_ids: Optional[list[str]] = None
    meta: Optional[EntryMeta] = None
