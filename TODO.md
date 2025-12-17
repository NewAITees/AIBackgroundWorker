# AIBackgroundWorker プロジェクト進捗状況

最終更新: 2025-01-27 (実装状況確認・完了タスク更新)

## 📋 プロジェクト概要

AIシステムを動かすための背景として動作する常駐システム。ユーザーの活動データと外部情報を自動的に収集・蓄積し、AIシステムが活用できる形でデータを提供します。

**技術スタック**: SQLite (WALモード) + Python 3.12 + uv

---

## ✅ 完了済みタスク

### プロジェクト構造の整理
- [x] 不要ファイル（Zone.Identifier、uv.lock、.pidファイル）の削除
- [x] スクリプトの統合（browser、info_collector、lifelog → scripts/）
- [x] パッケージ管理をuvに統一
- [x] プロジェクト構造の整理とドキュメント化
- [x] CLAUDE.mdの作成

### ライフログシステム（lifelog-system）
- [x] 基本的なプロジェクト構造の確立
- [x] SQLiteデータベース構造の実装（lifelog.db）
- [x] デーモン制御スクリプト（scripts/daemon.sh）
- [x] CLIビューアー（日別サマリー、タイムライン、時間帯別活動）
- [x] Windows前面ウィンドウロガー統合
- [x] プライバシー保護機能（ハッシュ化）

### ブラウザ履歴システム
- [x] データモデルの実装（BrowserHistoryEntry）
- [x] リポジトリの実装（BrowserHistoryRepository）
- [x] SQLiteスキーマの実装（ai_secretary.db）
- [x] インポートスクリプト（import_brave_history.sh）
- [x] 定期ポーリングスクリプト（poll_brave_history.sh）
- [x] cron登録スクリプト（install_poll_cron.sh）

### 外部情報収集システム（info_collector）
- [x] 基本的なプロジェクト構造の確立（src/info_collector/）
- [x] SQLiteデータベース構造の実装（repository.py: 299行）
- [x] データモデルの実装（models.py: 74行）
- [x] 設定管理の実装（config.py: 46行）
- [x] ニュース収集機能（collectors/news_collector.py: 164行）
- [x] RSS収集機能（collectors/rss_collector.py: 89行）
- [x] Web検索機能（collectors/search_collector.py: 54行）
- [x] DuckDuckGo検索クライアント（search/ddg_client.py: 85行）
- [x] 検索クエリプランナー（search_planner.py: 160行、Ollama統合）
- [x] 記事要約機能（summarizer.py: 232行）
- [x] Deep-dive分析パイプライン（jobs/analyze_pending.py: 106行）
- [x] 深掘りリサーチ機能（jobs/deep_research.py: 133行）
- [x] レポート生成機能（jobs/generate_report.py: 83行）
- [x] プロンプト管理システム（prompts/: 4ファイル、255行）
- [x] 自動実行スクリプト（auto_collect.sh等4つのスクリプト）
- [x] systemd定期実行設定（4つのタイマー: collector/analyze/deep/report）
- [x] ユニットテスト・統合テスト（391行のテストコード）

---

## 🚧 進行中タスク

### CLIビューアーの拡張
- [ ] info_collectorデータの表示機能（ニュース、RSS、検索結果、レポート）
  - [x] viewer_service（Web UI）での表示機能は実装済み ✅
  - [ ] CLIビューアー（cli_viewer.py）での表示機能は未実装
- [x] ブラウザ履歴表示機能 ✅
  - [x] `browser`コマンド（履歴一覧表示）
  - [x] `browser-stats`コマンド（統計表示）
- [ ] ブラウザ履歴とライフログの相関表示
  - [x] viewer_service（Web UI）での統合表示は実装済み ✅
  - [ ] CLIビューアーでの相関表示は未実装

### ブラウザ履歴機能の完成
- [x] `src.browser_history.BraveHistoryImporter` の実装確認・完成 ✅
  - [x] `importer.py`に完全実装済み（import_history, find_brave_history_path等）
  - [x] リポジトリとの統合も完了

### ライフログシステムの機能拡張
- [ ] データ収集の精度向上
- [ ] エラーハンドリングの強化
- [ ] ログローテーション機能
- [ ] **イベント情報の収集・格納機能（EVENTVIEW対応）** 🎯
  - [ ] Windowsイベントログやシステムイベント（エラー、警告、重要な操作など）を収集
  - [ ] 現在の`activity_intervals`テーブルに加えて、イベント情報を格納するテーブルを追加
  - [ ] エラー、システムイベント、アプリケーションイベントなど、PCで何が起きているかを把握できる情報を収集
  - [ ] データベーススキーマの拡張（`system_events`テーブルなど）
  - [ ] イベント収集コレクターの実装（Windows EventLog API、Linux syslog等）
  - [ ] イベント情報の分類・重要度判定機能
  - [ ] 既存の`activity_intervals`と統合した時系列表示

---

## 📝 未実装・計画中タスク

### 内向きの機能（Internal Data Collection）

#### ユーザー活動のデータ収集
- [x] WSL環境での活動記録の完全実装 ✅
  - [x] プロセス情報の収集
  - [x] アクティブウィンドウ情報の取得
  - [x] アプリケーション使用状況の記録
- [x] Windows環境での活動記録の完全実装 ✅
  - [x] フォアグラウンドウィンドウの記録
  - [x] アクティビティタイムラインの生成
- [x] WSLとWindowsデータの統合機能 ✅
  - [x] データマージ機能（merge_windows_logs.py）
  - [x] 時系列データの統合
- [ ] タスクスケジューラでの自動実行設定
  - [x] Windows前面ウィンドウロガーの自動起動設定方法 ✅
  - [x] WSL側デーモンの自動起動設定方法 ✅
  - [x] データ統合処理の定期実行設定方法 ✅

#### ブラウザ情報の自動取得
- [x] ブラウザ履歴の可視化機能 ✅
  - [x] 日別アクセス統計（`browser-stats --date`コマンド）
  - [x] ドメイン別集計（`browser-stats`コマンド）
  - [x] タイムライン表示（`browser`コマンド）
- [ ] 他のブラウザ対応（Chrome、Firefox等）
- [x] ブラウザとライフログの統合ビュー ✅
  - [x] viewer_service（Web UI）での統合表示は実装済み
  - [ ] CLIビューアーでの統合表示は未実装

### 外向きの機能（External Data Collection）

#### ニュース収集（SQLiteベース）
- [x] ニュース収集機能の実装 ✅
  - [x] `src.info_collector` パッケージ構造の作成
  - [x] `src.info_collector.NewsCollector` の実装
  - [x] 複数ニュースサイトからの収集
  - [x] SQLiteテーブル設計（news_articles）
- [x] ニュース収集の定期実行機能 ✅
- [x] ニュースの重複排除機能 ✅

#### RSSフィード収集（SQLiteベース）
- [x] RSS収集機能の実装 ✅
  - [x] `src.info_collector.RSSCollector` の実装
  - [x] feedparserライブラリの統合
  - [x] 複数RSSフィードからの収集
  - [x] SQLiteテーブル設計（rss_entries）
- [x] RSS収集の定期実行機能 ✅

#### Web検索機能（SQLiteベース）
- [x] Web検索機能の実装 ✅
  - [x] `src.info_collector.SearchCollector` の実装
  - [x] DuckDuckGo等の検索API統合
  - [x] SQLiteテーブル設計（search_results）
- [x] 検索結果の要約生成機能 ✅
- [x] Deep-dive分析・深掘りリサーチ機能 ✅
- [x] レポート生成パイプライン ✅

#### 情報管理
- [x] `src.info_collector.InfoCollectorRepository` の実装 ✅
- [x] `src.info_collector.InfoCollectorConfig` の実装 ✅
- [x] 情報の重複排除と更新管理 ✅

#### デイリーレポートの包括的統合 🎯
- [ ] **包括的なデイリーレポート生成機能の実装**
  - [ ] 現在のテーマレポートに加えて、すべての情報を統合したデイリーレポートを生成
  - [ ] 含める情報:
    - [ ] ライフログデータ（アクティブウィンドウ、操作状況、時間帯別活動）
    - [ ] イベント情報（エラー、システムイベント、重要な操作）
    - [ ] ブラウザ履歴（訪問したサイト、時間帯別アクセス）
    - [ ] 記事分析結果（重要度・関連度スコア、判断理由）
    - [ ] 深掘り調査結果（検索結果、統合分析）
    - [ ] テーマレポート（既存のテーマ別レポート）
  - [ ] 時間の粒度と意味の明確化:
    - [ ] 各情報のタイムスタンプを統一フォーマットで表示
    - [ ] 時間帯別の活動パターンを可視化
    - [ ] イベントと活動の相関関係を分析
    - [ ] 詳細度の調整（サマリー/詳細/完全版の3段階）
  - [ ] 人間が把握しやすい形式:
    - [ ] 時系列での統合表示
    - [ ] カテゴリ別の整理
    - [ ] 重要度順の並び替え
    - [ ] 視覚的な区切りと見出し構造
  - [ ] 既存の`generate_daily_report.py`を拡張または新規実装
  - [ ] プロンプト設計の改善（すべての情報源を考慮した統合プロンプト）

### データ可視化機能

#### CLIツールの拡張
- [ ] データ閲覧機能の拡張
  - [x] ブラウザ履歴の表示 ✅（`browser`, `browser-stats`コマンド）
  - [ ] 外部情報の表示（info_collector）
    - [x] viewer_service（Web UI）では実装済み ✅
    - [ ] CLIビューアーでは未実装
  - [ ] 検索結果の表示
    - [x] viewer_service（Web UI）では実装済み ✅
    - [ ] CLIビューアーでは未実装
  - [ ] レポートの表示
    - [x] viewer_service（Web UI）では実装済み ✅
    - [ ] CLIビューアーでは未実装
  - [x] データ統計の表示 ✅（`browser-stats`コマンド）
- [ ] エクスポート機能（CSV、JSON等）
- [x] 統合ダッシュボード（全データの概要） ✅
  - [x] viewer_service（Web UI）で実装済み（`/api/dashboard`）
  - [ ] CLIビューアーでの統合ダッシュボードは未実装

### システム統合

#### MCP Server実装
- [ ] MCP Serverの設計
- [ ] Claude連携機能の実装
- [ ] データ取得APIの実装
- [ ] セマンティック検索インターフェース

#### Windows API実装
- [ ] Win32 APIの統合
- [ ] Windows固有機能の実装

### その他の機能

#### パフォーマンス最適化
- [ ] データ収集の効率化
- [ ] データベースクエリの最適化
- [ ] メモリ使用量の最適化

#### テストと品質保証
- [x] ユニットテストの拡充 ✅
  - [x] test_collectors.py（プライバシー関数、ヘルスモニター）
  - [x] test_database.py（データベース操作）
  - [x] test_info_collector_planner.py（検索プランナー）
  - [x] test_jobs.py（ジョブ処理）
- [x] 統合テストの実装 ✅
  - [x] test_integration.py（ライフログ収集フロー）
  - [x] test_jobs_integration.py（ジョブパイプライン）
- [ ] エンドツーエンドテストの実装
- [ ] コードカバレッジの向上

#### ドキュメント
- [ ] APIドキュメントの作成
- [ ] 開発者ガイドの作成
- [ ] 運用マニュアルの作成

---

## 🔮 将来検討タスク（現時点では不要）

### ベクターDB統合（必要になったら実装）
**判断基準**: AIエージェントが実際に使い始めて、セマンティック検索が必要になったら

- [ ] ベクターDBの選定とセットアップ
  - [ ] ChromaDB / Qdrant / Pinecone等の検討
- [ ] データのベクター化処理
  - [ ] テキスト埋め込みの生成
  - [ ] メタデータの付与
- [ ] ベクターDBへの保存機能
- [ ] セマンティック検索機能の実装

**必要になるケース**:
- ニュース記事の全文を保存し始めた時
- 「○○について最近何か情報ある？」のような自然言語クエリが必要な時
- 類似度検索が必要になった時

### Web UI（将来の拡張）
- [ ] Web UIの設計
- [ ] フロントエンドフレームワークの選定
- [ ] バックエンドAPIの実装
- [ ] データ可視化ダッシュボード

### ローカルLLM統合
- [ ] ローカルLLMの選定とセットアップ
- [ ] 日次サマリー生成機能
- [ ] データ分析機能

---

## 🎯 現実的な優先度別タスク

### 【高優先度】今すぐ実装すべき

1. **イベント情報の収集・格納機能（EVENTVIEW対応）** 🎯 ⭐
   - Windowsイベントログやシステムイベントの収集
   - エラー、警告、重要な操作などの情報をDBに格納
   - 理由: PCで何が起きているかを把握するために必要
   - 実装内容:
     - [ ] データベーススキーマの拡張（`system_events`テーブル）
     - [ ] イベント収集コレクターの実装
     - [ ] 既存の`activity_intervals`との統合

2. **包括的なデイリーレポート生成機能** 🎯 ⭐
   - ライフログ、イベント、ブラウザ履歴、記事分析、深掘り調査など、すべての情報を統合
   - 時間の粒度と意味を明確化
   - 人間が把握しやすい形式で出力
   - 理由: 現状の認識と詳細や粒度時間の意味について認識がずれているため
   - 実装内容:
     - [ ] 既存の`generate_daily_report.py`を拡張
     - [ ] すべての情報源を統合したプロンプト設計
     - [ ] 時間帯別の活動パターン可視化

3. **ブラウザ履歴機能の完成** ⭐
   - `src.browser_history.BraveHistoryImporter` の実装確認
   - CLIビューアーでの表示機能追加
   - 理由: リポジトリは実装済み、残りわずかで完成

4. **外部情報収集機能の実装（SQLiteベース）** ⭐
   - `src.info_collector` パッケージ構造の作成
   - ニュース収集機能の実装
   - RSS収集機能の実装
   - 理由: プロジェクトの主要機能の1つ

5. **データ統合・可視化の強化**
   - 全データを統合したCLIダッシュボード
   - ブラウザ履歴とライフログの相関表示
   - 理由: データが増えてきたので統合ビューが必要

### 【中優先度】次に実装すべき

1. **MCP Server実装**
   - Claude連携によるAIシステムとの統合
   - データ取得APIの実装
   - 理由: AIシステムとの連携が目的

2. **定期実行機能の実装**
   - ニュース、RSS、ブラウザ履歴の自動収集
   - cron/タスクスケジューラ設定の自動化
   - 理由: 手動実行は現実的でない

3. **テストの拡充**
   - ユニットテスト
   - 統合テスト
   - 理由: 品質保証

### 【低優先度】余裕があれば

1. **他のブラウザ対応**
2. **Windows API実装（Win32）**
3. **パフォーマンス最適化**

---

## 📊 進捗率

- **プロジェクト構造**: 100% ✅
- **ライフログシステム（基本機能）**: 85% 🚧
- **ブラウザ情報収集（基盤）**: 100% ✅
- **ブラウザ情報収集（完成）**: 85% 🚧
  - [x] BraveHistoryImporter実装完了 ✅
  - [x] CLIビューアーでの表示機能実装完了 ✅
  - [ ] 他のブラウザ対応は未実装
- **外部情報収集（基本機能）**: 90% ✅
  - ニュース収集: 100% ✅
  - RSS収集: 100% ✅
  - Web検索: 100% ✅
  - Deep-dive分析: 100% ✅
  - レポート生成: 100% ✅
  - 定期実行: 100% ✅
  - テスト: 85% 🚧
    - [x] ユニットテスト実装済み ✅
    - [x] 統合テスト実装済み ✅
    - [ ] エンドツーエンドテスト未実装
- **データ可視化（CLIツール）**: 60% 🚧
  - [x] ライフログ表示機能 ✅
  - [x] ブラウザ履歴表示機能 ✅
  - [ ] info_collector表示機能（CLI）未実装
  - [ ] 統合表示機能（CLI）未実装
- **データ可視化（Web UI）**: 90% ✅
  - [x] viewer_service実装完了 ✅
  - [x] 統合ダッシュボード実装完了 ✅
- **MCP Server**: 0% 📝

**全体進捗**: 約 72%（ブラウザ履歴機能の完成、テスト実装、Web UI実装により上昇）

---

## 🚀 次の具体的アクション（優先順位順）

### 【第一ライン】気軽な履歴確認機能の実装（CLI版）⭐ ✅ 完了
**目的**: バックグラウンドで記録した履歴をコマンドラインから気軽に確認できる機能

**実装完了内容**:
- [x] `scripts/view.sh` ラッパースクリプトを作成（プロジェクトルートから実行可能）
- [x] CLIビューアーにinfo_collectorデータ表示機能を追加（news, reportsコマンド）
- [x] 統合ダッシュボードのCLI版を実装（dashboardコマンド）
- [x] カジュアルな確認用コマンドを実装（view, recentコマンド）
- [x] 引数なしで実行したら「今日のサマリー」を表示（デフォルト）

**現状の問題**（解決済み）:
- ✅ Webサーバー（viewer_service）は機能しているが、ブラウザを開く必要がある → CLI版で解決
- ✅ CLIビューアーはライフログ・ブラウザ履歴のみ対応、info_collectorは未対応 → 実装完了
- ✅ 日常的に「今日何があったか」を素早く確認する方法が不足 → `./scripts/view.sh` で解決

**実装内容**:
```bash
# 1. CLIビューアーの拡張（lifelog-system/src/lifelog/cli_viewer.py）
# - info_collector データの表示コマンドを追加
#   - news: 最新ニュース一覧
#   - rss: 最新RSS一覧
#   - reports: 生成されたレポート一覧
#   - info-summary: info_collector統計サマリー

# 2. 統合ダッシュボードのCLI版
# - dashboard コマンド: 全データを統合表示
#   - 今日のライフログサマリー
#   - 最新のブラウザ履歴
#   - 最新のニュース・RSS
#   - 最新のレポート
#   - 統計情報

# 3. カジュアルな確認用コマンド（新規）
# - view または status: 今日の活動をサマリー表示（1画面で完結）
# - recent: 直近N時間の活動・ニュース・レポートを一覧
# - today: 今日の全データを統合表示（詳細版）
# - quick: 5分で確認できる簡易版（重要情報のみ）

# 4. 出力形式の改善
# - rich ライブラリを使用してカラー出力・テーブル表示
# - ページング機能（長いリストの場合）
# - JSON出力オプション（--json フラグ）
```

**参考実装**:
- 既存: `src/viewer_service/queries/info_queries.py`（info_collectorクエリ実装済み）
- 既存: `src/viewer_service/queries/dashboard_queries.py`（統合ダッシュボード実装済み）
- 既存: `src/lifelog/cli_viewer.py`（ライフログ・ブラウザ履歴表示）

**期待される使用例**:
```bash
# プロジェクトルートから実行（最も簡単）
# 引数なし = 今日のサマリーを表示（デフォルト）
./scripts/view.sh

# 直近6時間の活動を確認
./scripts/view.sh recent --hours 6

# 最新のニュースを確認
./scripts/view.sh news --limit 10

# 生成されたレポートを確認
./scripts/view.sh reports --limit 5

# 統合ダッシュボード（全データ）
./scripts/view.sh dashboard

# 今日の詳細版
./scripts/view.sh today
```

**実装方針**:
- [ ] **プロジェクトルートから実行できるラッパースクリプトを作成**
  - `scripts/view.sh` を作成（プロジェクトルートから実行可能）
  - 引数なしで実行したら「今日のサマリー」を表示（デフォルト）
  - サブコマンドで各機能にアクセス（`view`, `recent`, `news`, `reports`, `dashboard`など）
  - 既存の `scripts/lifelog/get_daily_summary.sh` と同じパターン

- [ ] **エイリアス設定の提案（オプション）**
  - `.bashrc` や `.zshrc` に `alias view='cd /home/perso/analysis/AIBackgroundWorker && ./scripts/view.sh'` を追加
  - どこからでも `view` コマンドで実行可能に

### 2. CLIビューアーでのinfo_collector表示機能（1-2日）⭐
```bash
# lifelog-system/src/lifelog/cli_viewer.py に追加
# - info_collector データの表示コマンド
#   - ニュース一覧表示
#   - RSS一覧表示
#   - 検索結果表示
#   - レポート表示
#   - 統計サマリー
# 注意: viewer_service（Web UI）では既に実装済み
# 参考: src/viewer_service/queries/info_queries.py
```

### 2. ブラウザ履歴機能の完成（1-2日）✅ 完了
```bash
# ✅ 実装完了
# - BraveHistoryImporter の実装完了（src/browser_history/importer.py）
# - CLIビューアーでの表示機能実装完了（browser, browser-statsコマンド）
# - 残り: 他のブラウザ対応（Chrome、Firefox等）
```

### 3. データ統合ビューの実装（1-2日）
```bash
# 統合ダッシュボードの実装
# - ライフログ + ブラウザ履歴 + info_collector の統合表示
# - 時系列での相関表示
# - 日次サマリーの拡張
```

---

## 🔄 定期的な更新

このTODOリストは定期的に更新してください。タスクの完了時、新しい要件の追加時、優先度の変更時に更新します。

---

## 📝 メモ

### 技術的な決定事項
- **データベース**: SQLiteを採用（WALモード最適化済み）
  - lifelog.db: ライフログデータ
  - ai_secretary.db: ブラウザ履歴＋外部情報（予定）
- **ベクターDB**: 現時点では不要、将来必要になったら検討
  - 理由: 現在のデータは全て構造化データで、SQLiteで十分検索可能
  - 必要になるタイミング: セマンティック検索、全文検索が必要になった時

### 現状
- プロジェクト構造の整理が完了し、基本的なライフログシステムの骨格は実装済み
- ブラウザ履歴の基盤（モデル、リポジトリ、スクリプト）は実装済み
- 次は「完成」と「外部情報収集」にフォーカス

### 設計方針
- YAGNI原則（You Aren't Gonna Need It）: 必要になるまで実装しない
- まずSQLiteで完成させる → 実際に使ってみる → 必要なら拡張

---

## 📅 2025-12-10 作業記録

最終更新: 2025-12-10

### ✅ 完了した作業

#### 1. 自動起動システムの評価と問題分析
- [x] systemdタイマー/サービスの動作状況評価
  - info-collector.timer: ✅ hourly、正常動作
  - info-integrated.timer: ⚠️ 30分ごと、Ollamaタイムアウトエラー多発
  - brave-history-poller.timer: ✅ 5分ごと、正常動作
  - merge-windows-logs.timer: ✅ 15分ごと、正常動作
- [x] データベース統計の確認
  - 収集済み記事: 9,277件
  - 分析済み: 6,804件（73.3%）
  - 深掘り済み: 650件（7.0%）
  - 生成レポート: 222件
- [x] レポート生成の仕組み分析
  - **問題発見**: 現状は「時間範囲（日ごと）」でグループ化
  - **ユーザー希望**: 「深掘り内容（テーマ）ごと」に記事を書く
  - **原因**: コード設計が `generate_daily_report` で日次を前提

#### 2. Ollamaタイムアウト問題の修正（Phase 1: 負荷軽減）
- [x] **OllamaClientのタイムアウト延長**
  - 変更: 30秒 → 90秒
  - 環境変数 `OLLAMA_TIMEOUT` で設定可能に
  - ファイル: `lifelog-system/src/ai_secretary/ollama_client.py`
- [x] **nice/ionice によるプロセス優先度設定**
  - CPU優先度: 最低（nice -n 19）
  - I/O優先度: アイドル時のみ（ionice -c 3）
  - PC負荷を最小化し、バックグラウンド処理化
- [x] **バッチサイズの削減**
  - info-integrated: analyze 30件→10件、deep 3件→2件
  - info-collector: limit 15件→10件
- [x] **systemdサービスファイルの更新と適用**
  - `~/.config/systemd/user/info-integrated.service`
  - `~/.config/systemd/user/info-collector.service`
  - daemon-reload 完了

#### 3. テーマベースレポート生成機能の実装（2025-01-27）
- [x] **リポジトリにテーマごとに深掘りデータを取得するメソッドを追加**
  - `InfoCollectorRepository.fetch_deep_research_by_theme()` を実装
  - テーマ（summary）ごとにグループ化して深掘り済み記事を取得
- [x] **テーマ特化型プロンプトの作成**
  - `src/info_collector/prompts/theme_report.py` を新規作成
  - テーマごとの包括的なレポート生成プロンプトを実装
- [x] **テーマベースレポート生成ジョブの作成**
  - `src/info_collector/jobs/generate_theme_report.py` を新規作成
  - テーマごとにレポート生成、DB保存 + MDファイル出力
  - ファイル名形式: `article_{theme_slug}_{date}.md`
  - レポートカテゴリ: `category="theme"` で保存
- [x] **テーマレポート生成スクリプトの作成**
  - `scripts/info_collector/generate_theme_report.sh` を新規作成
  - 実行可能権限を設定
- [x] **統合パイプラインへの統合**
  - `scripts/info_collector/integrated_pipeline.sh` にステージ4として追加
  - 分析 → 深掘り → 日次レポート → テーマレポート の順で実行

#### 4. 分析・深掘りの比率向上（2025-01-27）
- [x] **バッチサイズの増加**
  - 分析バッチサイズ: 30 → 50（`analyze_articles.sh`, `integrated_pipeline.sh`）
  - 深掘りバッチサイズ: 3 → 5（`deep_research.sh`, `integrated_pipeline.sh`）
- [x] **深掘り閾値の緩和**
  - 最小重要度: 0.7 → 0.5（`deep_research.sh`）
  - 最小関連度: 0.6 → 0.5（`deep_research.sh`）
  - 統合パイプライン: 0.0 → 0.5（`integrated_pipeline.sh`）
- [x] **systemdサービスファイルの更新**
  - `scripts/systemd/info-integrated.service` を更新
  - 新しいデフォルト値（バッチサイズ50、深掘り5、閾値0.5）を使用

### 🚧 今後のタスク（優先順位順）

#### 高優先度（即座に対応）

0. **バグ修正: Unicode文字処理とSQLインジェクション対策** ✅ 完了（2025-12-10）
   - [x] `_slugify`関数の修正: Unicode文字（日本語）を適切に処理
     - re.UNICODEフラグを追加してUnicode文字を保持
     - 空文字列の場合はhexエンコードでフォールバック
     - 日本語テーマ名（例: 'AI関連', '感染症対策'）が正しくスラッグ化されるように修正
   - [x] SQLインジェクション脆弱性の修正: パラメータ化クエリを使用
     - 日付パラメータをf-string補間からパラメータ化クエリに変更
     - get_info_data関数内の全クエリ（news, RSS, search, analysis）を修正
     - DATE()関数とパラメータ化クエリを組み合わせて安全に処理

1. **Ollamaタイムアウト修正の効果検証** ⏳
   - [ ] 2025-12-10 15:30以降のログ確認
   - [ ] タイムアウトエラーが解消されたか検証
   - [ ] CPU/I/O負荷が軽減されたか確認

2. **テーマベースレポート生成機能の設計・実装** 🎯 ✅ 完了
   - [x] 新規ジョブ `generate_theme_report.py` の作成
   - [x] 深掘りデータをテーマごとにグループ化するロジック（`repository.fetch_deep_research_by_theme()`）
   - [x] テーマ特化型プロンプトの作成（`prompts/theme_report.py`）
   - [x] ファイル名形式: `article_{theme_slug}_{date}.md`
   - [x] レポートカテゴリ: `category="theme"` を追加
   - [x] スクリプト作成: `scripts/info_collector/generate_theme_report.sh`

3. **日次レポートとテーマレポートの併用運用** ✅ 完了
   - [x] 日次レポート: 全体概要把握用（現状維持）
   - [x] テーマレポート: 深掘り内容ごと（新規追加）
   - [x] 統合パイプラインにテーマレポート生成を追加（ステージ4として実装）
   - [x] レポート生成トリガー: 統合パイプライン実行時に自動生成（深掘り済み記事があれば即座に生成）

#### 中優先度（Phase 2: さらなる最適化）

4. **アイドル検出機能の追加（オプション）**
   - [ ] PowerShell経由でWindowsアイドル時間取得スクリプト作成
   - [ ] 統合パイプライン先頭でアイドルチェック実装
   - [ ] 非アイドル時は早期終了する仕組み
   - [ ] 目標: PCアイドル時のみフル性能で処理

5. **Ollamaのスレッド数/GPU使用率制限**
   - [ ] 環境変数 `OLLAMA_NUM_THREAD` の追加
   - [ ] 各ジョブのPythonコードで `options={"num_thread": 4}` 設定
   - [ ] GPU使用率の制限（`num_gpu` パラメータ）

6. **統合パイプラインの実行頻度調整**
   - [ ] 現在: 30分ごと → 提案: 1時間ごと
   - [ ] 理由: 現在の実行時間（7分以上）を考慮
   - [ ] ユーザー確認後に実施

#### 高優先度（新規要件）

7. **気軽な履歴確認機能の実装** 🎯
   - [ ] **要件**: バックグラウンドで記録した履歴を気軽に確認できる機能
   - [ ] **現状**: Webサーバー（viewer_service）は機能しているが、ブラウザを開く必要がある
   - [ ] **目標**: コマンドラインから簡単に、日常的に使える確認方法
   
**実装方針**:
- [ ] **プロジェクトルートから実行できるラッパースクリプトを作成**（最重要）
  - `scripts/view.sh` を作成（プロジェクトルートから実行可能）
  - 引数なしで実行したら「今日のサマリー」を表示（デフォルト）
  - 既存の `scripts/lifelog/get_daily_summary.sh` と同じパターン
  - 例: `./scripts/view.sh` → 今日のサマリー表示
  
- [ ] **CLIビューアーの拡張**
  - [ ] info_collectorデータの表示機能を追加（ニュース、RSS、検索結果、レポート）
  - [ ] 統合ダッシュボードのCLI版を実装
  - [ ] 1コマンドで全データを一覧表示できる機能
  
- [ ] **カジュアルな確認用コマンド**
  - [ ] `view` サブコマンド: 今日の活動をサマリー表示（デフォルト）
  - [ ] `recent` サブコマンド: 直近の活動・ニュース・レポートを一覧
  - [ ] `today` サブコマンド: 今日の全データを統合表示
  - [ ] `quick` サブコマンド: 5分で確認できる簡易版
  
- [ ] **出力形式の改善**
  - [ ] rich ライブラリを使用してカラー出力・テーブル表示
  - [ ] ページング機能（長いリストの場合）
  - [ ] JSON出力オプション（--json フラグ）
  
- [ ] **エイリアス設定の提案**（オプション）
  - `.bashrc` や `.zshrc` に `alias view='cd /home/perso/analysis/AIBackgroundWorker && ./scripts/view.sh'` を追加
  - どこからでも `view` コマンドで実行可能に
   
   **参考実装**:
   - 既存: `lifelog-system/src/lifelog/cli_viewer.py`（ライフログ・ブラウザ履歴表示）
   - 既存: `lifelog-system/src/viewer_service/`（Web UI、API実装済み）
   - 参考: `src/viewer_service/queries/info_queries.py`（info_collectorクエリ実装済み）

### 【第二ライン】デスクトップアプリの実装 🎯
   - [ ] **要件**: バックグラウンドで記録した履歴をデスクトップアプリから気軽に確認
   - [ ] **現状**: Webサーバー（viewer_service）は機能しているが、ブラウザを開く必要がある
   - [ ] **目標**: システムトレイ常駐型の軽量デスクトップアプリ
   - [ ] **優先度**: CLI版（第一ライン）の実装後に検討
   
   **実装方針**:
   - [ ] **技術選定**
     - [ ] **案A: Tauri（推奨）**: 軽量、Rust+Web技術、既存のviewer_serviceを活用可能
     - [ ] **案B: Electron**: Web技術ベース、既存のviewer_serviceをそのまま活用可能
     - [ ] **案C: Python + tkinter/PyQt**: 軽量、Pythonエコシステムと統合しやすい
     - [ ] **案D: システムトレイ常駐型**: 最小限のUI、通知機能付き
   
   - [ ] **機能要件**
     - [ ] システムトレイに常駐（最小化時も動作）
     - [ ] ワンクリックで今日のサマリーを表示
     - [ ] 既存のviewer_service APIを活用（`/api/dashboard`など）
     - [ ] 自動更新機能（定期的にデータを取得）
     - [ ] 通知機能（重要なニュースやレポートが生成されたら通知）
     - [ ] 設定画面（更新間隔、通知設定など）
   
   - [ ] **UI要件**
     - [ ] コンパクトなウィンドウ（画面の一部を占めるだけ）
     - [ ] カード形式での情報表示（ライフログ、ニュース、レポート）
     - [ ] クリックで詳細表示
     - [ ] ダークモード対応
   
   - [ ] **実装優先度**
     - [ ] Phase 1: 基本的な表示機能（既存APIを呼び出すだけ）
     - [ ] Phase 2: システムトレイ常駐機能
     - [ ] Phase 3: 自動更新・通知機能
     - [ ] Phase 4: 設定画面
   
   **参考実装**:
   - 既存: `lifelog-system/src/viewer_service/`（FastAPI、既存API実装済み）
   - 既存: `lifelog-system/src/viewer_service/templates/dashboard.html`（UI参考）

---

## 📊 システム状態（2025-12-10時点）

### データベース統計
- **総記事数**: 9,277件
- **分析済み**: 6,804件（73.3%）
- **深掘り済み**: 650件（7.0%）
- **生成レポート**: 222件

### 主要な問題と対策
| 問題 | 対策 | ステータス |
|------|------|----------|
| Ollamaタイムアウトエラー | タイムアウト延長（30秒→90秒） | ✅ 完了 |
| PC負荷が高い | nice/ionice、バッチサイズ削減 | ✅ 完了 |
| レポートが日ごと | テーマベースレポート機能追加 | ✅ 完了 |
| 分析・深掘り比率が低い | バッチサイズ増加（30→50、3→5）、閾値緩和（0.7→0.5） | ✅ 完了 |
| SQLiteロック競合 | WALモード確認、排他制御 | ⏳ 要対応 |

---
