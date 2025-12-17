-- ========================================
-- system_events: システムイベントテーブル（実装準備用）
-- ========================================
-- このファイルは実装準備用です。
-- 実装時には schema.py の CREATE_TABLES_SQL に統合してください。

-- システムイベントテーブル
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
CREATE INDEX IF NOT EXISTS idx_events_process ON system_events(process_name);

-- ========================================
-- 統合時系列ビュー（activity_intervals + system_events）
-- ========================================
-- 注意: SQLiteではビュー内のORDER BYは保証されないため、
-- 使用時には必ず ORDER BY timestamp DESC を指定すること
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

-- ========================================
-- 日次イベントサマリービュー
-- ========================================
CREATE VIEW IF NOT EXISTS daily_event_summary AS
SELECT
    date(event_timestamp) as date,
    event_type,
    category,
    COUNT(*) as event_count,
    AVG(severity) as avg_severity,
    MAX(severity) as max_severity,
    MIN(severity) as min_severity
FROM system_events
GROUP BY date(event_timestamp), event_type, category;
