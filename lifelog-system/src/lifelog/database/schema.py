"""
SQLite database schema for lifelog-system.

Design: Interval-normalized schema with WAL mode optimization.
See: doc/design/database_design.md
"""

CREATE_TABLES_SQL = """
-- ========================================
-- apps: アプリケーションマスタ（重複除去）
-- ========================================
CREATE TABLE IF NOT EXISTS apps (
    app_id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_name TEXT NOT NULL,
    process_path_hash TEXT NOT NULL,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    UNIQUE(process_name, process_path_hash)
);

CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(process_name);

-- ========================================
-- activity_intervals: 活動区間（メインデータ）
-- ========================================
CREATE TABLE IF NOT EXISTS activity_intervals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ts DATETIME NOT NULL,
    end_ts DATETIME NOT NULL,
    app_id INTEGER NOT NULL,
    window_hash TEXT NOT NULL,
    domain TEXT,
    is_idle INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER GENERATED ALWAYS AS
        (CAST((julianday(end_ts) - julianday(start_ts)) * 86400 AS INTEGER)) STORED,
    FOREIGN KEY(app_id) REFERENCES apps(app_id)
);

CREATE INDEX IF NOT EXISTS idx_intervals_time ON activity_intervals(start_ts, end_ts);
CREATE INDEX IF NOT EXISTS idx_intervals_app ON activity_intervals(app_id);
CREATE INDEX IF NOT EXISTS idx_intervals_date ON activity_intervals(date(start_ts));

-- ========================================
-- health_snapshots: ヘルスモニタリング（SLO計測用）
-- ========================================
CREATE TABLE IF NOT EXISTS health_snapshots (
    ts DATETIME PRIMARY KEY,
    cpu_percent REAL,
    mem_mb REAL,
    queue_depth INTEGER,
    collection_delay_p50 REAL,
    collection_delay_p95 REAL,
    dropped_events INTEGER,
    db_write_time_p95 REAL
);

CREATE INDEX IF NOT EXISTS idx_health_ts ON health_snapshots(ts);

-- ========================================
-- system_events: システムイベント
-- ========================================
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
    'activity' AS event_source,
    start_ts AS timestamp,
    NULL AS event_type,
    NULL AS severity,
    a.process_name AS process_name,
    i.window_hash AS window_hash,
    NULL AS message,
    NULL AS category
FROM activity_intervals i
JOIN apps a ON i.app_id = a.app_id

UNION ALL

SELECT 
    'system_event' AS event_source,
    event_timestamp AS timestamp,
    event_type,
    severity,
    process_name,
    NULL AS window_hash,
    message,
    category
FROM system_events;

-- ========================================
-- 日次イベントサマリービュー
-- ========================================
CREATE VIEW IF NOT EXISTS daily_event_summary AS
SELECT
    date(event_timestamp) AS date,
    event_type,
    category,
    COUNT(*) AS event_count,
    AVG(severity) AS avg_severity,
    MAX(severity) AS max_severity,
    MIN(severity) AS min_severity
FROM system_events
GROUP BY date(event_timestamp), event_type, category;

-- ========================================
-- 集計用ビュー（クエリ高速化）
-- ========================================
CREATE VIEW IF NOT EXISTS daily_app_usage AS
SELECT
    date(start_ts) as date,
    i.app_id,
    a.process_name,
    SUM(duration_seconds) as total_seconds,
    COUNT(*) as interval_count,
    SUM(CASE WHEN is_idle = 0 THEN duration_seconds ELSE 0 END) as active_seconds
FROM activity_intervals i
JOIN apps a ON i.app_id = a.app_id
GROUP BY date(start_ts), i.app_id;

CREATE VIEW IF NOT EXISTS hourly_activity AS
SELECT
    datetime(start_ts, 'start of hour') as hour,
    SUM(CASE WHEN is_idle = 0 THEN duration_seconds ELSE 0 END) as active_seconds,
    SUM(CASE WHEN is_idle = 1 THEN duration_seconds ELSE 0 END) as idle_seconds
FROM activity_intervals
GROUP BY datetime(start_ts, 'start of hour');
"""


# 既存DBへのマイグレーション用SQL（system_eventsテーブルとビューを追加）
MIGRATION_ADD_EVENTS_SQL = """
-- ========================================
-- system_events: システムイベントテーブル（マイグレーション）
-- ========================================
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp DATETIME NOT NULL,
    event_type TEXT NOT NULL,
    severity INTEGER NOT NULL,
    source TEXT NOT NULL,
    category TEXT,
    event_id INTEGER,
    message TEXT,
    message_hash TEXT,
    raw_data_json TEXT,
    process_name TEXT,
    user_name TEXT,
    machine_name TEXT,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_severity ON system_events(severity DESC);
CREATE INDEX IF NOT EXISTS idx_events_source ON system_events(source);
CREATE INDEX IF NOT EXISTS idx_events_category ON system_events(category);
CREATE INDEX IF NOT EXISTS idx_events_date ON system_events(date(event_timestamp));
CREATE INDEX IF NOT EXISTS idx_events_process ON system_events(process_name);

-- ========================================
-- 統合時系列ビュー（マイグレーション）
-- ========================================
-- 既存のビューを削除して再作成（ビュー定義が変更された場合に対応）
DROP VIEW IF EXISTS unified_timeline;

CREATE VIEW unified_timeline AS
SELECT 
    'activity' AS event_source,
    start_ts AS timestamp,
    NULL AS event_type,
    NULL AS severity,
    a.process_name AS process_name,
    i.window_hash AS window_hash,
    NULL AS message,
    NULL AS category
FROM activity_intervals i
JOIN apps a ON i.app_id = a.app_id

UNION ALL

SELECT 
    'system_event' AS event_source,
    event_timestamp AS timestamp,
    event_type,
    severity,
    process_name,
    NULL AS window_hash,
    message,
    category
FROM system_events;

-- ========================================
-- 日次イベントサマリービュー（マイグレーション）
-- ========================================
DROP VIEW IF EXISTS daily_event_summary;

CREATE VIEW daily_event_summary AS
SELECT
    date(event_timestamp) AS date,
    event_type,
    category,
    COUNT(*) AS event_count,
    AVG(severity) AS avg_severity,
    MAX(severity) AS max_severity,
    MIN(severity) AS min_severity
FROM system_events
GROUP BY date(event_timestamp), event_type, category;
"""


def get_pragma_settings() -> list[str]:
    """
    WALモード用のPRAGMA設定を取得.

    Returns:
        PRAGMA設定のSQLリスト
    """
    return [
        "PRAGMA journal_mode=WAL;",
        "PRAGMA synchronous=NORMAL;",
        "PRAGMA temp_store=MEMORY;",
        "PRAGMA mmap_size=268435456;",  # 256MB
        "PRAGMA page_size=4096;",
        "PRAGMA cache_size=-20000;",  # 約20MB
        "PRAGMA busy_timeout=5000;",  # 5秒
    ]
