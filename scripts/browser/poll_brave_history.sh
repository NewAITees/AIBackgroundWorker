#!/bin/bash
#
# Brave履歴を一定間隔で取り込む簡易ポーラー
# デフォルトは5分おきに import_brave_history.sh を実行
#
# Usage:
#   ./scripts/browser/poll_brave_history.sh [--interval 300] [--profile-path PATH] [--limit N] [--json] [--once]
#
# Options:
#   --interval SECONDS   実行間隔（秒）デフォルト: 300
#   --profile-path PATH  Braveプロファイルパス（自動検出しない場合に指定）
#   --limit N            インポート件数上限
#   --json               import_brave_history.sh を JSON 出力モードで実行
#   --lock-file PATH     ロックファイルパス（デフォルト: /tmp/aibackgroundworker_brave_poll.lock）
#   --once               1回だけ実行して終了
#   --help               このヘルプを表示
#
# 備考:
# - flockで多重起動を防止します。同じロックファイルを使う場合、同時起動しません。
# - importが失敗してもポーラー自体は継続します（exitコードはログに表示）。
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INTERVAL=300
PROFILE_PATH=""
LIMIT=""
OUTPUT_JSON="false"
LOCK_FILE="/tmp/aibackgroundworker_brave_poll.lock"
RUN_ONCE="false"

while [[ $# -gt 0 ]]; do
  case $1 in
    --interval)
      INTERVAL="$2"
      shift 2
      ;;
    --profile-path)
      PROFILE_PATH="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --json)
      OUTPUT_JSON="true"
      shift
      ;;
    --lock-file)
      LOCK_FILE="$2"
      shift 2
      ;;
    --once)
      RUN_ONCE="true"
      shift
      ;;
    --help)
      grep "^# " "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

cd "$PROJECT_ROOT"

# ロック取得（多重起動防止）
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  echo "Another poller is running (lock: $LOCK_FILE)."
  exit 0
fi

echo "Brave history poller started. interval=${INTERVAL}s lock=${LOCK_FILE}"

run_import() {
  local cmd=("$PROJECT_ROOT/scripts/browser/import_brave_history.sh")
  [[ -n "$PROFILE_PATH" ]] && cmd+=("--profile-path" "$PROFILE_PATH")
  [[ -n "$LIMIT" ]] && cmd+=("--limit" "$LIMIT")
  [[ "$OUTPUT_JSON" == "true" ]] && cmd+=("--json")

  # importが失敗してもポーラーは継続
  set +e
  "${cmd[@]}"
  local exit_code=$?
  set -e

  if [[ $exit_code -eq 0 ]]; then
    echo "[`date '+%Y-%m-%d %H:%M:%S'`] import OK (exit=${exit_code})"
  else
    echo "[`date '+%Y-%m-%d %H:%M:%S'`] import FAILED (exit=${exit_code})" >&2
  fi
}

trap 'echo "Stopping poller..."; exit 0' INT TERM

while true; do
  run_import
  if [[ "$RUN_ONCE" == "true" ]]; then
    break
  fi
  sleep "$INTERVAL"
done

echo "Poller finished."
