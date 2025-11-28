#!/usr/bin/env bash
# 未分析記事をOllamaで分析
# 例: ./scripts/info_collector/analyze_articles.sh --batch-size 30

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"
LOG_DIR="$PROJECT_ROOT/logs/info_collector"

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

cd "$LIFELOG_DIR" || exit 1

# デフォルト値
BATCH_SIZE=30
DB_PATH="data/ai_secretary.db"

# 引数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch-size)
      BATCH_SIZE="$2"
      shift 2
      ;;
    --db-path)
      DB_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--batch-size N] [--db-path PATH]" >&2
      exit 1
      ;;
  esac
done

LOG_FILE="$LOG_DIR/analyze_articles_$(date '+%Y%m%d').log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting article analysis (batch_size=$BATCH_SIZE)..." | tee -a "$LOG_FILE"

# 標準出力とエラー出力の両方をログファイルに追記
uv run python -m src.info_collector.jobs.analyze_pending \
  --db-path "$DB_PATH" \
  --batch-size "$BATCH_SIZE" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Article analysis completed successfully." | tee -a "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Article analysis failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
  exit $EXIT_CODE
fi
