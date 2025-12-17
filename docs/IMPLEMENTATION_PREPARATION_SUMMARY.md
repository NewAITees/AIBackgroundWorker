# 実装準備完了サマリー

## 概要

**【高優先度】今すぐ実装すべき** タスクとして指定されている以下の2機能の実装準備が完了しました：

1. **イベント情報の収集・格納機能（EVENTVIEW対応）** 🎯 ⭐
2. **包括的なデイリーレポート生成機能** 🎯 ⭐

## 優先度と実装理由

### 1. イベント情報の収集・格納機能（EVENTVIEW対応）

**優先度:** 🎯 ⭐ 高優先度 - 今すぐ実装すべき

**実装理由:**
- PCで何が起きているかを把握するために必要
- エラー、警告、重要な操作などの情報をDBに格納して分析可能にする

**実装内容:**
- [x] データベーススキーマの拡張（`system_events`テーブル） - 準備完了
- [x] イベント収集コレクターの実装 - インターフェース設計完了
- [x] 既存の`activity_intervals`との統合 - 設計完了

### 2. 包括的なデイリーレポート生成機能

**優先度:** 🎯 ⭐ 高優先度 - 今すぐ実装すべき

**実装理由:**
- 現状の認識と詳細や粒度時間の意味について認識がずれているため
- ライフログ、イベント、ブラウザ履歴、記事分析、深掘り調査など、すべての情報を統合
- 時間の粒度と意味を明確化
- 人間が把握しやすい形式で出力

**実装内容:**
- [x] 既存の`generate_daily_report.py`を拡張 - 設計完了
- [x] すべての情報源を統合したプロンプト設計 - 準備完了
- [x] 時間帯別の活動パターン可視化 - 設計完了

## 作成されたファイル

### 設計ドキュメント

1. **docs/EVENT_COLLECTION_DESIGN.md**
   - イベント情報収集機能の設計
   - データベーススキーマ（system_eventsテーブル）
   - イベント分類・重要度判定の仕様
   - イベントコレクターの設計

2. **docs/INTEGRATED_DAILY_REPORT_DESIGN.md**
   - 包括的デイリーレポート生成機能の設計
   - 全情報源統合の仕様
   - 時系列表示の設計
   - プロンプト設計

### データベーススキーマ準備

3. **lifelog-system/src/lifelog/database/schema_extension_events.sql**
   - system_eventsテーブル定義
   - 統合時系列ビュー定義
   - 日次イベントサマリービュー定義
   - 実装時にschema.pyに統合する準備

### イベントコレクターインターフェース

4. **lifelog-system/src/lifelog/collectors/event_collector_interface.py**
   - EventCollector基底クラス
   - WindowsEventLogCollectorインターフェース
   - LinuxSyslogCollectorインターフェース
   - EventClassifierクラス
   - 実装時のガイドとして使用

### 統合レポート生成準備

5. **lifelog-system/src/info_collector/data_aggregator.py**
   - DailyReportDataAggregatorクラス
   - データ集約ロジックのインターフェース
   - 統合時系列構築ロジック

6. **lifelog-system/src/info_collector/prompts/integrated_report_generation.py**
   - 統合レポート生成用プロンプト
   - データ要約関数
   - プロンプト構築関数

7. **lifelog-system/src/info_collector/jobs/generate_integrated_report.py**
   - 統合レポート生成モジュール
   - CLIエントリーポイント
   - 実装時のガイドとして使用

## 実装時の手順（優先度順）

> **注意:** 両方とも高優先度ですが、イベント情報収集機能を先に実装することで、統合レポート生成時にイベントデータを利用できます。

### 1. イベント情報収集機能の実装（優先度: 🎯 ⭐）

#### ステップ1: データベーススキーマ拡張
- `lifelog-system/src/lifelog/database/schema.py` の `CREATE_TABLES_SQL` に
  `schema_extension_events.sql` の内容を統合
- 既存データベースへのマイグレーションスクリプト作成

#### ステップ2: データベースマネージャー拡張
- `lifelog-system/src/lifelog/database/db_manager.py` に以下を追加:
  - `bulk_insert_events()` メソッド
  - `get_events_by_date_range()` メソッド
  - `get_events_with_activity()` メソッド

#### ステップ3: イベントコレクター実装
- `event_collector_interface.py` を参考に `event_collector.py` を実装
- Windows環境: `pywin32` または `win32evtlog` を使用
- Linux環境: `systemd-journal` または `journalctl` コマンドを使用

#### ステップ4: 設定ファイル作成
- `lifelog-system/config/event_collection.yaml` を作成
- イベント収集の設定を定義

#### ステップ5: 既存システムへの統合
- `activity_collector.py` にイベント収集機能を統合
- 定期実行の設定

### 2. 包括的デイリーレポート生成機能の実装（優先度: 🎯 ⭐）

> **注意:** イベント情報収集機能の実装が完了していれば、統合レポートにイベント情報を含めることができます。

#### ステップ1: データ集約モジュール実装
- `data_aggregator.py` のTODO部分を実装
- 各データソースからの取得ロジックを実装

#### ステップ2: プロンプト実装
- `integrated_report_generation.py` の要約関数を実装
- プロンプト構築ロジックを完成

#### ステップ3: レポート生成モジュール実装
- `generate_integrated_report.py` のTODO部分を実装
- LLM呼び出しとレポート保存ロジックを実装

#### ステップ4: CLI/スクリプト統合
- `scripts/info_collector/generate_integrated_report.sh` を作成
- 既存の `generate_report.sh` との統合検討

## 実装時の注意事項

### データベーススキーマ
- 既存のデータベースに影響を与えないよう注意
- マイグレーションスクリプトを必ず作成
- インデックスの最適化を考慮

### プライバシー保護
- イベントメッセージのハッシュ化をデフォルトで有効化
- 設定でハッシュ化を無効化可能にする
- ユーザー名も同様にハッシュ化可能にする

### パフォーマンス
- イベント収集は非同期で実行
- バルク書き込みを使用
- 大量データの処理時はページネーションを考慮

### エラーハンドリング
- 各データソースの取得失敗時の処理
- LLM呼び出し失敗時の処理
- 部分的なデータでもレポート生成可能にする

## 実装準備チェックリスト

### イベント情報収集機能（TODO.md対応）

- [x] データベーススキーマの拡張（`system_events`テーブル） - `schema_extension_events.sql` 作成済み
- [x] イベント収集コレクターの実装 - `event_collector_interface.py` インターフェース設計済み
- [x] 既存の`activity_intervals`との統合 - 統合時系列ビュー設計済み

### 包括的デイリーレポート生成機能（TODO.md対応）

- [x] 既存の`generate_daily_report.py`を拡張 - `generate_integrated_report.py` 設計済み
- [x] すべての情報源を統合したプロンプト設計 - `integrated_report_generation.py` 準備済み
- [x] 時間帯別の活動パターン可視化 - `data_aggregator.py` に `analyze_time_patterns()` 実装準備済み

## 次のステップ

1. **実装開始前の確認**
   - 設計ドキュメントのレビュー
   - 実装方針の最終確認
   - TODO.mdの実装内容との整合性確認

2. **段階的な実装（推奨順序）**
   - **Phase 1:** イベント情報収集機能から実装（統合レポートで利用可能にするため）
   - **Phase 2:** 統合レポート生成機能を実装（イベントデータを含む完全な統合レポート）

3. **テスト**
   - 各機能の単体テスト
   - 統合テスト（イベント + レポート生成）
   - パフォーマンステスト

4. **ドキュメント更新**
   - 実装完了後のドキュメント更新
   - 使用方法のドキュメント作成
   - TODO.mdのチェックボックス更新

## 関連ドキュメント

- [TODO.md](../TODO.md) - 優先度別タスクリスト（266-289行目を参照）
- [EVENT_COLLECTION_DESIGN.md](./EVENT_COLLECTION_DESIGN.md) - イベント情報収集機能の詳細設計
- [INTEGRATED_DAILY_REPORT_DESIGN.md](./INTEGRATED_DAILY_REPORT_DESIGN.md) - 統合デイリーレポート生成機能の詳細設計
- [CLAUDE.md](../CLAUDE.md) - プロジェクト全体のガイドライン
