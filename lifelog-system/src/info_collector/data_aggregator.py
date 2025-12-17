"""
デイリーレポート用データ集約モジュール（実装準備用）

このファイルは実装準備用です。
実装時には実際のデータ取得ロジックを実装してください。

設計ドキュメント: docs/INTEGRATED_DAILY_REPORT_DESIGN.md
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from src.lifelog.database.db_manager import DatabaseManager
from src.browser_history.repository import BrowserHistoryRepository
from src.info_collector.repository import InfoCollectorRepository


@dataclass
class UnifiedTimelineEntry:
    """統合時系列エントリ"""
    timestamp: datetime
    source_type: str  # 'lifelog', 'event', 'browser', 'article', 'deep_research', 'report'
    category: str
    title: str
    description: str
    metadata: dict
    importance_score: Optional[float] = None


@dataclass
class DailyReportData:
    """デイリーレポート用統合データ"""
    report_date: str
    lifelog_data: List[dict]
    events: List[dict]
    browser_history: List[dict]
    article_analyses: List[dict]
    deep_research: List[dict]
    theme_reports: List[dict]
    timeline: List[dict]


class DailyReportDataAggregator:
    """
    デイリーレポート用データ集約クラス
    
    各データソースからデータを取得し、統合データとして提供する。
    """
    
    def __init__(
        self,
        lifelog_db_path: Path,
        info_db_path: Path
    ):
        """
        Args:
            lifelog_db_path: ライフログデータベースのパス（lifelog.db）
            info_db_path: 情報収集データベースのパス（ai_secretary.db）
        """
        self.lifelog_db_path = lifelog_db_path
        self.info_db_path = info_db_path
        
        # データベース接続の初期化
        self.lifelog_db = DatabaseManager(str(lifelog_db_path))
        self.info_db = InfoCollectorRepository(str(info_db_path))
        self.browser_repo = BrowserHistoryRepository(info_db_path)
        # info_db_pathを文字列として保存（ブラウザ履歴取得で使用）
        self.info_db_path_str = str(info_db_path)
    
    def aggregate_daily_data(
        self,
        date: str,
        detail_level: str = "summary"  # 'summary', 'detailed', 'full'
    ) -> DailyReportData:
        """
        指定日のデータを集約
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
            detail_level: 詳細度（'summary', 'detailed', 'full'）
        
        Returns:
            DailyReportData: 統合データ
        """
        # 1. ライフログデータ取得
        lifelog_data = self._get_lifelog_data(date)
        
        # 2. イベント情報取得
        events = self._get_events(date)
        
        # 3. ブラウザ履歴取得
        browser_history = self._get_browser_history(date)
        
        # 4. 記事分析結果取得
        article_analyses = self._get_article_analyses(date)
        
        # 5. 深掘り調査結果取得
        deep_research = self._get_deep_research(date)
        
        # 6. テーマレポート取得
        theme_reports = self._get_theme_reports(date)
        
        # 7. 時系列統合
        timeline = self._build_unified_timeline(
            lifelog_data, events, browser_history,
            article_analyses, deep_research, date
        )
        
        return DailyReportData(
            report_date=date,
            lifelog_data=lifelog_data,
            events=events,
            browser_history=browser_history,
            article_analyses=article_analyses,
            deep_research=deep_research,
            theme_reports=theme_reports,
            timeline=timeline
        )
    
    def _get_lifelog_data(self, date: str) -> List[Dict[str, Any]]:
        """
        ライフログデータ取得
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
        
        Returns:
            ライフログデータのリスト
        """
        # 日付文字列をそのまま使用（SQLiteのDATE()関数で比較）
        conn = self.lifelog_db._get_connection()
        cursor = conn.cursor()
        
        # 活動インターバルを取得（DATE()関数で日付比較）
        cursor.execute(
            """
            SELECT
                i.start_ts,
                i.end_ts,
                a.process_name,
                i.window_hash,
                i.domain,
                i.is_idle,
                i.duration_seconds
            FROM activity_intervals i
            JOIN apps a ON i.app_id = a.app_id
            WHERE DATE(i.start_ts) = ?
            ORDER BY i.start_ts
            """,
            (date,),
        )
        
        intervals = []
        for row in cursor.fetchall():
            start_ts = self._parse_datetime(row["start_ts"])
            end_ts = self._parse_datetime(row["end_ts"])
            
            # タイムゾーン情報を除去（比較エラーを防ぐため）
            if start_ts and start_ts.tzinfo:
                start_ts = start_ts.replace(tzinfo=None)
            if end_ts and end_ts.tzinfo:
                end_ts = end_ts.replace(tzinfo=None)
            
            duration = row["duration_seconds"]
            if duration is None and start_ts and end_ts:
                duration = int((end_ts - start_ts).total_seconds())
            intervals.append({
                "timestamp": start_ts.isoformat() if start_ts else None,
                "start_ts": start_ts.isoformat() if start_ts else None,
                "end_ts": end_ts.isoformat() if end_ts else None,
                "process_name": row["process_name"],
                "window_hash": row["window_hash"],
                "domain": row["domain"],
                "is_idle": bool(row["is_idle"]),
                "duration_seconds": duration,
            })
        
        return intervals
    
    def _get_events(self, date: str) -> List[Dict[str, Any]]:
        """
        イベント情報取得
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
        
        Returns:
            イベントデータのリスト
        
        注意: DatabaseManager.get_events_by_date_range() メソッドが実装される必要があります
        """
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)
        
        # イベント情報を取得（中重要度以上）
        return self.lifelog_db.get_events_by_date_range(
            start, end,
            min_severity=50  # 中重要度以上
        )
    
    def _get_browser_history(self, date: str) -> List[Dict[str, Any]]:
        """
        ブラウザ履歴取得
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
        
        Returns:
            ブラウザ履歴データのリスト
        """
        # 直接SQLクエリで指定日の履歴を取得（DATE()関数を使用）
        conn = sqlite3.connect(self.info_db_path_str)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT url, title, visit_time, visit_count, source_browser
            FROM browser_history
            WHERE DATE(visit_time) = ?
            ORDER BY visit_time DESC
            LIMIT 1000
            """,
            (date,),
        )
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "visit_time": row["visit_time"],
                "title": row["title"],
                "url": row["url"],
                "visit_count": row["visit_count"],
                "source_browser": row["source_browser"],
            })
        
        conn.close()
        return history
    
    def _get_article_analyses(self, date: str) -> List[Dict[str, Any]]:
        """
        記事分析結果取得
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
        
        Returns:
            記事分析結果のリスト
        """
        start = datetime.strptime(date, "%Y-%m-%d")
        since = start.isoformat()
        
        rows = self.info_db.fetch_recent_analysis(since)
        end = start + timedelta(days=1)
        
        # 指定日の範囲に限定
        return [
            row for row in rows
            if (ts := self._parse_datetime(row.get("analyzed_at"))) and ts < end
        ]
    
    def _get_deep_research(self, date: str) -> List[Dict[str, Any]]:
        """
        深掘り調査結果取得
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
        
        Returns:
            深掘り調査結果のリスト
        """
        start = datetime.strptime(date, "%Y-%m-%d")
        since = start.isoformat()
        
        rows = self.info_db.fetch_recent_deep_research(since)
        end = start + timedelta(days=1)
        return [
            row for row in rows
            if (ts := self._parse_datetime(row.get("researched_at") or row.get("created_at"))) and ts < end
        ]
    
    def _get_theme_reports(self, date: str) -> List[Dict[str, Any]]:
        """
        テーマレポート取得
        
        Args:
            date: 日付文字列（YYYY-MM-DD）
        
        Returns:
            テーマレポートのリスト
        """
        if hasattr(self.info_db, "fetch_reports_by_date"):
            return self.info_db.fetch_reports_by_date(date, category="theme")
        return []
    
    def _build_unified_timeline(
        self,
        lifelog_data: List[Dict],
        events: List[Dict],
        browser_history: List[Dict],
        article_analyses: List[Dict],
        deep_research: List[Dict],
        date: str
    ) -> List[dict]:
        """
        統合時系列を構築
        
        Args:
            lifelog_data: ライフログデータ
            events: イベントデータ
            browser_history: ブラウザ履歴
            article_analyses: 記事分析結果
            deep_research: 深掘り調査結果
            date: 日付文字列
        
        Returns:
            統合時系列エントリのリスト（時系列でソート済み）
        """
        timeline: list[UnifiedTimelineEntry] = []
        
        # ライフログデータを時系列エントリに変換
        for entry in lifelog_data:
            ts = self._parse_datetime(entry.get("timestamp") or entry.get("start_ts"))
            if not ts:
                continue
            timeline.append(UnifiedTimelineEntry(
                timestamp=ts,
                source_type="lifelog",
                category="activity",
                title=entry.get("process_name", "Unknown"),
                description=entry.get("window_hash", "") or "",
                metadata=entry,
                importance_score=None
            ))
        
        # イベントデータを時系列エントリに変換
        for event in events:
            ts = self._parse_datetime(event.get("event_timestamp"))
            if not ts:
                continue
            timeline.append(UnifiedTimelineEntry(
                timestamp=ts,
                source_type="event",
                category=event.get("category", "other"),
                title=f"[{event.get('event_type', 'unknown')}] {event.get('message', '')[:50]}",
                description=event.get("message", ""),
                metadata=event,
                importance_score=event.get("severity", 0) / 100.0
            ))
        
        # ブラウザ履歴を時系列エントリに変換
        for history in browser_history:
            ts = self._parse_datetime(history.get("visit_time"))
            if not ts:
                continue
            timeline.append(UnifiedTimelineEntry(
                timestamp=ts,
                source_type="browser",
                category="browsing",
                title=history.get("title", history.get("url", "")),
                description=history.get("url", ""),
                metadata=history,
                importance_score=None
            ))
        
        # 記事分析結果を時系列エントリに変換
        for article in article_analyses:
            ts = self._parse_datetime(article.get("published_at") or article.get("analyzed_at") or article.get("fetched_at"))
            if not ts:
                continue
            timeline.append(UnifiedTimelineEntry(
                timestamp=ts,
                source_type="article",
                category=article.get("category", "other"),
                title=article.get("title", ""),
                description=article.get("summary", ""),
                metadata=article,
                importance_score=article.get("importance_score", 0)
            ))
        
        # 深掘り調査結果を時系列エントリに変換
        for research in deep_research:
            ts = self._parse_datetime(research.get("researched_at") or research.get("created_at"))
            if not ts:
                continue
            timeline.append(UnifiedTimelineEntry(
                timestamp=ts,
                source_type="deep_research",
                category="research",
                title=research.get("theme", ""),
                description=research.get("synthesized_content", "")[:200] if research.get("synthesized_content") else "",
                metadata=research,
                importance_score=None
            ))
        
        # タイムスタンプでソート（降順）
        timeline.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [asdict(entry) for entry in timeline]
    
    def analyze_time_patterns(self, data: DailyReportData) -> Dict[str, Any]:
        """
        時間帯別の活動パターンを分析
        
        Args:
            data: デイリーレポートデータ
        
        Returns:
            時間帯別パターンの辞書
        """
        patterns = {
            "morning": [],      # 6:00-12:00
            "afternoon": [],    # 12:00-18:00
            "evening": [],      # 18:00-22:00
            "night": []         # 22:00-6:00
        }
        
        # 各時間帯の活動を分類
        for entry in data.timeline:
            ts = self._parse_datetime(entry.get("timestamp"))
            if not ts:
                continue
            hour = ts.hour
            if 6 <= hour < 12:
                patterns["morning"].append(entry)
            elif 12 <= hour < 18:
                patterns["afternoon"].append(entry)
            elif 18 <= hour < 22:
                patterns["evening"].append(entry)
            else:
                patterns["night"].append(entry)
        
        return patterns

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """
        ISO文字列/Datetimeを安全にdatetimeへ変換.
        タイムゾーン情報は保持するが、比較時は統一が必要.
        """
        if isinstance(value, datetime):
            return value
        if value is None:
            return None
        try:
            dt = datetime.fromisoformat(str(value))
            # タイムゾーン情報がある場合は保持、ない場合はそのまま
            return dt
        except Exception:
            return None
