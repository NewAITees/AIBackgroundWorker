#!/usr/bin/env bash
# 既存 report / diary / MOC のObsidianリンクを同期

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"

YELLOWMABLE_DIR="${YELLOWMABLE_DIR:-/mnt/c/YellowMable}"
OUTPUT_DIR="${OUTPUT_DIR:-$YELLOWMABLE_DIR/00_Raw}"

cd "$LIFELOG_DIR" || exit 1
uv run python -m src.info_collector.jobs.sync_obsidian_links --output-dir "$OUTPUT_DIR"
