#!/usr/bin/env python3
"""
CLI Viewer for lifelog-system.

Usage:
    python src/cli_viewer.py summary [--date DATE]
    python src/cli_viewer.py hourly [--date DATE]
    python src/cli_viewer.py timeline [--hours HOURS]
    python src/cli_viewer.py health [--hours HOURS]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.lifelog.database.db_manager import DatabaseManager
from src.browser_history.repository import BrowserHistoryRepository
from src.viewer_service.queries import (
    info_queries,
    dashboard_queries,
)
from src.viewer_service.models import DashboardParams


def format_duration(seconds: int) -> str:
    """秒を時間:分:秒に変換."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def show_daily_summary(db: DatabaseManager, date: str = None) -> None:
    """日別サマリーを表示."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            process_name,
            total_seconds,
            active_seconds,
            interval_count
        FROM daily_app_usage
        WHERE date = ?
        ORDER BY total_seconds DESC
        LIMIT 20
    """,
        (date,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo data found for {date}")
        return

    print(f"\n=== Daily Summary for {date} ===\n")
    print(f"{'Process':<30} {'Total Time':<12} {'Active Time':<12} {'Count':<8}")
    print("-" * 70)

    total_seconds = 0
    total_active = 0

    for row in rows:
        process = row[0][:28]
        total = row[1]
        active = row[2]
        count = row[3]

        total_seconds += total
        total_active += active

        print(
            f"{process:<30} {format_duration(total):<12} {format_duration(active):<12} {count:<8}"
        )

    print("-" * 70)
    print(f"{'TOTAL':<30} {format_duration(total_seconds):<12} {format_duration(total_active):<12}")


def show_hourly_activity(db: DatabaseManager, date: str = None) -> None:
    """時間帯別の活動状況を表示."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            strftime('%H', hour) as hour,
            active_seconds,
            idle_seconds
        FROM hourly_activity
        WHERE date(hour) = ?
        ORDER BY hour
    """,
        (date,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo data found for {date}")
        return

    print(f"\n=== Hourly Activity for {date} ===\n")
    print(f"{'Hour':<8} {'Active':<12} {'Idle':<12} {'Total':<12}")
    print("-" * 50)

    for row in rows:
        hour = row[0]
        active = int(row[1])
        idle = int(row[2])
        total = active + idle

        print(
            f"{hour}:00   {format_duration(active):<12} {format_duration(idle):<12} {format_duration(total):<12}"
        )


def show_timeline(db: DatabaseManager, hours: int = 2) -> None:
    """最近のタイムラインを表示."""
    start_time = datetime.now() - timedelta(hours=hours)

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            i.start_ts,
            i.end_ts,
            a.process_name,
            i.domain,
            i.is_idle,
            i.duration_seconds
        FROM activity_intervals i
        JOIN apps a ON i.app_id = a.app_id
        WHERE i.start_ts >= ?
        ORDER BY i.start_ts DESC
        LIMIT 50
    """,
        (start_time,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo data found in the last {hours} hours")
        return

    print(f"\n=== Activity Timeline (Last {hours} hours) ===\n")
    print(f"{'Time':<20} {'Duration':<12} {'Process':<25} {'Status':<10}")
    print("-" * 75)

    for row in rows:
        start_ts = row[0]
        process = row[2][:23]
        domain = row[3]
        is_idle = row[4]
        duration = row[5]

        status = "IDLE" if is_idle else "ACTIVE"
        if domain:
            process += f" ({domain})"

        print(f"{start_ts:<20} {format_duration(duration):<12} {process:<25} {status:<10}")


def show_health_metrics(db: DatabaseManager, hours: int = 24) -> None:
    """ヘルスメトリクスを表示."""
    start_time = datetime.now() - timedelta(hours=hours)

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            ts,
            cpu_percent,
            mem_mb,
            queue_depth,
            collection_delay_p95,
            dropped_events,
            db_write_time_p95
        FROM health_snapshots
        WHERE ts >= ?
        ORDER BY ts DESC
        LIMIT 20
    """,
        (start_time,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo health data found in the last {hours} hours")
        return

    print(f"\n=== Health Metrics (Last {hours} hours) ===\n")
    print(f"{'Time':<20} {'CPU%':<8} {'Mem(MB)':<10} {'Queue':<8} {'Delay(s)':<10} {'Drops':<8}")
    print("-" * 75)

    for row in rows:
        ts = row[0]
        cpu = row[1]
        mem = row[2]
        queue = row[3]
        delay = row[4]
        drops = row[5]

        print(f"{ts:<20} {cpu:<8.1f} {mem:<10.1f} {queue:<8} {delay:<10.2f} {drops:<8}")

    # 最新のメトリクス
    if rows:
        latest = rows[0]
        print("\n=== Latest Status ===")
        print(f"CPU Usage: {latest[1]:.1f}%")
        print(f"Memory: {latest[2]:.1f} MB")
        print(f"Collection Delay P95: {latest[4]:.2f}s")
        print(f"Dropped Events: {latest[5]}")


def show_browser_history(limit: int = 20, date: str = None) -> None:
    """ブラウザ履歴を表示."""
    repo = BrowserHistoryRepository()

    if date:
        entries = repo.list_history(start_date=date, end_date=date, limit=limit)
        print(f"\n=== Browser History for {date} ===\n")
    else:
        entries = repo.list_history(limit=limit)
        print(f"\n=== Recent Browser History (Last {limit} entries) ===\n")

    if not entries:
        print("No browser history found")
        return

    print(f"{'Time':<20} {'Title':<50} {'URL':<60}")
    print("-" * 130)

    for entry in entries:
        time_str = entry.visit_time.strftime("%Y-%m-%d %H:%M:%S")
        title = (entry.title or "(No title)")[:48]
        url = entry.url[:58]

        print(f"{time_str:<20} {title:<50} {url:<60}")

    print(f"\nTotal: {len(entries)} entries")


def show_browser_stats(date: str = None) -> None:
    """ブラウザ統計を表示."""
    repo = BrowserHistoryRepository()

    conn = repo._connect()
    cursor = conn.cursor()

    # 日付フィルタ
    date_filter = ""
    params = []
    if date:
        date_filter = "WHERE date(visit_time) = ?"
        params.append(date)
        print(f"\n=== Browser Statistics for {date} ===\n")
    else:
        print("\n=== Browser Statistics (All Time) ===\n")

    # 総件数
    cursor.execute(f"SELECT COUNT(*) FROM browser_history {date_filter}", params)
    total = cursor.fetchone()[0]

    # ドメイン別集計
    query = f"""
        SELECT
            CASE
                WHEN url LIKE 'https://%' THEN substr(url, 9, instr(substr(url, 9), '/') - 1)
                WHEN url LIKE 'http://%' THEN substr(url, 8, instr(substr(url, 8), '/') - 1)
                ELSE 'other'
            END as domain,
            COUNT(*) as count
        FROM browser_history
        {date_filter}
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 20
    """
    cursor.execute(query, params)
    domains = cursor.fetchall()

    print(f"Total Visits: {total}")
    print(f"\n{'Domain':<40} {'Visits':<10}")
    print("-" * 50)

    for domain, count in domains:
        # ドメインがNoneまたは空の場合の処理
        domain_clean = domain if domain and domain.strip() else "(unknown)"
        print(f"{domain_clean:<40} {count:<10}")

    # 時間帯別集計
    if date:
        query = """
            SELECT
                strftime('%H', visit_time) as hour,
                COUNT(*) as count
            FROM browser_history
            WHERE date(visit_time) = ?
            GROUP BY hour
            ORDER BY hour
        """
        cursor.execute(query, [date])
        hourly = cursor.fetchall()

        if hourly:
            print(f"\n{'Hour':<8} {'Visits':<10}")
            print("-" * 20)
            for hour, count in hourly:
                print(f"{hour}:00   {count:<10}")

    conn.close()


def show_news(limit: int = 10, date: str = None) -> None:
    """最新ニュースを表示."""
    root = Path(__file__).resolve().parents[2]
    info_db_path = root / "data" / "ai_secretary.db"

    if not info_db_path.exists():
        print("Error: ai_secretary.db not found")
        return

    news = info_queries.get_latest_news(info_db_path, limit=limit)

    if not news:
        print("\nNo news found")
        return

    print(f"\n=== Latest News (Last {limit} items) ===\n")
    print(f"{'Time':<20} {'Source':<20} {'Title':<60}")
    print("-" * 100)

    for item in news:
        time_str = item.published_at.strftime("%Y-%m-%d %H:%M:%S") if item.published_at else "N/A"
        title = item.title[:58] if len(item.title) > 58 else item.title
        source = item.source[:18] if len(item.source) > 18 else item.source
        print(f"{time_str:<20} {source:<20} {title:<60}")


def show_reports(limit: int = 5) -> None:
    """生成されたレポートを表示."""
    root = Path(__file__).resolve().parents[2]
    info_db_path = root / "data" / "ai_secretary.db"

    if not info_db_path.exists():
        print("Error: ai_secretary.db not found")
        return

    # reportsテーブルから直接取得
    import sqlite3

    conn = sqlite3.connect(f"file:{info_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT title, report_date, content, category, created_at
        FROM reports
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\nNo reports found")
        return

    print(f"\n=== Latest Reports (Last {limit} items) ===\n")
    for row in rows:
        print(f"Date: {row['report_date']}")
        print(f"Title: {row['title']}")
        if row["category"]:
            print(f"Category: {row['category']}")
        content_preview = (
            row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"]
        )
        print(f"Preview: {content_preview}")
        print("-" * 80)


def show_dashboard(date: str = None, limit: int = 5) -> None:
    """統合ダッシュボードを表示."""
    root = Path(__file__).resolve().parents[2]
    lifelog_db_path = root / "data" / "lifelog.db"
    info_db_path = root / "data" / "ai_secretary.db"

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    if not lifelog_db_path.exists():
        print("Error: lifelog.db not found")
        return

    try:
        params = DashboardParams(date=date, limit=limit, hours=6, full=False)
        dashboard_data = dashboard_queries.get_dashboard_data(lifelog_db_path, info_db_path, params)
    except Exception as e:
        print(f"Error loading dashboard data: {e}")
        return

    print(f"\n=== Dashboard for {date} ===\n")

    # Lifelog
    if dashboard_data.lifelog and dashboard_data.lifelog.total_active_seconds is not None:
        print("📊 Lifelog:")
        print(f"  Total Active: {format_duration(dashboard_data.lifelog.total_active_seconds)}")
        if dashboard_data.lifelog.total_idle_seconds is not None:
            print(f"  Total Idle: {format_duration(dashboard_data.lifelog.total_idle_seconds)}")
        if dashboard_data.lifelog.top_apps:
            print("  Top Apps:")
            for app in dashboard_data.lifelog.top_apps[:5]:
                print(f"    - {app.process}: {format_duration(app.total_seconds)}")
        print()

    # Browser
    if dashboard_data.browser:
        if dashboard_data.browser.recent:
            print("🌐 Browser:")
            print(f"  Total Visits: {dashboard_data.browser.total_visits}")
            print("  Recent:")
            for entry in dashboard_data.browser.recent[:5]:
                time_str = entry.time.strftime("%H:%M:%S")
                title = entry.title[:50] if entry.title else "(No title)"
                print(f"    [{time_str}] {title}")
            print()

    # Info Collector
    if dashboard_data.info:
        if dashboard_data.info.news:
            print(f"📰 News: {len(dashboard_data.info.news)} items")
            for item in dashboard_data.info.news[:3]:
                print(f"  - {item.title[:60]}")
        if dashboard_data.info.report_latest:
            print(f"\n📄 Latest Report: {dashboard_data.info.report_latest.title}")
        print()


def show_view(date: str = None) -> None:
    """今日のサマリーを表示（デフォルトコマンド）."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    root = Path(__file__).resolve().parents[2]
    db_path = str(root / "data" / "lifelog.db")

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return

    db = DatabaseManager(db_path)

    # 簡易サマリー表示
    print(f"\n=== Today's Summary ({date}) ===\n")
    show_daily_summary(db, date)
    print()
    show_dashboard(date, limit=3)


def show_recent(hours: int = 6) -> None:
    """直近N時間の活動を表示."""
    root = Path(__file__).resolve().parents[2]
    db_path = str(root / "data" / "lifelog.db")

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        return

    db = DatabaseManager(db_path)

    print(f"\n=== Recent Activity (Last {hours} hours) ===\n")
    show_timeline(db, hours)

    # 最新ニュースも表示
    info_db_path = root / "data" / "ai_secretary.db"
    if info_db_path.exists():
        print()
        show_news(limit=5)


def main() -> None:
    """メインエントリーポイント."""
    parser = argparse.ArgumentParser(description="Lifelog CLI Viewer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # summary コマンド
    summary_parser = subparsers.add_parser("summary", help="Show daily summary")
    summary_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD, default: today)")

    # hourly コマンド
    hourly_parser = subparsers.add_parser("hourly", help="Show hourly activity")
    hourly_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD, default: today)")

    # timeline コマンド
    timeline_parser = subparsers.add_parser("timeline", help="Show recent timeline")
    timeline_parser.add_argument(
        "--hours", type=int, default=2, help="Hours to look back (default: 2)"
    )

    # health コマンド
    health_parser = subparsers.add_parser("health", help="Show health metrics")
    health_parser.add_argument(
        "--hours", type=int, default=24, help="Hours to look back (default: 24)"
    )

    # browser コマンド
    browser_parser = subparsers.add_parser("browser", help="Show browser history")
    browser_parser.add_argument(
        "--limit", type=int, default=20, help="Number of entries to show (default: 20)"
    )
    browser_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD, default: all)")

    # browser-stats コマンド
    browser_stats_parser = subparsers.add_parser("browser-stats", help="Show browser statistics")
    browser_stats_parser.add_argument(
        "--date", type=str, help="Date (YYYY-MM-DD, default: all time)"
    )

    # view コマンド（デフォルト）
    view_parser = subparsers.add_parser("view", help="Show today's summary (default)")
    view_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD, default: today)")

    # recent コマンド
    recent_parser = subparsers.add_parser("recent", help="Show recent activity")
    recent_parser.add_argument(
        "--hours", type=int, default=6, help="Hours to look back (default: 6)"
    )

    # news コマンド
    news_parser = subparsers.add_parser("news", help="Show latest news")
    news_parser.add_argument(
        "--limit", type=int, default=10, help="Number of items to show (default: 10)"
    )
    news_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD, default: all)")

    # reports コマンド
    reports_parser = subparsers.add_parser("reports", help="Show latest reports")
    reports_parser.add_argument(
        "--limit", type=int, default=5, help="Number of reports to show (default: 5)"
    )

    # dashboard コマンド
    dashboard_parser = subparsers.add_parser("dashboard", help="Show integrated dashboard")
    dashboard_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD, default: today)")
    dashboard_parser.add_argument(
        "--limit", type=int, default=5, help="Number of items per category (default: 5)"
    )

    args = parser.parse_args()

    # データベース接続
    root = Path(__file__).resolve().parents[2]
    db_path = str(root / "data" / "lifelog.db")
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Please run the collector first to generate data.")
        sys.exit(1)

    db = DatabaseManager(db_path)

    # コマンド実行
    if args.command == "summary":
        show_daily_summary(db, args.date)
    elif args.command == "hourly":
        show_hourly_activity(db, args.date)
    elif args.command == "timeline":
        show_timeline(db, args.hours)
    elif args.command == "health":
        show_health_metrics(db, args.hours)
    elif args.command == "browser":
        show_browser_history(args.limit, args.date)
    elif args.command == "browser-stats":
        show_browser_stats(args.date)
    elif args.command == "view":
        show_view(args.date)
    elif args.command == "recent":
        show_recent(args.hours)
    elif args.command == "news":
        show_news(args.limit, args.date)
    elif args.command == "reports":
        show_reports(args.limit)
    elif args.command == "dashboard":
        show_dashboard(args.date, args.limit)


if __name__ == "__main__":
    main()
