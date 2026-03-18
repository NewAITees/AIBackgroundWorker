"""
タイムライン API
指定日時周辺の entry 一覧を返す
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/timeline")
async def get_timeline(
    around: datetime = Query(default=None, description="基準日時（省略時は現在）"),
    before: int = Query(default=24, description="基準から何時間前まで取得するか"),
    after: int = Query(default=24, description="基準から何時間後まで取得するか"),
):
    """指定日時周辺の entry 一覧を返す（M1はstub）"""
    if around is None:
        around = datetime.now(timezone.utc)

    # TODO: 実際のデータ取得を実装する
    return {
        "around": around.isoformat(),
        "before_hours": before,
        "after_hours": after,
        "entries": [],
    }
