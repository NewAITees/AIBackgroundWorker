#!/usr/bin/env bash
# 定期収集用の統合コマンド（RSS/ニュース/Web検索）
# 例: ./scripts/info_collector/auto_collect.sh --use-ollama --limit 15

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"

cd "$LIFELOG_DIR" || exit 1

ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rss|--news|--search|--all)
      ARGS+=("$1")
      shift
      ;;
    --limit)
      ARGS+=("$1" "$2")
      shift 2
      ;;
    --use-ollama)
      ARGS+=("$1")
      shift
      ;;
    --interests-file|--base-queries-file)
      ARGS+=("$1" "$2")
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

uv run python -m src.info_collector.auto_runner "${ARGS[@]}"
