"""Browser history database query functions.

ai_secretary.db (browser_history テーブル) からデータを読み取り、DTOに変換する。
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from ..models import BrowserData, BrowserEntry, DomainStats


def _connect_browser_db(db_path: Path) -> sqlite3.Connection:
    """ブラウザ履歴DBに接続（読み取り専用）."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _extract_domain(url: str) -> Optional[str]:
    """URLからドメインを抽出."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None


def get_browser_data(db_path: Path, date: Optional[str] = None, limit: int = 20) -> BrowserData:
    """ブラウザ履歴データを取得.

    Args:
        db_path: ai_secretary.dbのパス
        date: 日付文字列 (YYYY-MM-DD)、Noneの場合は全期間
        limit: 取得件数

    Returns:
        BrowserData: ブラウザ履歴データ
    """
    if not db_path.exists():
        # DBが存在しない場合は空データを返す
        return BrowserData(recent=[], top_domains=[], total_visits=0)

    conn = _connect_browser_db(db_path)
    cursor = conn.cursor()

    # 日付フィルタ
    if date:
        start_dt = datetime.strptime(date, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=1)
        date_filter = (
            f"WHERE visit_time >= '{start_dt.isoformat()}' "
            f"AND visit_time < '{end_dt.isoformat()}'"
        )
    else:
        date_filter = ""

    # 直近の履歴
    cursor.execute(
        f"""
        SELECT visit_time, title, url
        FROM browser_history
        {date_filter}
        ORDER BY visit_time DESC
        LIMIT ?
        """,
        (limit,),
    )

    recent = []
    for row in cursor.fetchall():
        domain = _extract_domain(row["url"])
        recent.append(
            BrowserEntry(
                time=datetime.fromisoformat(row["visit_time"]),
                title=row["title"],
                url=row["url"],
                domain=domain,
            )
        )

    # ドメイン別集計
    cursor.execute(
        f"""
        SELECT url, COUNT(*) as count
        FROM browser_history
        {date_filter}
        GROUP BY url
        ORDER BY count DESC
        LIMIT 10
        """
    )

    domain_counts: dict[str, int] = {}
    for row in cursor.fetchall():
        domain = _extract_domain(row["url"])
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + row["count"]

    top_domains = [
        DomainStats(domain=domain, count=count)
        for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # 総訪問数
    cursor.execute(f"SELECT COUNT(*) as total FROM browser_history {date_filter}")
    total_visits = cursor.fetchone()["total"]

    conn.close()

    return BrowserData(recent=recent, top_domains=top_domains, total_visits=total_visits)


def search_browser_history(db_path: Path, query: str, limit: int = 50) -> List[BrowserEntry]:
    """ブラウザ履歴を検索.

    Args:
        db_path: ai_secretary.dbのパス
        query: 検索クエリ
        limit: 取得件数

    Returns:
        List[BrowserEntry]: 検索結果
    """
    if not db_path.exists():
        return []

    conn = _connect_browser_db(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT visit_time, title, url
        FROM browser_history
        WHERE title LIKE ? OR url LIKE ?
        ORDER BY visit_time DESC
        LIMIT ?
        """,
        (f"%{query}%", f"%{query}%", limit),
    )

    results = []
    for row in cursor.fetchall():
        domain = _extract_domain(row["url"])
        results.append(
            BrowserEntry(
                time=datetime.fromisoformat(row["visit_time"]),
                title=row["title"],
                url=row["url"],
                domain=domain,
            )
        )

    conn.close()
    return results
