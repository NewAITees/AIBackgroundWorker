#!/usr/bin/env bash
# 気軽な履歴確認コマンド（ラッパースクリプト）
# 引数なしで実行したら「今日のサマリー」を表示（デフォルト）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"

cd "$LIFELOG_DIR" || exit 1

# 引数なしの場合は「view」コマンド（今日のサマリー）を実行
if [ $# -eq 0 ]; then
  uv run python -m src.lifelog.cli_viewer view
else
  # 引数がある場合はそのままCLIビューアーに渡す
  uv run python -m src.lifelog.cli_viewer "$@"
fi

