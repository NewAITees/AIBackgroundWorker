# 自動実行設定ガイド - WSL systemd + Windowsタスクスケジューラ

このドキュメントでは、AIBackgroundWorkerのすべてのデータ収集を自動化する具体的な手順を説明します。

**更新日**: 2025-11-28
**動作確認済み環境**: WSL2 (Ubuntu) + Windows 11

---

## 📍 前提条件

- WSL2環境（Ubuntu）でsystemdが有効
- プロジェクトパス: `/home/perso/analysis/AIBackgroundWorker`
- Windows側からアクセス可能なパス: `\\wsl.localhost\Ubuntu\home\perso\analysis\AIBackgroundWorker`

### systemdの有効化確認

```bash
systemctl --version
```

systemdが無効な場合は、[付録A: systemdの有効化](#付録a-systemdの有効化)を参照してください。

---

## 🎯 自動実行の構成

### WSL systemdで管理（推奨）

以下のサービス/タイマーはWSL側のsystemdで管理します：

1. **lifelog-daemon** (サービス) - ライフログ収集デーモン（常駐）
2. **brave-history-poller** (タイマー) - ブラウザ履歴収集（5分ごと）
3. **merge-windows-logs** (タイマー) - Windowsログ統合（15分ごと）

### Windowsタスクスケジューラで管理

以下のタスクはWindows側のタスクスケジューラで管理します：

1. **Windows前面ウィンドウロガー** - Windows側の前面ウィンドウ記録（常駐）

**理由**: WSL環境からWindows APIを直接呼び出せないため、PowerShellスクリプトをWindows側で実行する必要があります。

---

## ステップ1: Windows前面ウィンドウロガーの設定（タスクスケジューラ）

### 1-1. タスクスケジューラを開く

1. Windowsキーを押して「タスク スケジューラ」と入力
2. 「タスク スケジューラ」アプリを開く

### 1-2. 基本タスクを作成

1. 右側の「**基本タスクの作成**」をクリック
2. **名前**: `AIBackgroundWorker - Windows Foreground Logger`
3. **説明**: `Windows前面ウィンドウを記録するロガー（常駐実行）`
4. 「次へ」をクリック

### 1-3. トリガーを設定

1. 「**ログオン時**」を選択
2. 「次へ」をクリック

### 1-4. 操作を設定

1. 「**プログラムの開始**」を選択
2. 「次へ」をクリック
3. 以下の値を入力：

   **プログラム/スクリプト**:
   ```
   powershell
   ```

   **引数の追加**:
   ```
   -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\perso\analysis\AIBackgroundWorker\scripts\windows\foreground_logger.ps1" -IntervalSeconds 5 -StopAfterSeconds 0 -OutputPath "\\wsl.localhost\Ubuntu\home\perso\analysis\AIBackgroundWorker\logs\windows_foreground.jsonl"
   ```

4. 「次へ」をクリック

### 1-5. 完了前の確認

1. 「**プロパティを開く**」のチェックボックスを**ON**
2. 「完了」をクリック

### 1-6. 詳細設定

プロパティダイアログが自動で開きます：

1. **全般タブ**:
   - 「**最上位の特権で実行する**」にチェック ✅
   - 「構成」: **Windows 10/11** を選択

2. **条件タブ**:
   - 「コンピューターが AC 電源に接続されている場合のみタスクを開始する」のチェックを**外す** ✅

3. **設定タブ**:
   - 「タスクが実行中の場合に適用される規則」: 「新しいインスタンスを開始しない」を選択

4. 「**OK**」をクリック

### 1-7. 動作確認

```bash
# WSL側で実行
cat /home/perso/analysis/AIBackgroundWorker/logs/windows_foreground.jsonl | tail -5
```

ログファイルにWindows前面ウィンドウの情報が記録されていることを確認してください。

---

## ステップ2: WSL systemdサービス/タイマーの設定

### 2-1. サービスファイルのインストール

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker

# サービスファイルをsystemdディレクトリにコピー
sudo cp scripts/systemd/lifelog-daemon.service /etc/systemd/system/
sudo cp scripts/systemd/brave-history-poller.service /etc/systemd/system/
sudo cp scripts/systemd/brave-history-poller.timer /etc/systemd/system/
sudo cp scripts/systemd/merge-windows-logs.service /etc/systemd/system/
sudo cp scripts/systemd/merge-windows-logs.timer /etc/systemd/system/

# systemdの設定を再読み込み
sudo systemctl daemon-reload
```

### 2-2. サービス/タイマーを有効化して起動

**WSL側のターミナルで実行**:

```bash
# ライフログデーモン（サービス）
sudo systemctl enable lifelog-daemon.service
sudo systemctl start lifelog-daemon.service

# ブラウザ履歴ポーラー（タイマー）
sudo systemctl enable brave-history-poller.timer
sudo systemctl start brave-history-poller.timer

# Windowsログ統合（タイマー）
sudo systemctl enable merge-windows-logs.timer
sudo systemctl start merge-windows-logs.timer
```

### 2-3. 動作確認

**WSL側のターミナルで実行**:

```bash
# サービスの状態確認
sudo systemctl status lifelog-daemon.service

# タイマーの状態確認
sudo systemctl status brave-history-poller.timer
sudo systemctl status merge-windows-logs.timer

# タイマーの一覧表示
sudo systemctl list-timers --all | grep -E "brave|merge"
```

**期待される出力**:

```
● lifelog-daemon.service - AIBackgroundWorker Lifelog Daemon
     Loaded: loaded (/etc/systemd/system/lifelog-daemon.service; enabled; preset: enabled)
     Active: active (running) since ...
```

```
● brave-history-poller.timer - AIBackgroundWorker - Brave History Poller Timer
     Loaded: loaded (/etc/systemd/system/brave-history-poller.timer; enabled; preset: enabled)
     Active: active (waiting) since ...
    Trigger: ... (next execution time)
```

---

## ✅ 設定完了後の確認

すべてのタスクが正しく動作しているか確認します。

### 確認コマンド（WSL側で実行）

```bash
cd /home/perso/analysis/AIBackgroundWorker

# 1. ライフログデーモンの状態確認
sudo systemctl status lifelog-daemon.service

# または daemon.sh で確認
./scripts/daemon.sh status

# 2. タイマーの状態確認
sudo systemctl list-timers --all | grep -E "brave|merge"

# 3. ログファイルの確認
ls -lh logs/

# 4. Windowsログファイルの確認
tail -10 logs/windows_foreground.jsonl

# 5. ブラウザ履歴ログの確認
tail -20 logs/brave_poll.log

# 6. データベースの内容確認
cd lifelog-system
uv run python -m src.lifelog.cli_viewer summary
```

### 有効化の確認

```bash
# すべてのサービス/タイマーが enabled になっているか確認
sudo systemctl is-enabled lifelog-daemon.service
sudo systemctl is-enabled brave-history-poller.timer
sudo systemctl is-enabled merge-windows-logs.timer
```

すべて `enabled` と表示されればOKです。

---

## 🔧 サービス管理コマンド

### ライフログデーモン（サービス）

```bash
# 停止
sudo systemctl stop lifelog-daemon.service

# 再起動
sudo systemctl restart lifelog-daemon.service

# ログ確認
sudo journalctl -u lifelog-daemon.service -f

# または
tail -f /home/perso/analysis/AIBackgroundWorker/logs/lifelog_daemon.log
```

### ブラウザ履歴ポーラー（タイマー）

```bash
# タイマーを停止
sudo systemctl stop brave-history-poller.timer

# タイマーを再起動
sudo systemctl restart brave-history-poller.timer

# 手動で即座に実行（テスト用）
sudo systemctl start brave-history-poller.service

# ログ確認
tail -f /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log
```

### Windowsログ統合（タイマー）

```bash
# タイマーを停止
sudo systemctl stop merge-windows-logs.timer

# タイマーを再起動
sudo systemctl restart merge-windows-logs.timer

# 手動で即座に実行（テスト用）
sudo systemctl start merge-windows-logs.service

# ログ確認
sudo journalctl -u merge-windows-logs.service -f
```

---

## 🔧 トラブルシューティング

### 問題1: lifelog-daemonがすぐに終了する

**症状**:
```bash
sudo systemctl status lifelog-daemon.service
# Main process exited, code=exited, status=2/INVALIDARGUMENT
```

**原因**:
- `uv`コマンドが見つからない、または権限エラー

**解決方法**:

```bash
# 1. uvのパスを確認
which uv
# 出力: /home/perso/.local/bin/uv

# 2. サービスファイルのPATH環境変数を確認
cat /etc/systemd/system/lifelog-daemon.service | grep PATH

# 3. 手動で実行してエラーを確認
cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
HOME=/home/perso /home/perso/.local/bin/uv run python -m src.lifelog.main_collector
```

### 問題2: lifelog-daemonが再起動ループになっている

**症状**:
```bash
sudo systemctl status lifelog-daemon.service
# Active: activating (auto-restart) と表示される
```

**原因**:
1. `uv`のキャッシュディレクトリへのアクセス権限エラー
2. `.venv`ディレクトリへのアクセス権限エラー
3. `HOME`環境変数が設定されていない

**解決方法**:

```bash
# 1. 権限を修正
sudo chown -R $USER:$USER ~/.cache/uv/
cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
chmod -R u+w .venv/

# 2. サービスファイルにHOME環境変数が設定されているか確認
cat /etc/systemd/system/lifelog-daemon.service | grep HOME

# 3. サービスを再起動
sudo systemctl restart lifelog-daemon.service

# 4. ログを確認
tail -50 /home/perso/analysis/AIBackgroundWorker/logs/lifelog_daemon.log
```

### 問題3: ブラウザ履歴が見つからない

**症状**:
```bash
tail logs/brave_poll.log
# ✗ エラー: Brave history file not found.
```

**原因**:
- Braveブラウザがインストールされていない
- Braveブラウザのプロファイルパスが標準的な場所にない

**解決方法**:

```bash
# 1. Braveブラウザのプロファイルパスを確認
# Windowsの場合:
# C:\Users\<USERNAME>\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default

# 2. プロファイルパスを指定して手動実行
cd /home/perso/analysis/AIBackgroundWorker
./scripts/browser/poll_brave_history.sh --once --profile-path "/mnt/c/Users/<USERNAME>/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default"
```

### 問題4: Windowsロガーが起動しない

**確認事項**:
- PowerShellの実行ポリシーを確認

**解決方法**:
```powershell
# PowerShell（管理者権限）で実行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 問題5: タイマーが実行されない

**確認事項**:

```bash
# タイマーが有効化されているか確認
sudo systemctl is-enabled brave-history-poller.timer

# タイマーの状態を確認
sudo systemctl status brave-history-poller.timer

# タイマーの一覧を確認
sudo systemctl list-timers --all
```

**解決方法**:

```bash
# タイマーを再起動
sudo systemctl restart brave-history-poller.timer

# systemdの設定を再読み込み
sudo systemctl daemon-reload
```

---

## 📝 systemdサービス/タイマーファイルの内容

### lifelog-daemon.service

```ini
[Unit]
Description=AIBackgroundWorker Lifelog Daemon
After=network.target

[Service]
Type=forking
User=perso
WorkingDirectory=/home/perso/analysis/AIBackgroundWorker
Environment="HOME=/home/perso"
Environment="ENABLE_WINDOWS_FOREGROUND_LOGGER=1"
Environment="PATH=/home/perso/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/perso/analysis/AIBackgroundWorker/scripts/daemon.sh start
ExecStop=/home/perso/analysis/AIBackgroundWorker/scripts/daemon.sh stop
PIDFile=/home/perso/analysis/AIBackgroundWorker/lifelog.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### brave-history-poller.timer

```ini
[Unit]
Description=AIBackgroundWorker - Brave History Poller Timer
Requires=brave-history-poller.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

### merge-windows-logs.timer

```ini
[Unit]
Description=AIBackgroundWorker - Merge Windows Logs Timer
Requires=merge-windows-logs.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
```

---

## 付録A: systemdの有効化

WSL2でsystemdが無効な場合は、以下の方法で有効化できます。

**WSL側のターミナルで実行**:

```bash
# /etc/wsl.conf を編集
sudo nano /etc/wsl.conf
```

以下の内容を追加：

```ini
[boot]
systemd=true
```

その後、WSLを再起動：

**Windows側のPowerShellで実行**:

```powershell
wsl --shutdown
```

WSLを再起動後、systemdが有効になります。

```bash
# systemdが有効化されたか確認
systemctl --version
```

---

## 🎉 完了

これで、すべてのデータ収集が自動化されました。

- **WSL起動時**: systemdサービス/タイマーが自動起動
- **Windowsログオン時**: Windows前面ウィンドウロガーが自動起動

次回のWSL起動・Windowsログオン時から、すべてのタスクが自動的に起動します。
