"""週次レビュー API。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from ..config import config
from ..routers.workspace import get_open_workspace
from ..services.behavior_review import build_weekly_review_payload
from ..storage.entry_reader import read_entries

router = APIRouter()


@router.get("/reviews/weekly")
async def get_weekly_review(
    anchor_date: date | None = Query(default=None, description="レビュー基準日"),
):
    workspace = get_open_workspace()
    target = anchor_date or date.today()
    entries = read_entries(workspace["path"], config.workspace.dirs.articles)
    return build_weekly_review_payload(entries, target, config.behavior)
