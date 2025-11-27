#!/usr/bin/env bash
# PC活動のタイムラインを取得

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# デフォルトは直近2時間
HOURS="${1:-2}"

cd "$ROOT_DIR/lifelog-system"
uv run python -m src.lifelog.cli_viewer timeline --hours "$HOURS"
