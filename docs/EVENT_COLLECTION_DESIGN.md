# イベント情報収集・格納機能（EVENTVIEW対応）設計ドキュメント

## 概要

Windowsイベントログやシステムイベント（エラー、警告、重要な操作など）を収集し、既存の`activity_intervals`テーブルと統合して時系列表示を可能にする機能。

## 目的

- PCで何が起きているかを把握できる情報を収集
- エラー、システムイベント、アプリケーションイベントを記録
- ライフログデータとイベント情報を統合した時系列分析を可能にする

## データベーススキーマ拡張

### system_events テーブル

```sql
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp DATETIME NOT NULL,
    event_type TEXT NOT NULL,  -- 'error', 'warning', 'info', 'critical', 'system', 'application'
    severity INTEGER NOT NULL,  -- 0-100 (重要度スコア)
    source TEXT NOT NULL,       -- 'windows_eventlog', 'linux_syslog', 'application', 'system'
    category TEXT,              -- 'security', 'system', 'application', 'network', etc.
    event_id INTEGER,           -- Windows EventLog ID や syslog facility/priority
    message TEXT,               -- イベントメッセージ（プライバシー考慮でハッシュ化可能）
    message_hash TEXT,          -- メッセージのSHA256ハッシュ（プライバシー保護用）
    raw_data_json TEXT,         -- 元のイベントデータ（JSON形式）
    process_name TEXT,          -- 関連プロセス名（あれば）
    user_name TEXT,             -- ユーザー名（プライバシー考慮でハッシュ化可能）
    machine_name TEXT,          -- マシン名
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_severity ON system_events(severity DESC);
CREATE INDEX IF NOT EXISTS idx_events_source ON system_events(source);
CREATE INDEX IF NOT EXISTS idx_events_category ON system_events(category);
CREATE INDEX IF NOT EXISTS idx_events_date ON system_events(date(event_timestamp));
```

### イベント分類・重要度判定

#### イベントタイプ（event_type）

- `error`: エラーイベント
- `warning`: 警告イベント
- `info`: 情報イベント
- `critical`: 重大なイベント
- `system`: システムイベント
- `application`: アプリケーションイベント

#### 重要度スコア（severity: 0-100）

- **90-100**: 重大（Critical）- システムクラッシュ、セキュリティ侵害など
- **70-89**: 高（High）- 重要なエラー、セキュリティ警告など
- **50-69**: 中（Medium）- 一般的なエラー、警告など
- **30-49**: 低（Low）- 情報メッセージ、軽微な警告など
- **0-29**: 最小（Minimal）- デバッグ情報、通常の操作ログなど

#### カテゴリ（category）

- `security`: セキュリティ関連
- `system`: システム関連
- `application`: アプリケーション関連
- `network`: ネットワーク関連
- `storage`: ストレージ関連
- `performance`: パフォーマンス関連
- `other`: その他

## イベント収集コレクター設計

### インターフェース設計

```python
# src/lifelog/collectors/event_collector.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class SystemEvent:
    """システムイベントデータモデル"""
    event_timestamp: datetime
    event_type: str
    severity: int
    source: str
    category: str
    event_id: Optional[int]
    message: str
    message_hash: str
    raw_data_json: str
    process_name: Optional[str]
    user_name: Optional[str]
    machine_name: str

class EventCollector(ABC):
    """イベント収集コレクターの基底クラス"""
    
    @abstractmethod
    def collect_events(
        self, 
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[SystemEvent]:
        """イベントを収集する"""
        pass
    
    @abstractmethod
    def classify_event(self, raw_event: dict) -> tuple[str, int, str]:
        """イベントを分類・重要度判定する
        Returns: (event_type, severity, category)
        """
        pass

class WindowsEventLogCollector(EventCollector):
    """Windows EventLog APIを使用したイベント収集"""
    
    def __init__(self, log_names: List[str] = None):
        """
        Args:
            log_names: 収集するログ名のリスト
                      ['Application', 'System', 'Security'] など
        """
        pass
    
    def collect_events(self, since: Optional[datetime] = None, 
                      event_types: Optional[List[str]] = None) -> List[SystemEvent]:
        """Windows EventLogからイベントを収集"""
        pass

class LinuxSyslogCollector(EventCollector):
    """Linux syslog/journaldを使用したイベント収集"""
    
    def __init__(self, facility_filter: List[str] = None):
        """
        Args:
            facility_filter: 収集するfacilityのリスト
                            ['kern', 'user', 'daemon', 'auth'] など
        """
        pass
    
    def collect_events(self, since: Optional[datetime] = None,
                      event_types: Optional[List[str]] = None) -> List[SystemEvent]:
        """Linux syslog/journaldからイベントを収集"""
        pass
```

### 実装方針

1. **Windows環境**
   - `win32evtlog` または `pywin32` を使用してEventLog APIにアクセス
   - 主要ログ: Application, System, Security
   - イベントIDベースで分類・重要度判定

2. **Linux環境**
   - `systemd-journal` または `syslog` を使用
   - journalctlコマンド経由でアクセス
   - facility/priorityベースで分類・重要度判定

3. **プライバシー保護**
   - メッセージ内容はデフォルトでハッシュ化
   - 設定でハッシュ化を無効化可能
   - ユーザー名も同様にハッシュ化可能

## データベースマネージャー拡張

### DatabaseManager への追加メソッド

```python
# src/lifelog/database/db_manager.py に追加

def bulk_insert_events(self, events: list[dict[str, Any]]) -> None:
    """イベントデータのバルク挿入"""
    pass

def get_events_by_date_range(
    self, 
    start: datetime, 
    end: datetime,
    event_types: Optional[List[str]] = None,
    min_severity: Optional[int] = None
) -> List[dict]:
    """指定期間のイベントを取得"""
    pass

def get_events_with_activity(
    self,
    start: datetime,
    end: datetime
) -> List[dict]:
    """activity_intervalsと統合したイベントデータを取得"""
    pass
```

## 時系列統合表示

### 統合ビューの設計

```sql
-- activity_intervalsとsystem_eventsを統合したビュー
-- 注意: SQLiteではビュー内のORDER BYは保証されないため、
-- 使用時には必ず ORDER BY timestamp DESC を指定すること
-- また、windowsテーブルは存在しないため、window_hashのみを使用
CREATE VIEW IF NOT EXISTS unified_timeline AS
SELECT 
    'activity' as event_source,
    start_ts as timestamp,
    NULL as event_type,
    NULL as severity,
    a.process_name,
    i.window_hash,
    NULL as message,
    NULL as category
FROM activity_intervals i
JOIN apps a ON i.app_id = a.app_id

UNION ALL

SELECT 
    'system_event' as event_source,
    event_timestamp as timestamp,
    event_type,
    severity,
    process_name,
    NULL as window_hash,
    message,
    category
FROM system_events;

-- 使用例:
-- SELECT * FROM unified_timeline ORDER BY timestamp DESC;
```

### CLIビューアー拡張

既存の`cli_viewer.py`に以下を追加：

```python
def show_unified_timeline(db: DatabaseManager, hours: int = 2) -> None:
    """活動とイベントを統合した時系列表示"""
    pass

def show_events_summary(db: DatabaseManager, date: str = None) -> None:
    """イベントサマリー表示"""
    pass
```

## 設定ファイル拡張

### config/event_collection.yaml（新規作成）

```yaml
event_collection:
  enabled: true
  collection_interval: 300  # 5分ごと
  
  windows:
    enabled: true
    log_names:
      - Application
      - System
      - Security
    event_levels:  # 収集するイベントレベル
      - Error
      - Warning
      - Critical
    max_events_per_collection: 1000
  
  linux:
    enabled: true
    facility_filter:
      - kern
      - user
      - daemon
      - auth
    priority_min: "warning"  # warning以上を収集
  
  classification:
    # イベントID/メッセージパターンによる分類ルール
    rules:
      - pattern: ".*error.*"
        event_type: "error"
        severity: 70
        category: "system"
      - pattern: ".*security.*"
        event_type: "warning"
        severity: 80
        category: "security"
  
  privacy:
    hash_messages: true
    hash_user_names: true
    exclude_patterns: []  # 除外するメッセージパターン
```

## 実装ステップ

1. **データベーススキーマ拡張**
   - `schema.py`に`system_events`テーブル定義を追加
   - マイグレーションスクリプトの作成

2. **イベントコレクター実装**
   - `EventCollector`基底クラスの実装
   - `WindowsEventLogCollector`の実装
   - `LinuxSyslogCollector`の実装

3. **データベースマネージャー拡張**
   - `bulk_insert_events`メソッドの実装
   - イベント取得メソッドの実装

4. **統合表示機能**
   - 統合ビューの作成
   - CLIビューアーの拡張

5. **設定・統合**
   - 設定ファイルの作成
   - 既存のコレクターシステムへの統合

## 関連ファイル

- `lifelog-system/src/lifelog/database/schema.py` - スキーマ定義
- `lifelog-system/src/lifelog/database/db_manager.py` - DB操作
- `lifelog-system/src/lifelog/collectors/event_collector.py` - イベントコレクター（新規）
- `lifelog-system/src/lifelog/cli_viewer.py` - CLIビューアー拡張
- `lifelog-system/config/event_collection.yaml` - 設定ファイル（新規）
