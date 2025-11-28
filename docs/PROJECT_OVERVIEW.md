# AIBackgroundWorker プロジェクト概要

## プロジェクトの目的

このプロジェクトは、他のAIシステムを動かすための背景として動作する常駐システムを開発するプロジェクトです。ユーザーの活動データと外部情報を自動的に収集・蓄積し、AIシステムが活用できる形でデータを提供します。

## システムアーキテクチャ

本システムは、**内向きの機能**と**外向きの機能**の2つの主要な機能領域で構成されています。

### 1. 内向きの機能（Internal Data Collection）

ユーザーのローカル環境での活動を自動的に収集・記録する機能群です。

#### 1.1 ユーザー活動のデータ収集

- **WSL環境での活動記録**
  - 実行中のプロセス情報
  - アクティブなウィンドウ情報
  - アプリケーション使用状況
  - 活動時間の記録

- **Windows環境での活動記録**
  - フォアグラウンドウィンドウの記録
  - アプリケーション使用状況
  - アクティビティタイムライン

- **データの統合**
  - WSLとWindowsの両方から収集したデータを統合
  - 時系列での活動記録を生成

#### 1.2 ブラウザ情報の自動取得

- **ブラウザ履歴の収集**
  - Braveブラウザの履歴を自動的に取得
  - 定期的なポーリングによる履歴更新
  - 訪問したURL、ドメイン、タイトルなどの情報を記録

- **プライバシー保護**
  - デフォルトでフルURLではなくドメインのみを保存
  - センシティブな情報の除外機能

#### 1.3 ベクターDBへの格納

- 収集したデータをベクターDBに格納
- AIシステムが検索・活用しやすい形式でデータを保存
- セマンティック検索に対応したデータ構造

### 2. 外向きの機能（External Data Collection）

インターネット上の情報を自動的に収集する機能群です。

#### 2.1 ニュース収集

- **最新ニュースの自動収集**
  - インターネット上で最近のニュースを自動的に取得
  - 定期的な更新による最新情報の維持

#### 2.2 RSSフィード収集

- RSSフィードからの情報収集
- 複数のソースからの情報統合

#### 2.3 Web検索機能

- 必要に応じたWeb検索の実行
- 検索結果の要約生成

### 3. データ可視化機能

データベース内の情報を人間が確認できるようにする機能です。

#### 3.1 データ閲覧機能

- **CLIツールによる閲覧**
  - 日別サマリー表示
  - 時間帯別活動状況
  - 最近のタイムライン表示
  - ヘルスメトリクス表示

#### 3.2 データの可視化

- 収集したデータの内容を確認可能な形式で表示
- データの存在場所と内容を把握できるインターフェース
- データの整合性確認機能

## プロジェクト構成

```
AIBackgroundWorker/
├── lifelog-system/       # メインのライフログシステム
│   ├── src/              # ソースコード
│   │   ├── lifelog/      # ライフログコア機能
│   │   ├── browser_history/  # ブラウザ履歴機能
│   │   └── info_collector/    # 外部情報収集機能
│   ├── config/           # 設定ファイル
│   ├── tests/            # テストコード
│   ├── logs/             # ログファイル
│   ├── data/             # データベースファイル
│   ├── pyproject.toml    # プロジェクト設定
│   └── README.md         # ライフログシステムのREADME
├── scripts/              # 実行スクリプト（統合済み）
│   ├── browser/          # ブラウザ情報収集スクリプト
│   │   ├── import_brave_history.sh
│   │   ├── poll_brave_history.sh
│   │   └── install_poll_cron.sh
│   ├── info_collector/   # 外部情報収集スクリプト
│   │   ├── auto_collect.sh        # RSS/ニュース/検索の一括収集
│   │   ├── analyze_articles.sh    # 収集後の分析
│   │   ├── deep_research.sh       # 深掘り調査
│   │   ├── generate_report.sh     # 日次レポート生成
│   │   └── check_logs.sh          # ログ確認
│   ├── lifelog/          # ライフログ関連スクリプト
│   │   ├── merge_windows_logs.py
│   │   ├── get_daily_summary.sh
│   │   └── get_timeline.sh
│   ├── windows/          # Windows関連スクリプト
│   │   └── foreground_logger.ps1
│   └── daemon.sh         # デーモン制御スクリプト
├── docs/                 # ドキュメント
│   └── PROJECT_OVERVIEW.md
├── pyproject.toml        # ルートプロジェクト設定
└── README.md             # プロジェクト全体のREADME
```

## 技術スタック

- **言語**: Python 3.12+
- **データベース**: SQLite (WALモード)
- **ベクターDB**: （実装予定）
- **環境**: WSL2 + Windows
- **パッケージ管理**: uv
- **コード品質**: mypy, black, ruff

## 主要機能の詳細

### ライフログシステム（lifelog-system）

- **イベント駆動型**の高精度トラッキング
- **SQLite WALモード**による高性能データベース
- **プライバシー・バイ・デザイン**（デフォルトで個人情報を保存しない）
- **SLO監視**による運用品質の保証

### データベース構造

- **apps**: アプリケーションマスタ
- **activity_intervals**: 活動区間（メインデータ）
- **health_snapshots**: ヘルスモニタリング

### プライバシー保護

デフォルトで以下の情報は**保存されません**：
- ウィンドウタイトル原文（ハッシュのみ保存）
- ブラウザのフルURL（ドメインのみ保存）
- キー入力内容

## 実行方法

### セットアップ

```bash
# 依存関係のインストール
cd lifelog-system
uv sync
```

### バックグラウンド実行（推奨）

```bash
# ルートディレクトリから実行
ENABLE_WINDOWS_FOREGROUND_LOGGER=1 ./scripts/daemon.sh start

# 状態確認
./scripts/daemon.sh status

# 停止
./scripts/daemon.sh stop
```

### データ閲覧

```bash
# 日別サマリー表示
./scripts/lifelog/get_daily_summary.sh

# タイムライン表示
./scripts/lifelog/get_timeline.sh

# または直接実行
cd lifelog-system
uv run python -m src.lifelog.cli_viewer summary
uv run python -m src.lifelog.cli_viewer hourly
uv run python -m src.lifelog.cli_viewer timeline --hours 2
```

### ブラウザ履歴の収集

```bash
# Brave履歴のインポート
./scripts/browser/import_brave_history.sh

# ポーラーを起動（5分おきに自動収集）
./scripts/browser/poll_brave_history.sh
```

### 外部情報の収集

```bash
# 収集（RSS/ニュース/検索）
./scripts/info_collector/auto_collect.sh --all

# 分析
./scripts/info_collector/analyze_articles.sh --batch-size 30

# 深掘り
./scripts/info_collector/deep_research.sh --batch-size 5

# レポート生成
./scripts/info_collector/generate_report.sh --hours 24
```

## 今後の拡張予定

- ベクターDBへの統合
- MCP Server実装（Claude連携）
- Windows API実装（Win32）
- ブラウザ履歴統合の強化
- ローカルLLMによる日次サマリー
- Web UIによるデータ可視化

## ライセンス

MIT
