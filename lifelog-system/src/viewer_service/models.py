"""Data Transfer Objects (DTOs) for viewer service.

統合ビューサービスで使用するPydanticモデル定義。
各データソース（lifelog, browser, info_collector）からの
データを統一フォーマットで扱う。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


# ============================================================
# Lifelog DTOs
# ============================================================


class AppUsage(BaseModel):
    """アプリケーション使用状況."""

    process: str
    total_seconds: int
    percentage: Optional[float] = None


class ActivityInterval(BaseModel):
    """活動インターバル."""

    timestamp: datetime
    process: str
    domain: Optional[str] = None
    duration: int
    is_idle: bool = False


class HealthMetrics(BaseModel):
    """ヘルスメトリクス."""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    delay_p95: float


class LifelogData(BaseModel):
    """ライフログデータ."""

    date: str
    total_active_seconds: int
    total_idle_seconds: int
    top_apps: List[AppUsage] = Field(default_factory=list)
    recent_intervals: List[ActivityInterval] = Field(default_factory=list)
    health_latest: Optional[HealthMetrics] = None


# ============================================================
# Browser DTOs
# ============================================================


class BrowserEntry(BaseModel):
    """ブラウザ履歴エントリ."""

    time: datetime
    title: Optional[str] = None
    url: str
    domain: Optional[str] = None


class DomainStats(BaseModel):
    """ドメイン統計."""

    domain: str
    count: int


class BrowserData(BaseModel):
    """ブラウザ履歴データ."""

    recent: List[BrowserEntry] = Field(default_factory=list)
    top_domains: List[DomainStats] = Field(default_factory=list)
    total_visits: int = 0


# ============================================================
# Info Collector DTOs
# ============================================================


class NewsItem(BaseModel):
    """ニュース項目."""

    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    summary: Optional[str] = None


class RSSItem(BaseModel):
    """RSSフィード項目."""

    title: str
    url: str
    feed_name: str
    published_at: Optional[datetime] = None
    summary: Optional[str] = None


class SearchResult(BaseModel):
    """検索結果."""

    title: str
    url: str
    snippet: Optional[str] = None
    query: str
    timestamp: datetime


class SummaryItem(BaseModel):
    """要約項目."""

    title: str
    summary: str
    created_at: datetime
    source_type: str


class ReportItem(BaseModel):
    """レポート項目."""

    title: str
    report_date: str
    content_head: str
    full_content: Optional[str] = None


class AnalysisItem(BaseModel):
    """分析項目."""

    title: str
    importance: float
    relevance: float
    keywords: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    deep_research: Optional[Dict[str, Any]] = None


class InfoData(BaseModel):
    """外部情報データ."""

    news: List[NewsItem] = Field(default_factory=list)
    rss: List[RSSItem] = Field(default_factory=list)
    search: List[SearchResult] = Field(default_factory=list)
    summary_latest: Optional[SummaryItem] = None
    report_latest: Optional[ReportItem] = None
    analysis: List[AnalysisItem] = Field(default_factory=list)


# ============================================================
# Dashboard DTO
# ============================================================


class DashboardData(BaseModel):
    """統合ダッシュボードデータ.

    全データソースを統合したレスポンスDTO。
    """

    generated_at: datetime = Field(default_factory=datetime.now)
    lifelog: LifelogData
    browser: BrowserData
    info: InfoData


# ============================================================
# Query Parameters
# ============================================================


class DashboardParams(BaseModel):
    """ダッシュボードクエリパラメータ."""

    date: Optional[str] = None
    hours: int = 6
    limit: int = 5
    full: bool = False
