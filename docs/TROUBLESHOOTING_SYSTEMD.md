# systemdサービスのトラブルシューティング

## 問題: サービスが再起動ループになっている

### 症状

```bash
sudo systemctl status lifelog-daemon.service
```

出力:
```
Active: activating (auto-restart) since ...
```

### 原因

1. **PATHに`uv`コマンドが含まれていない**
   - systemdサービスは限られたPATHで実行される
   - `~/.local/bin`がPATHに含まれていない

2. **`daemon.sh start`がバックグラウンドプロセスを起動してすぐに終了する**
   - systemdは`Type=simple`の場合、ExecStartのプロセスが終了すると「サービスが終了した」と判断
   - `Restart=always`により再起動ループが発生

### 解決方法

#### 方法1: systemdサービスを直接プロセスを起動するように変更（推奨）

サービスファイルを修正して、`daemon.sh`を使わずに直接`uv run python`を実行します。

**修正後のサービスファイル**:

```ini
[Unit]
Description=AIBackgroundWorker Lifelog Daemon
After=network.target

[Service]
Type=simple
User=perso
WorkingDirectory=/home/perso/analysis/AIBackgroundWorker/lifelog-system
Environment="ENABLE_WINDOWS_FOREGROUND_LOGGER=1"
Environment="PATH=/home/perso/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/perso/.local/bin/uv run python -m src.lifelog.main_collector
Restart=always
RestartSec=10
StandardOutput=append:/home/perso/analysis/AIBackgroundWorker/logs/lifelog_daemon.log
StandardError=append:/home/perso/analysis/AIBackgroundWorker/logs/lifelog_daemon.log

[Install]
WantedBy=multi-user.target
```

#### 方法2: ログを確認してエラーを特定

**WSL側のターミナルで実行**:

```bash
# サービスのログを確認
sudo journalctl -u lifelog-daemon.service -n 100 --no-pager

# リアルタイムでログを確認
sudo journalctl -u lifelog-daemon.service -f
```

#### 方法3: 手動で実行してエラーを確認

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker/lifelog-system
/home/perso/.local/bin/uv run python -m src.lifelog.main_collector
```

エラーメッセージを確認してください。

---

## 問題: `uv`コマンドが見つからない

### 確認方法

**WSL側のターミナルで実行**:

```bash
which uv
```

### 解決方法

#### 1. `uv`のパスを確認

```bash
ls -la ~/.local/bin/uv
```

#### 2. systemdサービスでPATHを明示的に設定

サービスファイルの`[Service]`セクションに以下を追加:

```ini
Environment="PATH=/home/perso/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

または、`ExecStart`でフルパスを指定:

```ini
ExecStart=/home/perso/.local/bin/uv run python -m src.lifelog.main_collector
```

---

## 問題: Windowsロガーが起動しない

systemdサービスで`ENABLE_WINDOWS_FOREGROUND_LOGGER=1`が設定されていても、Windowsロガーが起動しない場合があります。

### 確認方法

**WSL側のターミナルで実行**:

```bash
# Windowsロガーの状態を確認
cd /home/perso/analysis/AIBackgroundWorker
./scripts/daemon.sh winlogger-status
```

### 解決方法

Windowsロガーは、systemdサービスから直接起動するのではなく、タスクスケジューラで別途設定してください。

---

## サービスを再インストールする場合

**WSL側のターミナルで実行**:

```bash
cd /home/perso/analysis/AIBackgroundWorker

# サービスを停止
sudo systemctl stop lifelog-daemon.service

# サービスを無効化
sudo systemctl disable lifelog-daemon.service

# サービスファイルを更新
sudo cp scripts/systemd/lifelog-daemon.service /etc/systemd/system/

# systemdを再読み込み
sudo systemctl daemon-reload

# サービスを有効化
sudo systemctl enable lifelog-daemon.service

# サービスを起動
sudo systemctl start lifelog-daemon.service

# 状態を確認
sudo systemctl status lifelog-daemon.service
```

