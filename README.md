# AIBackgroundWorker

AIシステムを動かすための背景として動作する常駐システム。ユーザーの活動データと外部情報を自動的に収集・蓄積し、AIシステムが活用できる形でデータを提供します。

## プロジェクト概要

詳細なプロジェクト概要については、[docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) を参照してください。

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

### データ可視化機能

- **データ閲覧機能**
  - DBの中身を人間が見えるように表示
  - CLIツールによるデータ閲覧
  - データの存在場所と内容を把握可能

## プロジェクト構成

- `lifelog-system/`: メインのライフログシステム（PC活動の記録）
- `browser/`: ブラウザ情報収集モジュール
- `info_collector/`: 外部情報収集モジュール（ニュース、RSS等）
- `lifelog/`: ライフログ関連ユーティリティ
- `windows/`: Windows関連機能
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