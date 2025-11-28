#!/usr/bin/env bash
# 分析・深掘り結果から日次レポートを生成
# 例: ./scripts/info_collector/generate_report.sh --hours 24

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"
LOG_DIR="$PROJECT_ROOT/logs/info_collector"

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

cd "$LIFELOG_DIR" || exit 1

# デフォルト値
HOURS=24
DB_PATH="data/ai_secretary.db"
OUTPUT_DIR="data/reports"

# 引数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hours)
      HOURS="$2"
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
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--hours N] [--db-path PATH] [--output-dir PATH]" >&2
      exit 1
      ;;
  esac
done

LOG_FILE="$LOG_DIR/generate_report_$(date '+%Y%m%d').log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting report generation (past $HOURS hours)..." | tee -a "$LOG_FILE"

# 標準出力とエラー出力の両方をログファイルに追記
uv run python -m src.info_collector.jobs.generate_report \
  --db-path "$DB_PATH" \
  --output-dir "$OUTPUT_DIR" \
  --hours "$HOURS" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Report generation completed successfully." | tee -a "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Report generation failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
  exit $EXIT_CODE
fi
