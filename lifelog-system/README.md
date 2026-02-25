# Lifelog System

PC活動を自動的に記録し、AIが理解可能な形式のライフログとして蓄積する基盤システム。

## 概要

- **イベント駆動型**の高精度トラッキング
- **SQLite WALモード**による高性能データベース
- **プライバシー・バイ・デザイン**（デフォルトで個人情報を保存しない）
- **SLO監視**による運用品質の保証

## 保存先（固定）

- Windows保存先: `C:\YellowMable`
- WSL保存先: `/mnt/c/YellowMable`
- レポート既定出力先: `/mnt/c/YellowMable/00_Raw`
- 環境変数: `YELLOWMABLE_DIR`（未指定時は `/mnt/c/YellowMable`）

## インストール

```bash
cd lifelog-system
uv sync
```

## 使用方法

### バックグラウンド実行（推奨）

```bash
cd lifelog-system

# デーモン起動（Windows前面ロガーも起動したい場合はENVを付与）
ENABLE_WINDOWS_FOREGROUND_LOGGER=1 ./scripts/daemon.sh start

# 状態確認
./scripts/daemon.sh status

# ログ確認
./scripts/daemon.sh logs

# デーモン停止
./scripts/daemon.sh stop

# 再起動
./scripts/daemon.sh restart
```

### フォアグラウンド実行（テスト用）

```bash
# デフォルト設定で実行
./run.sh

# 実行時間を制限（テスト用）
./run.sh --duration 60
```

### データ閲覧（CLIツール）

```bash
# 日別サマリー表示
uv run python -m src.cli_viewer summary
uv run python -m src.cli_viewer summary --date 2025-11-10

# 時間帯別活動状況
uv run python -m src.cli_viewer hourly
uv run python -m src.cli_viewer hourly --date 2025-11-10

# 最近のタイムライン
uv run python -m src.cli_viewer timeline --hours 2

# ヘルスメトリクス
uv run python -m src.cli_viewer health --hours 24
```

### 設定

#### config/config.yaml

- サンプリング間隔
- アイドル判定閾値
- バルク書き込み設定
- SLO目標値

#### config/privacy.yaml

- タイトル原文保存の可否
- 除外プロセスリスト
- センシティブキーワード

## データベース構造

### テーブル

- **apps**: アプリケーションマスタ
- **activity_intervals**: 活動区間（メインデータ）
- **health_snapshots**: ヘルスモニタリング

### ビュー

- **daily_app_usage**: 日別アプリ使用時間
- **hourly_activity**: 時間帯別活動状況

## プライバシー保護

デフォルトで以下の情報は**保存されません**：

- ウィンドウタイトル原文（ハッシュのみ保存）
- ブラウザのフルURL（ドメインのみ保存）
- キー入力内容

## Windowsでの前面ウィンドウ記録（補助ツール）

WSL/Ubuntu側ではフォアグラウンド取得が制限されるため、Windowsホスト上で動かす簡易ロガーを同梱しています。

```
cd lifelog-system/scripts/windows
powershell -ExecutionPolicy Bypass -File .\foreground_logger.ps1 -IntervalSeconds 5 -StopAfterSeconds 0
```

- デフォルト出力: `lifelog-system/logs/windows_foreground.jsonl`（JSON Lines）
- パラメータ:
  - `-IntervalSeconds <int>`: 取得間隔（秒）
  - `-StopAfterSeconds <int>`: この秒数で停止（0以下なら無制限）
  - `-OutputPath <path>`: 出力先ファイルを変更

#### lifelogデーモンからWindowsロガーも同時起動する
- WSL上で lifelog デーモンを起動する際に環境変数を付与すると、WSLから `powershell.exe` を呼び出してWindows側ロガーも起動します。
```bash
cd lifelog-system
ENABLE_WINDOWS_FOREGROUND_LOGGER=1 ./scripts/daemon.sh start
```
- 追加の環境変数（任意）  
  - `WINDOWS_FOREGROUND_INTERVAL`: 取得間隔（秒、デフォルト 5）  
  - `WINDOWS_FOREGROUND_STOP_AFTER`: 自動停止までの秒数（0以下で無制限）
- lifelog停止時にWindowsロガーは自動停止しません。止めたい場合は:
```bash
./scripts/daemon.sh winlogger-stop
```
状態確認:
```bash
./scripts/daemon.sh winlogger-status
```

### Windowsタスクスケジューラで常駐させる例
1. 「タスク スケジューラ」を開く
2. 基本タスクの作成 → トリガー「ログオン時」または「コンピューターの起動時」
3. 操作で「プログラムの開始」を選び、以下を指定  
   - プログラム/スクリプト: `powershell`  
   - 引数の追加: `-ExecutionPolicy Bypass -File "C:\path\to\lifelog-system\scripts\windows\foreground_logger.ps1" -IntervalSeconds 5`
4. 必要に応じて「最上位の特権で実行する」にチェック

出力ファイルはWSLから `/mnt/c/path/to/.../windows_foreground.jsonl` として参照できます。WSL側のDBに統合する場合は、別途インポートジョブを用意してください。

## 開発

### テスト実行

```bash
uv run pytest tests/ -v
```

### コードフォーマット

```bash
uv run black src/ tests/
uv run ruff check src/ tests/
```

## ライセンス

MIT

## 今後の拡張

- MCP Server実装（Claude連携）
- Windows API実装（Win32）
- ブラウザ履歴統合
- ローカルLLMによる日次サマリー
