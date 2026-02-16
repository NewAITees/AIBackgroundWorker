#!/usr/bin/env bash
# Compatibility wrapper: keep lifelog-system path while delegating to root script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
ROOT_SCRIPT="$ROOT_DIR/scripts/daemon.sh"

if [ ! -x "$ROOT_SCRIPT" ]; then
  echo "root daemon script not found or not executable: $ROOT_SCRIPT" >&2
  exit 1
fi

LIFELOG_PROJECT_DIR="$PROJECT_DIR" \
LIFELOG_PID_FILE="$PROJECT_DIR/lifelog.pid" \
LIFELOG_LOG_FILE="$PROJECT_DIR/logs/lifelog_daemon.log" \
WIN_LOGGER_PID_FILE="$PROJECT_DIR/windows_logger.pid" \
WIN_LOG_FILE="$PROJECT_DIR/logs/windows_logger.log" \
WIN_JSON_FILE="$PROJECT_DIR/logs/windows_foreground.jsonl" \
exec "$ROOT_SCRIPT" "$@"
