#!/usr/bin/env bash
# ログ確認用ヘルパースクリプト

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs/info_collector"

echo "=== Info Collector ログ確認ツール ==="
echo ""

# 引数がない場合はメニュー表示
if [ $# -eq 0 ]; then
  echo "使い方:"
  echo "  $0 [analyze|deep|report|all|errors|today]"
  echo ""
  echo "オプション:"
  echo "  analyze  - 分析ジョブのログを表示"
  echo "  deep     - 深掘りジョブのログを表示"
  echo "  report   - レポート生成ジョブのログを表示"
  echo "  all      - すべてのログファイルを表示"
  echo "  errors   - エラーのみを表示"
  echo "  today    - 今日のログのみを表示"
  echo ""
  echo "例:"
  echo "  $0 deep      # 深掘りログを表示"
  echo "  $0 errors    # エラーのみ表示"
  echo ""
  echo "systemdログを見る場合:"
  echo "  journalctl --user -u info-deep.service -n 50"
  exit 0
fi

case "$1" in
  analyze)
    echo "=== 分析ジョブログ（最新） ==="
    tail -50 "$LOG_DIR"/analyze_articles_*.log 2>/dev/null | tail -50
    ;;
  deep)
    echo "=== 深掘りジョブログ（最新） ==="
    tail -100 "$LOG_DIR"/deep_research_*.log 2>/dev/null | tail -100
    ;;
  report)
    echo "=== レポート生成ジョブログ（最新） ==="
    tail -50 "$LOG_DIR"/generate_report_*.log 2>/dev/null | tail -50
    ;;
  all)
    echo "=== すべてのログファイル ==="
    ls -lh "$LOG_DIR"/*.log 2>/dev/null
    echo ""
    echo "詳細を見るには: tail -f logs/info_collector/deep_research_$(date +%Y%m%d).log"
    ;;
  errors)
    echo "=== エラーログ（すべて） ==="
    grep -i "error\|warning\|failed\|exception" "$LOG_DIR"/*.log 2>/dev/null | tail -50
    ;;
  today)
    TODAY=$(date +%Y%m%d)
    echo "=== 今日のログ ($TODAY) ==="
    for log in "$LOG_DIR"/*_${TODAY}.log; do
      if [ -f "$log" ]; then
        echo ""
        echo "--- $(basename $log) ---"
        tail -20 "$log"
      fi
    done
    ;;
  *)
    echo "不明なオプション: $1"
    echo "$0 を引数なしで実行してヘルプを表示"
    exit 1
    ;;
esac
