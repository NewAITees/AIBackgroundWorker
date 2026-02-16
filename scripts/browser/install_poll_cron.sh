#!/bin/bash
#
# Brave履歴ポーラーをcronに登録するセットアップスクリプト
#
# 既存のcrontabを保持したまま、5分おきのpoll_brave_history.sh実行を追記します。
# 同じ行がすでにある場合は置き換えます。
#
# Usage:
#   ./scripts/browser/install_poll_cron.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
POLL_SCRIPT="$PROJECT_ROOT/scripts/browser/poll_brave_history.sh"
CLEANUP_SCRIPT="$PROJECT_ROOT/scripts/logs/cleanup_logs.sh"
LOG_FILE="$PROJECT_ROOT/logs/brave_poll.log"

# ログディレクトリ作成
mkdir -p "$(dirname "$LOG_FILE")"

# 5分ごとの実行行
CRON_LINE="*/5 * * * * cd \"$PROJECT_ROOT\" && \"$CLEANUP_SCRIPT\" >> \"$LOG_FILE\" 2>&1 && \"$POLL_SCRIPT\" --interval 300 >> \"$LOG_FILE\" 2>&1"

# 既存crontabを取得（なければ空）
TMP_CRON="$(mktemp)"
if crontab -l > "$TMP_CRON" 2>/dev/null; then
  true
else
  # crontab未設定の場合は空ファイルで続行
  : > "$TMP_CRON"
fi

# 既存の同一行を除去
grep -v "$POLL_SCRIPT" "$TMP_CRON" > "${TMP_CRON}.clean" || true
mv "${TMP_CRON}.clean" "$TMP_CRON"

# 新しい行を追記
echo "$CRON_LINE" >> "$TMP_CRON"

# crontabを反映
crontab "$TMP_CRON"
rm "$TMP_CRON"

echo "Installed Brave history poller to cron:"
echo "  $CRON_LINE"
echo "ログ: $LOG_FILE"
