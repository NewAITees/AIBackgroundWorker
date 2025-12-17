# 包括的デイリーレポート生成機能 設計ドキュメント

## 概要

現在のテーマレポートに加えて、すべての情報源を統合した包括的なデイリーレポートを生成する機能。

## 目的

- ライフログ、イベント、ブラウザ履歴、記事分析、深掘り調査、テーマレポートを統合
- 時間の粒度と意味を明確化
- 人間が把握しやすい形式で時系列表示
- イベントと活動の相関関係を分析

## 統合する情報源

### 1. ライフログデータ
- **ソース**: `lifelog-system/data/lifelog.db` の `activity_intervals` テーブル
- **データ内容**:
  - アクティブウィンドウ情報
  - 操作状況（アプリケーション使用状況）
  - 時間帯別活動パターン
  - アイドル時間
- **取得方法**: `DatabaseManager` を使用して期間指定で取得

### 2. イベント情報
- **ソース**: `lifelog-system/data/lifelog.db` の `system_events` テーブル（実装後）
- **データ内容**:
  - エラー、システムイベント、重要な操作
  - イベントタイプ、重要度、カテゴリ
- **取得方法**: `DatabaseManager.get_events_by_date_range()` を使用

### 3. ブラウザ履歴
- **ソース**: `lifelog-system/data/ai_secretary.db` の `browser_history` テーブル
- **データ内容**:
  - 訪問したサイト
  - 時間帯別アクセス
  - ドメイン別集計
- **取得方法**: `BrowserHistoryRepository` を使用

### 4. 記事分析結果
- **ソース**: `lifelog-system/data/ai_secretary.db` の `article_analysis` テーブル
- **データ内容**:
  - 重要度・関連度スコア
  - 判断理由
  - カテゴリ、キーワード
- **取得方法**: `InfoCollectorRepository.fetch_recent_analysis()` を使用

### 5. 深掘り調査結果
- **ソース**: `lifelog-system/data/ai_secretary.db` の `deep_research` テーブル
- **データ内容**:
  - 検索結果
  - 統合分析
  - テーマ別の深掘り内容
- **取得方法**: `InfoCollectorRepository.fetch_recent_deep_research()` を使用

### 6. テーマレポート
- **ソース**: `lifelog-system/data/ai_secretary.db` の `reports` テーブル
- **データ内容**:
  - 既存のテーマ別レポート
- **取得方法**: `InfoCollectorRepository.fetch_reports()` を使用

## データ統合設計

### 統合データモデル

```python
# src/info_collector/models.py に追加

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

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
    timeline: List[UnifiedTimelineEntry]
```

### データ取得モジュール

```python
# src/info_collector/data_aggregator.py（新規作成）

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from src.lifelog.database.db_manager import DatabaseManager
from src.browser_history.repository import BrowserHistoryRepository
from src.info_collector.repository import InfoCollectorRepository

class DailyReportDataAggregator:
    """デイリーレポート用データ集約クラス"""
    
    def __init__(
        self,
        lifelog_db_path: Path,
        info_db_path: Path
    ):
        self.lifelog_db = DatabaseManager(str(lifelog_db_path))
        self.info_db = InfoCollectorRepository(str(info_db_path))
        self.browser_repo = BrowserHistoryRepository(info_db_path)
    
    def aggregate_daily_data(
        self,
        date: str,
        detail_level: str = "summary"  # 'summary', 'detailed', 'full'
    ) -> DailyReportData:
        """指定日のデータを集約"""
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
        """ライフログデータ取得"""
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)
        
        # 時間帯別活動パターン
        # アプリケーション使用状況
        # アクティブウィンドウ情報
        pass
    
    def _get_events(self, date: str) -> List[Dict[str, Any]]:
        """イベント情報取得"""
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)
        
        return self.lifelog_db.get_events_by_date_range(
            start, end,
            min_severity=50  # 中重要度以上
        )
    
    def _get_browser_history(self, date: str) -> List[Dict[str, Any]]:
        """ブラウザ履歴取得"""
        # BrowserHistoryRepositoryを使用
        pass
    
    def _get_article_analyses(self, date: str) -> List[Dict[str, Any]]:
        """記事分析結果取得"""
        start = datetime.strptime(date, "%Y-%m-%d")
        since = start.isoformat()
        
        return self.info_db.fetch_recent_analysis(since)
    
    def _get_deep_research(self, date: str) -> List[Dict[str, Any]]:
        """深掘り調査結果取得"""
        start = datetime.strptime(date, "%Y-%m-%d")
        since = start.isoformat()
        
        return self.info_db.fetch_recent_deep_research(since)
    
    def _get_theme_reports(self, date: str) -> List[Dict[str, Any]]:
        """テーマレポート取得"""
        # InfoCollectorRepositoryを使用
        pass
    
    def _build_unified_timeline(
        self,
        lifelog_data: List[Dict],
        events: List[Dict],
        browser_history: List[Dict],
        article_analyses: List[Dict],
        deep_research: List[Dict],
        date: str
    ) -> List[UnifiedTimelineEntry]:
        """統合時系列を構築"""
        timeline = []
        
        # すべてのデータソースを時系列で統合
        # タイムスタンプでソート
        # 重要度順に並び替え
        
        return sorted(timeline, key=lambda x: x.timestamp)
```

## プロンプト設計

### 統合プロンプト構造

```python
# src/info_collector/prompts/integrated_report_generation.py（新規作成）

SYSTEM_PROMPT = """あなたは包括的な日次レポート生成アシスタントです。
ユーザーの1日の活動、システムイベント、ブラウザ履歴、情報収集結果を統合して、
読みやすく構造化されたMarkdownレポートを作成してください。

【レポートの目的】
- ユーザーが1日を振り返り、活動パターンや重要な出来事を把握できるようにする
- イベントと活動の相関関係を分析する
- 情報収集結果と実際の活動を関連付ける

【レポート構成】
1. 概要（1日の全体像を3-4文で要約）
2. 時系列サマリー（時間帯別の主要な活動とイベント）
3. 活動パターン分析
   - 時間帯別の活動状況
   - 主なアプリケーション使用状況
   - ブラウザアクセスパターン
4. システムイベント分析
   - 重要なエラーや警告
   - イベントと活動の相関関係
5. 情報収集結果
   - 重要記事の要約
   - 深掘り調査の主要な発見
   - テーマ別の洞察
6. 統合分析
   - 活動と情報収集の関連性
   - 時間帯別のパターン
   - 重要な出来事のまとめ
7. 参考データ一覧

【時間の粒度と意味】
- 各情報のタイムスタンプを統一フォーマット（YYYY-MM-DD HH:MM:SS）で表示
- 時間帯別の活動パターンを可視化（朝/昼/夕方/夜）
- イベントと活動の相関関係を明確に示す

【文体の原則】
- 簡潔で分かりやすい日本語
- 専門用語には簡単な説明を付ける
- 時系列は自然な流れで記述
- 見出しは階層的に使用（##, ###）
- データの出所を明記

必ずMarkdown形式で出力してください。"""

USER_PROMPT_TEMPLATE = """以下の情報から、{report_date}の包括的なデイリーレポートを作成してください。

【ライフログデータ】
{lifelog_summary}

【システムイベント】
{events_summary}

【ブラウザ履歴】
{browser_summary}

【記事分析結果】
{articles_summary}

【深掘り調査結果】
{deep_research_summary}

【テーマレポート】
{theme_reports_summary}

【統合時系列データ】
{timeline_data}

上記の構成に従ってMarkdownレポートを生成してください。"""
```

### プロンプト構築関数

```python
def build_integrated_prompt(
    report_date: str,
    data: DailyReportData,
    detail_level: str = "summary"
) -> dict[str, str]:
    """統合レポート生成プロンプトを構築"""
    
    # 詳細度に応じてデータを要約
    if detail_level == "summary":
        lifelog_summary = _summarize_lifelog(data.lifelog_data)
        events_summary = _summarize_events(data.events, top_n=10)
        browser_summary = _summarize_browser(data.browser_history, top_n=20)
        articles_summary = _summarize_articles(data.article_analyses, top_n=5)
        deep_research_summary = _summarize_deep_research(data.deep_research, top_n=3)
        timeline_data = _summarize_timeline(data.timeline, top_n=30)
    elif detail_level == "detailed":
        # より詳細な情報を含める
        pass
    else:  # full
        # すべての情報を含める
        pass
    
    return {
        "system": SYSTEM_PROMPT,
        "user": USER_PROMPT_TEMPLATE.format(
            report_date=report_date,
            lifelog_summary=lifelog_summary,
            events_summary=events_summary,
            browser_summary=browser_summary,
            articles_summary=articles_summary,
            deep_research_summary=deep_research_summary,
            theme_reports_summary=_format_theme_reports(data.theme_reports),
            timeline_data=timeline_data
        )
    }
```

## レポート生成モジュール拡張

### generate_daily_report.py の拡張

```python
# src/info_collector/jobs/generate_integrated_report.py（新規作成、または既存を拡張）

from pathlib import Path
from datetime import datetime

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.data_aggregator import DailyReportDataAggregator
from src.info_collector.prompts import integrated_report_generation

def generate_integrated_daily_report(
    lifelog_db_path: Path,
    info_db_path: Path,
    output_dir: Path,
    date: str = None,
    detail_level: str = "summary"  # 'summary', 'detailed', 'full'
) -> Path | None:
    """包括的なデイリーレポートを生成"""
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # データ集約
    aggregator = DailyReportDataAggregator(lifelog_db_path, info_db_path)
    data = aggregator.aggregate_daily_data(date, detail_level)
    
    # プロンプト構築
    prompts = integrated_report_generation.build_integrated_prompt(
        date, data, detail_level
    )
    
    # LLMでレポート生成
    ollama = OllamaClient()
    content = ollama.generate(
        prompt=prompts["user"],
        system=prompts["system"],
        options={"temperature": 0.5}
    )
    
    # 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"integrated_report_{date}.md"
    report_path.write_text(content, encoding="utf-8")
    
    # DBにも保存（オプション）
    # repo.save_report(...)
    
    return report_path
```

## 時間の粒度と意味の明確化

### 時間帯別パターン分析

```python
def analyze_time_patterns(data: DailyReportData) -> dict:
    """時間帯別の活動パターンを分析"""
    patterns = {
        "morning": [],      # 6:00-12:00
        "afternoon": [],    # 12:00-18:00
        "evening": [],      # 18:00-22:00
        "night": []         # 22:00-6:00
    }
    
    # 各時間帯の活動を分類
    # イベントと活動の相関関係を分析
    
    return patterns
```

### タイムスタンプ統一フォーマット

すべてのタイムスタンプを `YYYY-MM-DD HH:MM:SS` 形式で統一表示。

## 人間が把握しやすい形式

### 1. 時系列での統合表示
- すべてのイベントを時系列で並べる
- 時間帯ごとにセクションを分ける
- 関連するイベントをグループ化

### 2. カテゴリ別の整理
- 活動、イベント、情報収集をカテゴリ別に整理
- 重要度順に並び替え

### 3. 重要度順の並び替え
- イベントの重要度スコアで並び替え
- 記事の重要度スコアで並び替え

### 4. 視覚的な区切りと見出し構造
- 明確な見出し階層（##, ###）
- セクション間の視覚的な区切り
- リストや表を適切に使用

## 実装ステップ

1. **データ集約モジュール実装**
   - `DailyReportDataAggregator` クラスの実装
   - 各データソースからの取得ロジック

2. **統合プロンプト設計**
   - `integrated_report_generation.py` の作成
   - プロンプトテンプレートの実装

3. **レポート生成モジュール拡張**
   - `generate_integrated_report.py` の作成
   - 既存の `generate_daily_report.py` との統合検討

4. **時間パターン分析機能**
   - 時間帯別パターン分析の実装
   - 相関関係分析の実装

5. **CLI/スクリプト統合**
   - 既存の `generate_report.sh` を拡張
   - 新しい統合レポート生成スクリプトの作成

## 関連ファイル

- `lifelog-system/src/info_collector/data_aggregator.py` - データ集約（新規）
- `lifelog-system/src/info_collector/prompts/integrated_report_generation.py` - プロンプト（新規）
- `lifelog-system/src/info_collector/jobs/generate_integrated_report.py` - レポート生成（新規）
- `scripts/info_collector/generate_integrated_report.sh` - スクリプト（新規）
- `lifelog-system/src/info_collector/models.py` - データモデル拡張
