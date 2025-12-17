#!/usr/bin/env bash
# 指定期間のレポートを一括生成
# 例: ./scripts/info_collector/generate_reports_batch.sh --days 21
# 例: ./scripts/info_collector/generate_reports_batch.sh --start-date 2025-01-01 --end-date 2025-01-21

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"
LOG_DIR="$PROJECT_ROOT/logs/info_collector"

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

cd "$LIFELOG_DIR" || exit 1

# デフォルト値
DAYS=21  # 3週間
START_DATE=""
END_DATE=""
DB_PATH="data/ai_secretary.db"
OUTPUT_DIR="data/reports"
SKIP_EXISTING=false

# 引数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      DAYS="$2"
      shift 2
      ;;
    --start-date)
      START_DATE="$2"
      shift 2
      ;;
    --end-date)
      END_DATE="$2"
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
    --skip-existing)
      SKIP_EXISTING=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--days N] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--db-path PATH] [--output-dir PATH] [--skip-existing]" >&2
      exit 1
      ;;
  esac
done

LOG_FILE="$LOG_DIR/generate_reports_batch_$(date '+%Y%m%d').log"

# 日付範囲の決定
if [ -n "$START_DATE" ] && [ -n "$END_DATE" ]; then
  # 開始日と終了日が指定されている場合
  START="$START_DATE"
  END="$END_DATE"
elif [ -n "$END_DATE" ]; then
  # 終了日のみ指定されている場合（開始日は終了日からDAYS日前）
  END="$END_DATE"
  START=$(date -d "$END -$DAYS days" +%Y-%m-%d 2>/dev/null || date -v-${DAYS}d -j -f "%Y-%m-%d" "$END" +%Y-%m-%d 2>/dev/null || python3 -c "from datetime import datetime, timedelta; d = datetime.strptime('$END', '%Y-%m-%d'); print((d - timedelta(days=$DAYS)).strftime('%Y-%m-%d'))")
else
  # デフォルト: 昨日までのDAYS日分
  END=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d 2>/dev/null || python3 -c "from datetime import datetime, timedelta; print((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))")
  START=$(date -d "$END -$DAYS days" +%Y-%m-%d 2>/dev/null || date -v-${DAYS}d -j -f "%Y-%m-%d" "$END" +%Y-%m-%d 2>/dev/null || python3 -c "from datetime import datetime, timedelta; d = datetime.strptime('$END', '%Y-%m-%d'); print((d - timedelta(days=$DAYS)).strftime('%Y-%m-%d'))")
fi

echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] バッチレポート生成開始" | tee -a "$LOG_FILE"
echo "  期間: $START 〜 $END" | tee -a "$LOG_FILE"
echo "  スキップ設定: $SKIP_EXISTING" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 既存のレポートファイルをチェックする関数
check_report_exists() {
  local date=$1
  local report_file="$OUTPUT_DIR/report_${date}.md"
  if [ -f "$report_file" ]; then
    return 0  # 存在する
  else
    return 1  # 存在しない
  fi
}

# 日付リストを生成（Pythonを使用）
DATE_LIST=$(python3 <<EOF
from datetime import datetime, timedelta

start = datetime.strptime('$START', '%Y-%m-%d')
end = datetime.strptime('$END', '%Y-%m-%d')
current = start

dates = []
while current <= end:
    dates.append(current.strftime('%Y-%m-%d'))
    current += timedelta(days=1)

print('\n'.join(dates))
EOF
)

TOTAL_COUNT=$(echo "$DATE_LIST" | wc -l)
SUCCESS_COUNT=0
SKIP_COUNT=0
FAIL_COUNT=0

echo "" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $TOTAL_COUNT 日分のレポートを生成します..." | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 各日付についてレポートを生成
CURRENT=0
for date in $DATE_LIST; do
  CURRENT=$((CURRENT + 1))
  
  # 既存チェック
  if [ "$SKIP_EXISTING" = true ] && check_report_exists "$date"; then
    echo "[$CURRENT/$TOTAL_COUNT] $date: スキップ（既存レポートあり）" | tee -a "$LOG_FILE"
    SKIP_COUNT=$((SKIP_COUNT + 1))
    continue
  fi
  
  echo "[$CURRENT/$TOTAL_COUNT] $date: レポート生成中..." | tee -a "$LOG_FILE"
  
  # レポート生成
  if "$SCRIPT_DIR/generate_report.sh" \
    --date "$date" \
    --db-path "$DB_PATH" \
    --output-dir "$OUTPUT_DIR" >> "$LOG_FILE" 2>&1; then
    echo "[$CURRENT/$TOTAL_COUNT] $date: ✅ 成功" | tee -a "$LOG_FILE"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    echo "[$CURRENT/$TOTAL_COUNT] $date: ❌ 失敗" | tee -a "$LOG_FILE"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    # エラーが発生しても続行（他の日付のレポート生成を続ける）
  fi
  
  # 少し待機（システム負荷を軽減）
  sleep 1
done

# 結果サマリー
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] バッチレポート生成完了" | tee -a "$LOG_FILE"
echo "  成功: $SUCCESS_COUNT 件" | tee -a "$LOG_FILE"
echo "  スキップ: $SKIP_COUNT 件" | tee -a "$LOG_FILE"
echo "  失敗: $FAIL_COUNT 件" | tee -a "$LOG_FILE"
echo "  合計: $TOTAL_COUNT 件" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 失敗がある場合は非ゼロで終了
if [ $FAIL_COUNT -gt 0 ]; then
  exit 1
fi

exit 0
