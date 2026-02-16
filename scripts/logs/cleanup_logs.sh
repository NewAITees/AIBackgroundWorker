#!/usr/bin/env bash
# ログ肥大化を防ぐためのクリーンアップ
# - 保存日数を超えたログを削除
# - 総容量が上限を超えた場合は古い順に削除
# - 単一ファイルが巨大化した場合は末尾だけ残してトリム

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 既定値（必要なら環境変数で上書き）
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
LOG_MAX_TOTAL_MB="${LOG_MAX_TOTAL_MB:-1024}"
LOG_MAX_FILE_MB="${LOG_MAX_FILE_MB:-256}"
LOG_KEEP_TAIL_MB="${LOG_KEEP_TAIL_MB:-32}"

MAX_TOTAL_BYTES=$((LOG_MAX_TOTAL_MB * 1024 * 1024))
MAX_FILE_BYTES=$((LOG_MAX_FILE_MB * 1024 * 1024))
KEEP_TAIL_BYTES=$((LOG_KEEP_TAIL_MB * 1024 * 1024))

TARGET_DIRS=(
  "$PROJECT_ROOT/logs"
  "$PROJECT_ROOT/scripts/logs"
  "$PROJECT_ROOT/lifelog-system/logs"
  "$PROJECT_ROOT/lifelog-system/scripts/logs"
)

LOG_EXTENSIONS=(
  "*.log"
  "*.out"
  "*.err"
  "*.jsonl"
)

build_find_expr() {
  local first=1
  for pattern in "${LOG_EXTENSIONS[@]}"; do
    if [ "$first" -eq 0 ]; then
      printf ' -o'
    fi
    printf ' -name %q' "$pattern"
    first=0
  done
}

collect_files() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    return 0
  fi
  local expr
  expr="$(build_find_expr)"
  # shellcheck disable=SC2086
  eval "find \"\$dir\" -type f \\( $expr \\) -print"
}

trim_large_file() {
  local file="$1"
  local size
  size=$(stat -c '%s' "$file" 2>/dev/null || echo 0)
  if [ "$size" -le "$MAX_FILE_BYTES" ]; then
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  tail -c "$KEEP_TAIL_BYTES" "$file" > "$tmp" 2>/dev/null || true
  cat "$tmp" > "$file"
  rm -f "$tmp"
  echo "trimmed: $file (${size} bytes -> keep tail ${KEEP_TAIL_BYTES} bytes)"
}

cleanup_by_retention() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    return 0
  fi
  local expr
  expr="$(build_find_expr)"
  # shellcheck disable=SC2086
  eval "find \"\$dir\" -type f \\( $expr \\) -mtime +\"$LOG_RETENTION_DAYS\" -print -delete" \
    | sed 's/^/deleted(old): /'
}

total_size_bytes() {
  local total=0
  local file size
  while IFS= read -r file; do
    size=$(stat -c '%s' "$file" 2>/dev/null || echo 0)
    total=$((total + size))
  done
  echo "$total"
}

cleanup_by_total_size() {
  local file_list
  file_list="$(mktemp)"

  local dir
  for dir in "${TARGET_DIRS[@]}"; do
    collect_files "$dir"
  done | while IFS= read -r f; do
    stat -c '%Y %n' "$f" 2>/dev/null || true
  done | sort -n | sed 's/^[0-9]\+ //' > "$file_list"

  local total
  total=$(total_size_bytes < "$file_list")
  if [ "$total" -le "$MAX_TOTAL_BYTES" ]; then
    rm -f "$file_list"
    return 0
  fi

  while IFS= read -r file; do
    [ -f "$file" ] || continue
    rm -f "$file"
    echo "deleted(size): $file"
    total=$(total_size_bytes < "$file_list")
    if [ "$total" -le "$MAX_TOTAL_BYTES" ]; then
      break
    fi
  done < "$file_list"

  rm -f "$file_list"
}

run() {
  echo "[cleanup_logs] start $(date '+%Y-%m-%d %H:%M:%S')"
  echo "[cleanup_logs] retention=${LOG_RETENTION_DAYS}d total<=${LOG_MAX_TOTAL_MB}MB single<=${LOG_MAX_FILE_MB}MB keep_tail=${LOG_KEEP_TAIL_MB}MB"

  local dir file
  for dir in "${TARGET_DIRS[@]}"; do
    while IFS= read -r file; do
      trim_large_file "$file"
    done < <(collect_files "$dir")
  done

  for dir in "${TARGET_DIRS[@]}"; do
    cleanup_by_retention "$dir"
  done

  cleanup_by_total_size

  local remaining
  remaining=0
  for dir in "${TARGET_DIRS[@]}"; do
    if [ -d "$dir" ]; then
      remaining=$((remaining + $(du -sb "$dir" | awk '{print $1}')))
    fi
  done
  echo "[cleanup_logs] done remaining_total_bytes=$remaining"
}

run "$@"
