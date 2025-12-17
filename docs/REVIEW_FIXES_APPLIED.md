# レビュー結果の修正適用サマリー

## 概要

`docs/UNCOMMITTED_FEATURE_REVIEW.md` のレビュー結果を反映し、実装準備ファイルを修正しました。

## 修正内容

### 1. Event Collection (EVENTVIEW) の修正

#### 1.1 スキーマ拡張ファイルの修正

**ファイル:** `lifelog-system/src/lifelog/database/schema_extension_events.sql`

**修正内容:**
- ✅ 統合時系列ビューから `ORDER BY timestamp DESC` を削除
  - SQLiteではビュー内のORDER BYは保証されないため
  - 使用時に明示的に `ORDER BY timestamp DESC` を指定する必要があることをコメントで明記
- ✅ 存在しない `windows` テーブルへの参照を削除
  - `window_hash` のみを使用するように修正

**修正前:**
```sql
LEFT JOIN windows w ON i.window_hash = w.window_hash
ORDER BY timestamp DESC;
```

**修正後:**
```sql
-- 注意: SQLiteではビュー内のORDER BYは保証されないため、
-- 使用時には必ず ORDER BY timestamp DESC を指定すること
-- 使用例: SELECT * FROM unified_timeline ORDER BY timestamp DESC;
```

#### 1.2 イベントコレクターインターフェースの修正

**ファイル:** `lifelog-system/src/lifelog/collectors/event_collector_interface.py`

**修正内容:**
- ✅ `SystemEvent.from_raw_event()` メソッドの改善
  - タイムスタンプ変換処理を改善（ISO形式、datetimeオブジェクト、タイムゾーン対応）
  - `severity` を0-100の範囲にクランプ
  - プライバシー設定（`privacy_config`）パラメータを追加
  - メッセージとユーザー名のハッシュ化オプションを実装準備
- ✅ `EventClassifier.classify_event()` メソッドの改善
  - ログレベルベースの分類ロジックを追加
  - `severity` を0-100の範囲にクランプ
  - 実装時のガイドコメントを追加

**主な変更点:**
```python
# タイムスタンプ変換の改善
if isinstance(timestamp_str, str):
    try:
        event_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except ValueError:
        event_timestamp = datetime.now()

# severityのクランプ
severity = max(0, min(100, severity))

# プライバシー設定の追加
privacy_config = privacy_config or {}
hash_messages = privacy_config.get("hash_messages", True)
```

#### 1.3 設計ドキュメントの修正

**ファイル:** `docs/EVENT_COLLECTION_DESIGN.md`

**修正内容:**
- ✅ 統合時系列ビューの設計を修正
  - `windows` テーブル参照を削除
  - ORDER BYの注意事項を追加

### 2. Integrated Daily Report の修正

#### 2.1 データ集約モジュールの修正

**ファイル:** `lifelog-system/src/info_collector/data_aggregator.py`

**修正内容:**
- ✅ フィールド名の不一致を修正
  - `deep_research` テーブルのタイムスタンプフィールドを `researched_at` に修正（`created_at` ではない）
- ✅ タイムスタンプ変換のガード処理を追加
  - 空文字列や無効なタイムスタンプの場合にスキップ
  - `datetime.fromisoformat()` のエラーハンドリングを追加
  - タイムゾーン対応（"Z"を"+00:00"に変換）
- ✅ 存在しないメソッドへの依存を明記
  - `DatabaseManager.get_events_by_date_range()` が実装される必要があることをコメントで明記
  - `InfoCollectorRepository.fetch_reports_by_date()` が実装される必要があることをコメントで明記

**主な変更点:**
```python
# フィールド名の修正
timestamp_str = research.get("researched_at") or research.get("created_at")

# タイムスタンプガード処理
if not timestamp_str:
    continue

try:
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
except (ValueError, AttributeError):
    continue
```

#### 2.2 プロンプト生成モジュールの修正

**ファイル:** `lifelog-system/src/info_collector/prompts/integrated_report_generation.py`

**修正内容:**
- ✅ タイムライン型変換処理を追加
  - `UnifiedTimelineEntry` (dataclass) を dict に変換する処理を追加
  - `_summarize_timeline()` 関数でdataclassとdictの両方をサポート
- ✅ 関数シグネチャの型ヒントを修正
  - `timeline: list[dict]` → `timeline: list` (dataclassまたはdictのリスト)

**主な変更点:**
```python
# タイムライン型変換
timeline_dicts = []
for entry in timeline:
    if hasattr(entry, 'timestamp'):  # dataclassの場合
        timeline_dicts.append({
            "timestamp": entry.timestamp.isoformat(),
            "source_type": entry.source_type,
            # ...
        })
    else:  # dictの場合
        timeline_dicts.append(entry)
```

#### 2.3 レポート生成モジュールの修正

**ファイル:** `lifelog-system/src/info_collector/jobs/generate_integrated_report.py`

**修正内容:**
- ✅ 関数シグネチャの不一致を修正
  - `build_integrated_prompt()` は個別のリストを要求するため、`DailyReportData` から個別のフィールドを渡すように修正

**修正前:**
```python
prompts = integrated_report_generation.build_integrated_prompt(
    date, data, detail_level
)
```

**修正後:**
```python
prompts = integrated_report_generation.build_integrated_prompt(
    report_date=date,
    lifelog_data=data.lifelog_data,
    events=data.events,
    browser_history=data.browser_history,
    article_analyses=data.article_analyses,
    deep_research=data.deep_research,
    theme_reports=data.theme_reports,
    timeline=data.timeline,
    detail_level=detail_level
)
```

## 残存する課題（実装時に解決が必要）

### 1. データベーススキーマの統合
- `schema_extension_events.sql` の内容を `schema.py` の `CREATE_TABLES_SQL` に統合する必要がある
- 既存データベースへのマイグレーションスクリプトを作成する必要がある

### 2. 存在しないメソッドの実装
- `DatabaseManager.get_events_by_date_range()` メソッドの実装
- `InfoCollectorRepository.fetch_reports_by_date()` メソッドの実装（または既存メソッドの確認）

### 3. 設定ファイルの接続
- `event_collection.yaml` の設定をコレクターに接続する必要がある
- プライバシー設定の実装

### 4. 要約関数の実装
- `_summarize_lifelog()` と `_summarize_browser()` はまだプレースホルダー
- 実装時に実際のデータ要約ロジックを実装する必要がある

### 5. タイムゾーン処理
- タイムゾーンの正規化処理を追加する必要がある
- ユーザー向けの表示形式を統一する必要がある

## 追加で気になる点

### 1. データベース接続の管理
- `DailyReportDataAggregator` で複数のデータベースに接続する際の接続管理
- エラーハンドリングとリトライロジック

### 2. パフォーマンス
- 大量のデータを集約する際のメモリ使用量
- タイムライン構築時のソート処理の最適化

### 3. テスト
- タイムスタンプ変換のエッジケースのテスト
- 存在しないフィールドや空データのテスト

### 4. ドキュメント
- 実装時の注意事項をより詳細に記載
- エラーハンドリングのガイドライン

## 次のステップ

1. **実装開始前の最終確認**
   - 修正内容のレビュー
   - 残存課題の優先順位付け

2. **段階的な実装**
   - Phase 1: イベント情報収集機能（スキーマ統合から）
   - Phase 2: 統合レポート生成機能（データ集約から）

3. **テスト実装**
   - タイムスタンプ変換のテスト
   - 型変換のテスト
   - エラーハンドリングのテスト
