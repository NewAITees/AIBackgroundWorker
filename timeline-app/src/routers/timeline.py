"""
タイムライン API
指定日時周辺の entry 一覧を返す
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query

from ..config import config
from ..models.entry import EntryStatus, EntryType
from ..routers.workspace import get_open_workspace
from ..storage.daily_reader import read_timeline_entries
from ..storage.todo_control import read_todo_control

router = APIRouter()


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
    todo_entries = sorted(
        read_todo_control(workspace["path"], config.workspace.dirs.todo_control),
        key=lambda entry: _as_utc(entry.timestamp),
    )
    timeline_entries = [
        entry
        for entry in entries
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

    all_entries = sorted(
        timeline_entries + todo_entries,
        key=lambda entry: _as_utc(entry.timestamp),
    )
    return {
        "around": around_utc.isoformat(),
        "before_hours": before,
        "after_hours": after,
        "entries": [entry.model_dump(mode="json") for entry in all_entries],
        "past_entries": [entry.model_dump(mode="json") for entry in past_entries],
        "todo_entries": [entry.model_dump(mode="json") for entry in todo_entries],
        "future_entries": [entry.model_dump(mode="json") for entry in future_entries],
    }
