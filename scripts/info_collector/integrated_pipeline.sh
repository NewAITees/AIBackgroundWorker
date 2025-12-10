#!/usr/bin/env bash
# 統合情報収集パイプライン: analyze → deep → report を連続実行
# 各段階で前段階の結果を活用し、一貫性のある情報処理を実現

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"
LOG_DIR="$PROJECT_ROOT/logs/info_collector"

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

# デフォルト値
ANALYZE_BATCH_SIZE=30
DEEP_BATCH_SIZE=3
DEEP_MIN_IMPORTANCE=0.0
DEEP_MIN_RELEVANCE=0.0
REPORT_HOURS=1  # 統合パイプラインでは直近1時間のみ対象
DB_PATH="data/ai_secretary.db"

# 引数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --analyze-batch-size)
      ANALYZE_BATCH_SIZE="$2"
      shift 2
      ;;
    --deep-batch-size)
      DEEP_BATCH_SIZE="$2"
      shift 2
      ;;
    --deep-min-importance)
      DEEP_MIN_IMPORTANCE="$2"
      shift 2
      ;;
    --deep-min-relevance)
      DEEP_MIN_RELEVANCE="$2"
      shift 2
      ;;
    --report-hours)
      REPORT_HOURS="$2"
      shift 2
      ;;
    --db-path)
      DB_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--analyze-batch-size N] [--deep-batch-size N] [--deep-min-importance F] [--deep-min-relevance F] [--report-hours N] [--db-path PATH]" >&2
      exit 1
      ;;
  esac
done

LOG_FILE="$LOG_DIR/integrated_pipeline_$(date '+%Y%m%d').log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "========================================" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] 統合パイプライン開始" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# ===== ステージ1: 記事分析 =====
echo "" | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] [STAGE 1/3] 記事分析を開始..." | tee -a "$LOG_FILE"
"$SCRIPT_DIR/analyze_articles.sh" \
  --batch-size "$ANALYZE_BATCH_SIZE" \
  --db-path "$DB_PATH" 2>&1 | tee -a "$LOG_FILE"

ANALYZE_EXIT_CODE=${PIPESTATUS[0]}
if [ $ANALYZE_EXIT_CODE -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: 記事分析が失敗しました (exit code: $ANALYZE_EXIT_CODE)" | tee -a "$LOG_FILE"
  exit $ANALYZE_EXIT_CODE
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [STAGE 1/3] 記事分析が完了しました" | tee -a "$LOG_FILE"

# ===== ステージ2: 深掘り調査 =====
echo "" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [STAGE 2/3] 深掘り調査を開始..." | tee -a "$LOG_FILE"
"$SCRIPT_DIR/deep_research.sh" \
  --batch-size "$DEEP_BATCH_SIZE" \
  --min-importance "$DEEP_MIN_IMPORTANCE" \
  --min-relevance "$DEEP_MIN_RELEVANCE" \
  --db-path "$DB_PATH" 2>&1 | tee -a "$LOG_FILE"

DEEP_EXIT_CODE=${PIPESTATUS[0]}
if [ $DEEP_EXIT_CODE -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: 深掘り調査が失敗しました (exit code: $DEEP_EXIT_CODE)" | tee -a "$LOG_FILE"
  exit $DEEP_EXIT_CODE
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [STAGE 2/3] 深掘り調査が完了しました" | tee -a "$LOG_FILE"

# ===== ステージ3: レポート生成 =====
echo "" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [STAGE 3/3] レポート生成を開始..." | tee -a "$LOG_FILE"
"$SCRIPT_DIR/generate_report.sh" \
  --hours "$REPORT_HOURS" \
  --db-path "$DB_PATH" 2>&1 | tee -a "$LOG_FILE"

REPORT_EXIT_CODE=${PIPESTATUS[0]}
if [ $REPORT_EXIT_CODE -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: レポート生成が失敗しました (exit code: $REPORT_EXIT_CODE)" | tee -a "$LOG_FILE"
  exit $REPORT_EXIT_CODE
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [STAGE 3/3] レポート生成が完了しました" | tee -a "$LOG_FILE"

# ===== 完了 =====
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 統合パイプライン完了" | tee -a "$LOG_FILE"
echo "  - 記事分析: $ANALYZE_BATCH_SIZE 件処理" | tee -a "$LOG_FILE"
echo "  - 深掘り調査: $DEEP_BATCH_SIZE 件処理" | tee -a "$LOG_FILE"
echo "  - レポート生成: 直近 $REPORT_HOURS 時間" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit 0
