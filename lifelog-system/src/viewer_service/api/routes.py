"""FastAPI routes for viewer service."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import JSONResponse

from ..models import (
    DashboardData,
    DashboardParams,
    LifelogData,
    BrowserData,
    InfoData,
    BrowserEntry,
    NewsItem,
    ReportItem,
)
from ..queries.dashboard_queries import get_dashboard_data
from ..queries.lifelog_queries import (
    get_daily_summary,
    get_recent_timeline,
    get_health_metrics,
)
from ..queries.browser_queries import get_browser_data, search_browser_history
from ..queries.info_queries import get_info_data, get_latest_news, get_reports


router = APIRouter()


# ============================================================
# Health Check
# ============================================================


@router.get("/health")
async def health_check():
    """ヘルスチェック."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ============================================================
# Dashboard
# ============================================================


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard(
    request: Request,
    date: Optional[str] = Query(None, description="日付 (YYYY-MM-DD)"),
    hours: int = Query(6, ge=1, le=168, description="遡る時間数"),
    limit: int = Query(5, ge=1, le=100, description="取得件数"),
    full: bool = Query(False, description="全文取得フラグ"),
):
    """統合ダッシュボードデータを取得."""
    try:
        lifelog_db = request.app.state.lifelog_db
        info_db = request.app.state.info_db

        params = DashboardParams(date=date, hours=hours, limit=limit, full=full)
        data = get_dashboard_data(lifelog_db, info_db, params)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Lifelog
# ============================================================


@router.get("/lifelog/summary", response_model=LifelogData)
async def get_lifelog_summary(
    request: Request,
    date: Optional[str] = Query(None, description="日付 (YYYY-MM-DD)"),
):
    """ライフログ日次サマリーを取得."""
    try:
        lifelog_db = request.app.state.lifelog_db
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        return get_daily_summary(lifelog_db, date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lifelog/timeline")
async def get_lifelog_timeline(
    request: Request,
    hours: int = Query(6, ge=1, le=168, description="遡る時間数"),
):
    """ライフログタイムラインを取得."""
    try:
        lifelog_db = request.app.state.lifelog_db
        intervals = get_recent_timeline(lifelog_db, hours)
        return {"intervals": intervals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lifelog/health")
async def get_lifelog_health(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="遡る時間数"),
):
    """ヘルスメトリクスを取得."""
    try:
        lifelog_db = request.app.state.lifelog_db
        metrics = get_health_metrics(lifelog_db, hours)
        return {"metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Browser
# ============================================================


@router.get("/browser/recent", response_model=BrowserData)
async def get_browser_recent(
    request: Request,
    date: Optional[str] = Query(None, description="日付 (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
):
    """ブラウザ履歴を取得."""
    try:
        info_db = request.app.state.info_db
        return get_browser_data(info_db, date=date, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser/search")
async def search_browser(
    request: Request,
    q: str = Query(..., min_length=1, description="検索クエリ"),
    limit: int = Query(50, ge=1, le=100, description="取得件数"),
):
    """ブラウザ履歴を検索."""
    try:
        info_db = request.app.state.info_db
        results = search_browser_history(info_db, q, limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Info Collector
# ============================================================


@router.get("/info/latest", response_model=InfoData)
async def get_info_latest(
    request: Request,
    source: Optional[str] = Query(None, description="ソース (news|rss|search|all)"),
    date: Optional[str] = Query(None, description="日付 (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=100, description="取得件数"),
    full: bool = Query(False, description="全文取得フラグ"),
):
    """外部情報（最新）を取得."""
    try:
        info_db = request.app.state.info_db
        return get_info_data(info_db, date=date, limit=limit, full=full)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/news")
async def get_info_news(
    request: Request,
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
):
    """ニュースを取得."""
    try:
        info_db = request.app.state.info_db
        news = get_latest_news(info_db, limit)
        return {"news": news}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/reports")
async def get_info_reports(
    request: Request,
    limit: int = Query(5, ge=1, le=20, description="取得件数"),
):
    """レポートを取得."""
    try:
        info_db = request.app.state.info_db
        reports = get_reports(info_db, limit)
        return {"reports": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
