# AIBackgroundWorker

AIシステムを動かすための背景として動作する常駐システム。ユーザーの活動データと外部情報を自動的に収集・蓄積し、AIシステムが活用できる形でデータを提供します。

## プロジェクト概要

詳細なプロジェクト概要については、[docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) を参照してください。

## 保存先（固定）

- Windows保存先: `C:\YellowMable`
- WSL保存先: `/mnt/c/YellowMable`
- レポート既定出力先: `/mnt/c/YellowMable/00_Raw`
- 環境変数: `YELLOWMABLE_DIR`（未指定時は `/mnt/c/YellowMable`）

リポジトリ直下のシンボリックリンク `YellowMable` からもアクセスできます。

## 主要機能

### 内向きの機能（Internal Data Collection）

- **ユーザー活動のデータ収集**
  - WSLとWindowsでのユーザーの動きをデータとして収集
  - ベクターDBに格納
- **ブラウザ情報の自動取得**
  - ブラウザの履歴を自動的に取得・記録

### 外向きの機能（External Data Collection）

- **インターネット情報の収集**
  - 最近のニュースを自動的に収集
  - RSSフィードからの情報収集
  - Web検索機能

## 自動情報収集（優先機能）

RSS/ニュース/Web検索をまとめて**能動的に1時間ごと収集**できます。興味関心は `lifelog-system/config/info_collector/*.txt` で管理し、`--use-ollama` を付けるとローカルOllamaに検索クエリの提案を依頼します（Ollamaが落ちていてもフォールバックします）。

### 1回実行

```bash
./scripts/info_collector/auto_collect.sh --all --limit 15 --use-ollama
```

### 定期実行（systemdタイマーで毎時）

```bash
sudo cp scripts/systemd/info-collector.service /etc/systemd/system/
sudo cp scripts/systemd/info-collector.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now info-collector.timer
```

設定ファイル:
- `lifelog-system/config/info_collector/rss_feeds.txt`: RSS URL一覧
- `lifelog-system/config/info_collector/news_sites.txt`: ニュースサイトURL一覧
- `lifelog-system/config/info_collector/search_queries.txt`: ベース検索クエリ（フォールバック）
- `lifelog-system/config/info_collector/interests.txt`: ユーザー興味（Ollamaプロンプト用）

## メンテナンス

重複ディレクトリ（`x/x` や想定外の `logs`/`scripts`）の監査:

```bash
uv run python scripts/system/audit_duplicate_dirs.py
```

### データ可視化機能

- **データ閲覧機能**
  - DBの中身を人間が見えるように表示
  - CLIツールによるデータ閲覧
  - データの存在場所と内容を把握可能

## プロジェクト構成

- `lifelog-system/`: メインのライフログシステム本体（`src/`, `config/`, `tests/`）
- `scripts/`: 運用スクリプト群（`lifelog`, `info_collector`, `browser`, `systemd`, `windows`）
- `logs/`: 実行ログ出力先
- `desktop-viewer/`: デスクトップ向けビューア
- `docs/`: ドキュメント

## クイックスタート

詳細な使用方法については、各モジュールのREADMEを参照してください。

### ライフログシステムの起動

```bash
cd lifelog-system
ENABLE_WINDOWS_FOREGROUND_LOGGER=1 ./scripts/daemon.sh start
```

### データ閲覧

```bash
cd lifelog-system
uv run python -m src.cli_viewer summary
```

## ライセンス

MIT
