"""Info collector database query functions.

ai_secretary.db (collected_info, info_summaries, article_analysis等) からデータを読み取り、DTOに変換する。
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import (
    InfoData,
    NewsItem,
    RSSItem,
    SearchResult,
    SummaryItem,
    ReportItem,
    AnalysisItem,
)


def _connect_info_db(db_path: Path) -> sqlite3.Connection:
    """info_collector DBに接続（読み取り専用）."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def get_info_data(
    db_path: Path,
    date: Optional[str] = None,
    limit: int = 10,
    full: bool = False,
) -> InfoData:
    """外部情報データを取得.

    Args:
        db_path: ai_secretary.dbのパス
        date: 日付文字列 (YYYY-MM-DD)、Noneの場合は全期間
        limit: 各カテゴリの取得件数
        full: 全文取得フラグ

    Returns:
        InfoData: 外部情報データ
    """
    if not db_path.exists():
        return InfoData()

    conn = _connect_info_db(db_path)
    cursor = conn.cursor()

    # 日付フィルタ
    if date:
        date_filter = f"AND DATE(fetched_at) = '{date}'"
    else:
        date_filter = ""

    # ニュース
    cursor.execute(
        f"""
        SELECT title, url, source_name, published_at, snippet, content
        FROM collected_info
        WHERE source_type = 'news' {date_filter}
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    news = []
    for row in cursor.fetchall():
        summary = row["content"] if full else (row["snippet"] or "")[:200]
        news.append(
            NewsItem(
                title=row["title"],
                url=row["url"],
                source=row["source_name"] or "Unknown",
                published_at=(
                    datetime.fromisoformat(row["published_at"])
                    if row["published_at"]
                    else None
                ),
                summary=summary,
            )
        )

    # RSS
    cursor.execute(
        f"""
        SELECT title, url, source_name, published_at, snippet, content
        FROM collected_info
        WHERE source_type = 'rss' {date_filter}
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    rss = []
    for row in cursor.fetchall():
        summary = row["content"] if full else (row["snippet"] or "")[:200]
        rss.append(
            RSSItem(
                title=row["title"],
                url=row["url"],
                feed_name=row["source_name"] or "Unknown",
                published_at=(
                    datetime.fromisoformat(row["published_at"])
                    if row["published_at"]
                    else None
                ),
                summary=summary,
            )
        )

    # 検索結果
    cursor.execute(
        f"""
        SELECT title, url, snippet, metadata_json, fetched_at
        FROM collected_info
        WHERE source_type = 'search' {date_filter}
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    search = []
    for row in cursor.fetchall():
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        query = metadata.get("query", "")
        search.append(
            SearchResult(
                title=row["title"],
                url=row["url"],
                snippet=row["snippet"],
                query=query,
                timestamp=datetime.fromisoformat(row["fetched_at"]),
            )
        )

    # 最新の要約
    cursor.execute(
        """
        SELECT summary_type, title, summary_text, created_at
        FROM info_summaries
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    summary_row = cursor.fetchone()
    summary_latest = None
    if summary_row:
        summary_latest = SummaryItem(
            title=summary_row["title"],
            summary=summary_row["summary_text"],
            created_at=datetime.fromisoformat(summary_row["created_at"]),
            source_type=summary_row["summary_type"],
        )

    # 最新のレポート
    cursor.execute(
        """
        SELECT title, summary_text, created_at
        FROM info_summaries
        WHERE summary_type = 'daily_report'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    report_row = cursor.fetchone()
    report_latest = None
    if report_row:
        content = report_row["summary_text"]
        content_head = content[:500] if not full else content
        report_latest = ReportItem(
            title=report_row["title"],
            report_date=datetime.fromisoformat(
                report_row["created_at"]
            ).strftime("%Y-%m-%d"),
            content_head=content_head,
            full_content=content if full else None,
        )

    # 分析結果
    cursor.execute(
        f"""
        SELECT
            ci.title,
            aa.importance_score,
            aa.relevance_score,
            aa.keywords,
            aa.summary,
            aa.deep_research_json
        FROM article_analysis aa
        JOIN collected_info ci ON aa.article_id = ci.id
        {date_filter.replace('fetched_at', 'ci.fetched_at')}
        ORDER BY aa.importance_score DESC, aa.relevance_score DESC
        LIMIT ?
        """,
        (limit,),
    )

    analysis = []
    for row in cursor.fetchall():
        keywords_list = json.loads(row["keywords"]) if row["keywords"] else []
        deep_research = (
            json.loads(row["deep_research_json"])
            if row["deep_research_json"]
            else None
        )

        analysis.append(
            AnalysisItem(
                title=row["title"],
                importance=row["importance_score"] or 0.0,
                relevance=row["relevance_score"] or 0.0,
                keywords=keywords_list,
                summary=row["summary"],
                deep_research=deep_research,
            )
        )

    conn.close()

    return InfoData(
        news=news,
        rss=rss,
        search=search,
        summary_latest=summary_latest,
        report_latest=report_latest,
        analysis=analysis,
    )


def get_latest_news(db_path: Path, limit: int = 20) -> List[NewsItem]:
    """最新ニュースを取得.

    Args:
        db_path: ai_secretary.dbのパス
        limit: 取得件数

    Returns:
        List[NewsItem]: ニュースリスト
    """
    if not db_path.exists():
        return []

    conn = _connect_info_db(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT title, url, source_name, published_at, snippet
        FROM collected_info
        WHERE source_type = 'news'
        ORDER BY published_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    news = []
    for row in cursor.fetchall():
        news.append(
            NewsItem(
                title=row["title"],
                url=row["url"],
                source=row["source_name"] or "Unknown",
                published_at=(
                    datetime.fromisoformat(row["published_at"])
                    if row["published_at"]
                    else None
                ),
                summary=row["snippet"],
            )
        )

    conn.close()
    return news


def get_reports(db_path: Path, limit: int = 5) -> List[ReportItem]:
    """レポートを取得.

    Args:
        db_path: ai_secretary.dbのパス
        limit: 取得件数

    Returns:
        List[ReportItem]: レポートリスト
    """
    if not db_path.exists():
        return []

    conn = _connect_info_db(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT title, summary_text, created_at
        FROM info_summaries
        WHERE summary_type = 'daily_report'
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    reports = []
    for row in cursor.fetchall():
        reports.append(
            ReportItem(
                title=row["title"],
                report_date=datetime.fromisoformat(
                    row["created_at"]
                ).strftime("%Y-%m-%d"),
                content_head=row["summary_text"][:500],
                full_content=None,
            )
        )

    conn.close()
    return reports
