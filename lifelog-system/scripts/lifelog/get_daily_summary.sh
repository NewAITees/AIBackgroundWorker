#!/usr/bin/env bash
# PC活動の日別サマリーを取得

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# デフォルトは今日
DATE="${1:-$(date +"%Y-%m-%d")}"

cd "$ROOT_DIR"
uv run python -m src.lifelog.cli_viewer summary --date "$DATE"
