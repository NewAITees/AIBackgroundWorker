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
  echo "  $0 [analyze|deep|report|all|errors|today|health]"
  echo ""
  echo "オプション:"
  echo "  analyze  - 分析ジョブのログを表示"
  echo "  deep     - 深掘りジョブのログを表示"
  echo "  report   - レポート生成ジョブのログを表示"
  echo "  all      - すべてのログファイルを表示"
  echo "  errors   - エラーのみを表示"
  echo "  today    - 今日のログのみを表示"
  echo "  health   - 主要問題の発生件数サマリを表示"
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
    rg -n -i "error|warning|failed|exception" "$LOG_DIR"/*.log 2>/dev/null | tail -50
    ;;
  health)
    TODAY=$(date +%Y%m%d)
    TODAY_FILES=("$LOG_DIR"/*_"${TODAY}".log)

    echo "=== 健康状態サマリ（${TODAY}） ==="
    echo ""

    # 今日のログに限定して件数を表示（ファイルがない場合は0）
    if [ -f "${TODAY_FILES[0]}" ]; then
      DB_LOCKS=$(rg -n "database is locked" "${TODAY_FILES[@]}" 2>/dev/null | wc -l)
      RUNPY_WARN=$(rg -n "RuntimeWarning: 'src\\.info_collector\\.jobs\\." "${TODAY_FILES[@]}" 2>/dev/null | wc -l)
      DDG_WARN=$(rg -n "duckduckgo_search.*renamed to .*ddgs" "${TODAY_FILES[@]}" 2>/dev/null | wc -l)
      NO_RESULTS=$(rg -n "No search results for article_id|Too few relevant results" "${TODAY_FILES[@]}" 2>/dev/null | wc -l)
    else
      DB_LOCKS=0
      RUNPY_WARN=0
      DDG_WARN=0
      NO_RESULTS=0
    fi

    echo "database is locked: $DB_LOCKS"
    echo "runpy RuntimeWarning: $RUNPY_WARN"
    echo "duckduckgo_search rename warning: $DDG_WARN"
    echo "deep_research no-result warnings: $NO_RESULTS"
    echo ""
    echo "詳細例（直近20件）:"
    rg -n -i \
      "database is locked|RuntimeWarning: 'src\\.info_collector\\.jobs\\.|duckduckgo_search.*renamed to .*ddgs|No search results for article_id|Too few relevant results" \
      "$LOG_DIR"/*.log 2>/dev/null | tail -20
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
