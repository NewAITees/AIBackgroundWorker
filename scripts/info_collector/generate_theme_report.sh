#!/usr/bin/env bash
# 深掘り済み記事からテーマベースレポートを生成
# 例: ./scripts/info_collector/generate_theme_report.sh --min-articles 1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"
LOG_DIR="$PROJECT_ROOT/logs/info_collector"

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

cd "$LIFELOG_DIR" || exit 1

# デフォルト値
MIN_ARTICLES=1
DB_PATH="data/ai_secretary.db"
OUTPUT_DIR="/mnt/c/YellowMable/00_Raw"

# 引数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-articles)
      MIN_ARTICLES="$2"
      shift 2
      ;;
    --db-path)
      DB_PATH="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --no-skip-existing)
      SKIP_EXISTING_FLAG="--no-skip-existing"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--min-articles N] [--db-path PATH] [--output-dir PATH] [--no-skip-existing]" >&2
      exit 1
      ;;
  esac
done

LOG_FILE="$LOG_DIR/generate_theme_report_$(date '+%Y%m%d').log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting theme report generation (min_articles=$MIN_ARTICLES)..." | tee -a "$LOG_FILE"

# 標準出力とエラー出力の両方をログファイルに追記
CMD_ARGS=(
  --db-path "$DB_PATH"
  --output-dir "$OUTPUT_DIR"
  --min-articles "$MIN_ARTICLES"
)
if [ -n "${SKIP_EXISTING_FLAG:-}" ]; then
  CMD_ARGS+=(--no-skip-existing)
fi

uv run python -m src.info_collector.jobs.generate_theme_report \
  "${CMD_ARGS[@]}" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Theme report generation completed successfully." | tee -a "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Theme report generation failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
  exit $EXIT_CODE
fi
