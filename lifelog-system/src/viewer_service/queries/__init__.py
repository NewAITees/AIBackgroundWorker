"""Query functions for viewer service."""

from .lifelog_queries import get_daily_summary, get_recent_timeline, get_health_metrics
from .browser_queries import get_browser_data, search_browser_history
from .info_queries import get_info_data, get_latest_news, get_reports
from .dashboard_queries import get_dashboard_data

__all__ = [
    "get_daily_summary",
    "get_recent_timeline",
    "get_health_metrics",
    "get_browser_data",
    "search_browser_history",
    "get_info_data",
    "get_latest_news",
    "get_reports",
    "get_dashboard_data",
]
