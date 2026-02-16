#!/usr/bin/env bash
# Compatibility wrapper for root script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ROOT_SCRIPT="$ROOT_DIR/scripts/lifelog/get_daily_summary.sh"

if [ ! -x "$ROOT_SCRIPT" ]; then
  echo "root script not found or not executable: $ROOT_SCRIPT" >&2
  exit 1
fi

exec "$ROOT_SCRIPT" "$@"
