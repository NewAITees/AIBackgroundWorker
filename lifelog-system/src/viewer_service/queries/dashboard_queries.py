"""Dashboard aggregation queries.

各データソース（lifelog, browser, info_collector）のクエリを統合し、
DashboardDataとして返す。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import DashboardData, DashboardParams
from .lifelog_queries import get_daily_summary
from .browser_queries import get_browser_data
from .info_queries import get_info_data


def get_dashboard_data(
    lifelog_db: Path,
    info_db: Path,
    params: DashboardParams,
) -> DashboardData:
    """統合ダッシュボードデータを取得.

    Args:
        lifelog_db: lifelog.dbのパス
        info_db: ai_secretary.dbのパス
        params: クエリパラメータ

    Returns:
        DashboardData: 統合ダッシュボードデータ
    """
    # 日付のデフォルト値（今日）
    date = params.date or datetime.now().strftime("%Y-%m-%d")

    # Lifelogデータ
    lifelog_data = get_daily_summary(lifelog_db, date)

    # Browserデータ
    browser_data = get_browser_data(info_db, date=date, limit=params.limit)

    # Info Collectorデータ
    info_data = get_info_data(
        info_db, date=date, limit=params.limit, full=params.full
    )

    return DashboardData(
        generated_at=datetime.now(),
        lifelog=lifelog_data,
        browser=browser_data,
        info=info_data,
    )
