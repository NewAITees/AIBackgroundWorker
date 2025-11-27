# タスクスケジューラ設定手順 - 完全ガイド

このドキュメントでは、Windowsタスクスケジューラを使って、すべてのデータ収集を自動化する具体的な手順を説明します。

## 📍 前提条件

- WSL2環境（Ubuntu）で作業している
- プロジェクトパス: `/home/perso/analysis/AIBackgroundWorker`
- Windows側からアクセス可能なパス: `\\wsl.localhost\Ubuntu\home\perso\analysis\AIBackgroundWorker`

---

## 🎯 設定するタスク一覧

以下のタスクを設定します：

### Windowsタスクスケジューラで設定するタスク

1. **Windows前面ウィンドウロガー** - 常駐実行（ログオン時起動）

### WSL側で設定するタスク（systemdサービス・タイマー）

2. **WSL側ライフログデーモン** - 常駐実行（systemdサービスとして設定）
3. **ブラウザ履歴収集** - 5分ごとに実行（systemdタイマーとして設定）✅ **推奨**
4. **Windowsログ統合** - 15分ごとに実行（systemdタイマーとして設定）

**注意**: ブラウザ履歴収集は、PATH環境変数の問題を回避するため、WSL側のsystemdタイマーを使用することを推奨します。

---

## ステップ1: Windows前面ウィンドウロガーの設定

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
   
   **注意**: 出力パスを明示的に指定しています。デフォルトでは同じ場所に出力されますが、明示的に指定することで確実に動作します。

   **開始場所（オプション）**:
   ```
   \\wsl.localhost\Ubuntu\home\perso\analysis\AIBackgroundWorker\scripts\windows
   ```

4. 「次へ」をクリック

### 1-5. 完了前の確認

1. 「**完了**」のチェックボックスを**外す**（詳細設定をするため）
2. 「完了」をクリック

### 1-6. 詳細設定

1. 作成したタスクを右クリック → 「**プロパティ**」を選択
2. **全般タブ**:
   - 「**最上位の特権で実行する**」にチェック ✅
   - 「構成」: **Windows 10/11** を選択
3. **条件タブ**:
   - 「コンピューターが AC 電源に接続されている場合のみタスクを開始する」のチェックを**外す** ✅
4. **設定タブ**:
   - 「タスクが要求されたときに実行する」にチェック ✅
   - 「タスクが実行中でも新しいインスタンスを開始する」を選択
5. 「**OK**」をクリック

### 1-7. 動作確認

1. タスクを右クリック → 「**実行**」を選択
2. 数秒待ってから、タスクを右クリック → 「**履歴**」タブを確認
3. エラーがないことを確認

**確認方法**:
```powershell
# PowerShellで確認（WSLから）
cat /home/perso/analysis/AIBackgroundWorker/logs/windows_foreground.jsonl | tail -5
```

---

## ステップ2: WSL側ライフログデーモンの設定（systemdサービス）

WSL側のデーモンは、systemdサービスとして設定します（WSL2でsystemdが有効な場合）。

### 2-1. systemdサービスファイルを作成

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker

# systemdサービスディレクトリを作成（存在しない場合）
sudo mkdir -p /etc/systemd/system

# サービスファイルを作成
sudo nano /etc/systemd/system/lifelog-daemon.service
```

### 2-2. サービスファイルの内容

プロジェクトに含まれているサービスファイルを使用します：

```bash
# サービスファイルをコピー
sudo cp scripts/systemd/lifelog-daemon.service /etc/systemd/system/
```

サービスファイルの内容：

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

**注意**: 
- `User=perso` の部分は、実際のユーザー名に合わせて変更してください
- `Type=forking` を使用しているため、`daemon.sh start`がバックグラウンドプロセスを起動し、PIDファイルに書き込みます
- `HOME`環境変数を明示的に設定することで、`uv`のキャッシュディレクトリへのアクセス権限問題を回避します

### 2-3. 権限の確認と修正（重要）

**WSL側のターミナルで実行**:

```bash
# uvのキャッシュディレクトリの権限を確認
ls -la ~/.cache/uv/

# 権限が正しくない場合（root所有など）、修正
sudo chown -R perso:perso ~/.cache/uv/

# .venvディレクトリの権限を確認
cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
ls -la .venv/

# 権限が正しくない場合、修正
chmod -R u+w .venv/
```

### 2-4. サービスを有効化

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker

# サービスファイルをコピー
sudo cp scripts/systemd/lifelog-daemon.service /etc/systemd/system/

# systemdの設定を再読み込み
sudo systemctl daemon-reload

# サービスを有効化（起動時に自動起動）
sudo systemctl enable lifelog-daemon.service

# サービスを起動
sudo systemctl start lifelog-daemon.service
```

### 2-5. 動作確認

**WSL側のターミナルで実行**:

```bash
# サービスの状態を確認

sudo systemctl status lifelog-daemon.service

# または、daemon.shで確認
cd /home/perso/analysis/AIBackgroundWorker
./scripts/daemon.sh status
```

**期待される出力**:
```
Lifelog is running (PID: xxxxx)
```

### 2-6. サービス管理コマンド

**WSL側のターミナルで実行**:

```bash
# サービスを停止
sudo systemctl stop lifelog-daemon.service

# サービスを再起動
sudo systemctl restart lifelog-daemon.service

# サービスのログを確認
sudo journalctl -u lifelog-daemon.service -f
```

### 2-7. systemdが無効な場合

WSL2でsystemdが無効な場合は、以下の方法で有効化できます：

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

---

## ステップ3: ブラウザ履歴収集の設定

**推奨方法**: WSL側のsystemdタイマーを使用します（PATH環境変数の問題を回避できます）。

### 方法A: WSL側のsystemdタイマーを使用（推奨）

### 3A-1. systemdサービスとタイマーファイルをインストール

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker

# サービスファイルをコピー
sudo cp scripts/systemd/brave-history-poller.service /etc/systemd/system/
sudo cp scripts/systemd/brave-history-poller.timer /etc/systemd/system/

# systemdの設定を再読み込み
sudo systemctl daemon-reload

# タイマーを有効化
sudo systemctl enable brave-history-poller.timer

# タイマーを起動
sudo systemctl start brave-history-poller.timer
```

### 3A-2. 動作確認

**WSL側のターミナルで実行**:

```bash
# タイマーの状態を確認
sudo systemctl status brave-history-poller.timer

# タイマーの一覧を確認
sudo systemctl list-timers brave-history-poller.timer

# 手動で実行（テスト）
sudo systemctl start brave-history-poller.service

# ログを確認
tail -f /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log
```

### 3A-3. タイマーの管理コマンド

**WSL側のターミナルで実行**:

```bash
# タイマーを停止
sudo systemctl stop brave-history-poller.timer

# タイマーを再起動
sudo systemctl restart brave-history-poller.timer

# タイマーを無効化
sudo systemctl disable brave-history-poller.timer
```

---

### 方法B: Windowsタスクスケジューラを使用（代替方法）

**注意**: この方法ではPATH環境変数の問題が発生する可能性があります。可能であれば方法Aを推奨します。

### 3B-1. タスクを作成

1. 「**基本タスクの作成**」をクリック
2. **名前**: `AIBackgroundWorker - Browser History Poller`
3. **説明**: `Braveブラウザ履歴を5分ごとに収集`
4. 「次へ」をクリック

### 3B-2. トリガーを設定

1. 「**スケジュールに従う**」を選択
2. **繰り返し間隔**: **5分** を選択
3. 「次へ」をクリック

### 3B-3. 操作を設定

1. 「**プログラムの開始**」を選択
2. 「次へ」をクリック
3. 以下の値を入力：

   **プログラム/スクリプト**:
   ```
   wsl
   ```

   **引数の追加**:
   ```
   -d Ubuntu -e bash -c "cd /home/perso/analysis/AIBackgroundWorker && ./scripts/browser/poll_brave_history.sh --once >> /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log 2>&1"
   ```
   
   **注意**: ログファイルへのリダイレクト（`>> .../logs/brave_poll.log 2>&1`）を追加しています。これにより、標準出力と標準エラー出力の両方がログファイルに記録されます。

4. 「次へ」をクリック

### 3B-4. 完了前の確認

1. 「完了」のチェックボックスを**外す**
2. 「完了」をクリック

### 3B-5. 詳細設定

1. 作成したタスクを右クリック → 「**プロパティ**」を選択
2. **全般タブ**:
   - 「**最上位の特権で実行する**」にチェック ✅
3. **条件タブ**:
   - 「コンピューターが AC 電源に接続されている場合のみタスクを開始する」のチェックを**外す** ✅
4. **設定タブ**:
   - 「タスクが要求されたときに実行する」にチェック ✅
   - 「タスクが実行中でも新しいインスタンスを開始する」を選択
5. 「**OK**」をクリック

### 3B-6. 動作確認

1. タスクを右クリック → 「**実行**」を選択
2. WSL側で確認：

```bash
# WSL側で実行
# ログファイルが作成されるまで少し待つ
sleep 5
tail -f /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log
```

**注意**: 
- ログファイルが存在しない場合は、タスクがまだ実行されていないか、エラーが発生している可能性があります
- タスクスケジューラの「履歴」タブでエラーを確認してください
- Braveブラウザがインストールされていない場合、エラーメッセージが表示されます

---

## ステップ4: Windowsログ統合の設定（systemdタイマー）

Windowsログ統合もsystemdタイマーで設定します。

### 4-1. systemdサービスとタイマーファイルをインストール

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker

# サービスファイルをコピー
sudo cp scripts/systemd/merge-windows-logs.service /etc/systemd/system/
sudo cp scripts/systemd/merge-windows-logs.timer /etc/systemd/system/

# systemdの設定を再読み込み
sudo systemctl daemon-reload

# タイマーを有効化
sudo systemctl enable merge-windows-logs.timer

# タイマーを起動
sudo systemctl start merge-windows-logs.timer
```

### 4-2. 動作確認

**WSL側のターミナルで実行**:

```bash
# タイマーの状態を確認
sudo systemctl status merge-windows-logs.timer

# タイマーの一覧を確認
sudo systemctl list-timers merge-windows-logs.timer

# 手動で実行（テスト）
sudo systemctl start merge-windows-logs.service

# サービスのログを確認
sudo journalctl -u merge-windows-logs.service -f
```

### 4-3. タイマーの管理コマンド

**WSL側のターミナルで実行**:

```bash
# タイマーを停止
sudo systemctl stop merge-windows-logs.timer

# タイマーを再起動
sudo systemctl restart merge-windows-logs.timer

# タイマーを無効化
sudo systemctl disable merge-windows-logs.timer
```

### 4-4. データベースの内容確認

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
uv run python -m src.lifelog.cli_viewer summary
```

---

## ✅ 設定完了後の確認

すべてのタスクが正しく動作しているか確認します。

### 確認コマンド（WSL側で実行）

```bash
# 1. ライフログデーモンの状態確認
cd /home/perso/analysis/AIBackgroundWorker
./scripts/daemon.sh status

# 2. Windowsロガーの状態確認
./scripts/daemon.sh winlogger-status

# 3. Windowsログファイルの確認
ls -lh logs/windows_foreground.jsonl

# 4. ブラウザ履歴ログの確認
tail -20 logs/brave_poll.log

# 5. データベースの内容確認
cd lifelog-system
uv run python -m src.lifelog.cli_viewer summary
```

### タスクスケジューラでの確認

1. タスク スケジューラを開く
2. 「タスク スケジューラ ライブラリ」を選択
3. 以下の3つのタスクが表示されていることを確認：
   - `AIBackgroundWorker - Windows Foreground Logger`
   - `AIBackgroundWorker - Browser History Poller`
   - `AIBackgroundWorker - Merge Windows Logs`
4. 各タスクの「状態」が「準備完了」になっていることを確認

### systemdサービスの確認

**WSL側のターミナルで実行**:

```bash
# サービスの状態を確認
sudo systemctl status lifelog-daemon.service
```

---

## 🔧 トラブルシューティング

### 問題1: タスクが実行されない

**確認事項**:
1. タスクを右クリック → 「履歴」タブでエラーを確認
2. 「最上位の特権で実行する」にチェックが入っているか確認
3. パスが正しいか確認（`\\wsl.localhost\Ubuntu\...` の形式）

**解決方法**:
- エラーメッセージを確認して、パスや権限の問題を修正

### 問題2: WSLコマンドが実行されない

**確認事項**:
```powershell
# PowerShellで確認
wsl -l -v
```

**解決方法**:
- WSLが正しくインストールされているか確認
- 引数の `-d Ubuntu` の部分を、実際のディストリビューション名に変更

### 問題3: ログファイルが生成されない

**確認事項**:
```bash
# WSL側で確認
ls -la /home/perso/analysis/AIBackgroundWorker/logs/
```

**解決方法**:
- ログディレクトリが存在するか確認
- 権限の問題がないか確認

### 問題4: Windowsロガーが起動しない

**確認事項**:
- PowerShellの実行ポリシーを確認

**解決方法**:
```powershell
# PowerShell（管理者権限）で実行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 問題5: systemdサービスが再起動ループになっている

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
sudo chown -R perso:perso ~/.cache/uv/
cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
chmod -R u+w .venv/

# 2. サービスファイルにHOME環境変数が設定されているか確認
cat /etc/systemd/system/lifelog-daemon.service | grep HOME

# 3. サービスを再起動
sudo systemctl restart lifelog-daemon.service

# 4. ログを確認
tail -50 /home/perso/analysis/AIBackgroundWorker/logs/lifelog_daemon.log
```

### 問題6: systemdサービスが起動するがすぐに終了する

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

### 問題7: ブラウザ履歴収集タスクが実行されてもログファイルが作成されない

**症状**:
```bash
tail -f /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log
# tail: cannot open '/home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log' for reading: No such file or directory
```

**原因**:
1. タスクスケジューラの設定でログファイルへのリダイレクトが指定されていない
2. ログディレクトリが存在しない

**解決方法**:

```bash
# 1. ログディレクトリが存在するか確認
ls -la /home/perso/analysis/AIBackgroundWorker/logs/

# 2. 存在しない場合は作成
mkdir -p /home/perso/analysis/AIBackgroundWorker/logs/

# 3. タスクスケジューラの設定を確認
# 「引数の追加」に以下が含まれているか確認：
# >> /home/perso/analysis/AIBackgroundWorker/logs/brave_poll.log 2>&1
```

### 問題8: Braveブラウザ履歴が見つからない

**症状**:
```bash
tail logs/brave_poll.log
# ✗ エラー: Brave history file not found. Please specify --profile-path or ensure Brave is installed.
```

**原因**:
- Braveブラウザがインストールされていない
- Braveブラウザのプロファイルパスが標準的な場所にない
- Braveブラウザが実行中で履歴ファイルがロックされている

**解決方法**:

```bash
# 1. Braveブラウザのプロファイルパスを確認
# Windowsの場合:
# C:\Users\<USERNAME>\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default

# 2. プロファイルパスを指定して実行
cd /home/perso/analysis/AIBackgroundWorker
./scripts/browser/poll_brave_history.sh --once --profile-path "/mnt/c/Users/<USERNAME>/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default"

# 3. タスクスケジューラの設定でプロファイルパスを指定する場合
# 「引数の追加」に以下を追加：
# --profile-path "/mnt/c/Users/<USERNAME>/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default"
```

---

## 📝 次のステップ

設定が完了したら、以下を確認してください：

1. **データが正しく収集されているか**
   ```bash
   cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
   uv run python -m src.lifelog.cli_viewer summary
   ```

2. **定期的にデータが更新されているか**
   - 数時間後に再度確認して、データが増えているか確認

3. **ログファイルのサイズを確認**
   - ログファイルが大きくなりすぎていないか確認

---

## 🎉 完了

これで、すべてのデータ収集が自動化されました。次回のログオン時から、すべてのタスクが自動的に起動します。

