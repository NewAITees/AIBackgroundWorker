"""
タイムライン API
指定日時周辺の entry 一覧を返す
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query

from ..config import config
from ..models.entry import Entry, EntryStatus, EntryType
from ..routers.workspace import get_open_workspace
from ..storage.daily_reader import read_timeline_entries
from ..storage.entry_reader import read_entries

router = APIRouter()
TODO_FUTURE_OFFSET = timedelta(minutes=5)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/timeline")
async def get_timeline(
    around: datetime = Query(default=None, description="基準日時（省略時は現在）"),
    before: int = Query(default=24, description="基準から何時間前まで取得するか"),
    after: int = Query(default=24, description="基準から何時間後まで取得するか"),
):
    """指定日時周辺の entry 一覧を返す。"""
    workspace = get_open_workspace()
    if around is None:
        around = datetime.now(timezone.utc)
    around_utc = _as_utc(around)

    start_at = around_utc - timedelta(hours=before)
    end_at = around_utc + timedelta(hours=after)
    entries = read_timeline_entries(
        workspace["path"],
        config.workspace.dirs.daily,
        start_at=start_at,
        end_at=end_at,
    )
    active_todos = [
        _project_active_todo(entry)
        for entry in read_entries(workspace["path"], config.workspace.dirs.articles)
        if entry.type == EntryType.todo and entry.status == EntryStatus.active
    ]
    merged_entries = {entry.id: entry for entry in entries}
    for entry in active_todos:
        if _as_utc(start_at) <= _as_utc(entry.timestamp) <= _as_utc(end_at):
            merged_entries[entry.id] = entry

    todo_entries = sorted(
        [
            entry
            for entry in merged_entries.values()
            if entry.type == EntryType.todo and entry.status == EntryStatus.active
        ],
        key=lambda entry: _as_utc(entry.timestamp),
    )
    timeline_entries = [
        entry
        for entry in merged_entries.values()
        if not (entry.type == EntryType.todo and entry.status == EntryStatus.active)
    ]
    past_entries = sorted(
        [entry for entry in timeline_entries if _as_utc(entry.timestamp) <= around_utc],
        key=lambda entry: _as_utc(entry.timestamp),
    )
    future_entries = sorted(
        [entry for entry in timeline_entries if _as_utc(entry.timestamp) > around_utc],
        key=lambda entry: _as_utc(entry.timestamp),
    )

    return {
        "around": around_utc.isoformat(),
        "before_hours": before,
        "after_hours": after,
        "entries": [
            entry.model_dump(mode="json")
            for entry in sorted(merged_entries.values(), key=lambda entry: _as_utc(entry.timestamp))
        ],
        "past_entries": [entry.model_dump(mode="json") for entry in past_entries],
        "todo_entries": [entry.model_dump(mode="json") for entry in todo_entries],
        "future_entries": [entry.model_dump(mode="json") for entry in future_entries],
    }


def _project_active_todo(entry: Entry) -> Entry:
    now = datetime.now(timezone.utc)
    if entry.meta.recurring_enabled:
        return entry
    entry_timestamp = _as_utc(entry.timestamp)
    if entry_timestamp > now:
        return entry
    due_at = entry.meta.due_at
    if due_at is not None and _as_utc(due_at) > now:
        return entry.model_copy(update={"timestamp": _as_utc(due_at)})
    return entry.model_copy(update={"timestamp": now + TODO_FUTURE_OFFSET})
