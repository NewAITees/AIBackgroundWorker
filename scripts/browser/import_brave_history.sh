#!/bin/bash
#
# Brave履歴インポートスクリプト
#
# Usage:
#   ./scripts/browser/import_brave_history.sh [OPTIONS]
#
# Options:
#   --profile-path PATH    Braveプロファイルのパス（自動検出される場合は不要）
#   --limit N              インポート件数上限
#   --json                 JSON形式で出力
#   --help                 ヘルプを表示
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# PATHにuvを追加（タスクスケジューラから実行される場合に必要）
export PATH="$HOME/.local/bin:$PATH"

# デフォルト値
PROFILE_PATH=""
LIMIT=""
OUTPUT_JSON="false"

# 引数解析
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile-path)
      PROFILE_PATH="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --json)
      OUTPUT_JSON="true"
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --profile-path PATH    Braveプロファイルのパス"
      echo "  --limit N              インポート件数上限"
      echo "  --json                 JSON形式で出力"
      echo "  --help                 ヘルプを表示"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# uvコマンドのパスを取得（複数の可能性を試す）
UV_CMD=""
if command -v uv &> /dev/null; then
    UV_CMD="uv"
elif [ -f "$HOME/.local/bin/uv" ]; then
    UV_CMD="$HOME/.local/bin/uv"
elif [ -f "/home/perso/.local/bin/uv" ]; then
    UV_CMD="/home/perso/.local/bin/uv"
else
    echo "✗ エラー: uvコマンドが見つかりません。PATHを確認してください: $PATH" >&2
    exit 127
fi

# Python経由でインポート実行
cd "$PROJECT_ROOT/lifelog-system"

PYTHON_SCRIPT=$(cat <<'EOF'
import sys
import json
from pathlib import Path
from src.browser_history import BraveHistoryImporter

try:
    profile_path = sys.argv[1] if sys.argv[1] != "" else None
    limit = int(sys.argv[2]) if sys.argv[2] != "" else None
    output_json = sys.argv[3] == "true"

    importer = BraveHistoryImporter()

    if profile_path:
        profile_path_obj = Path(profile_path)
    else:
        profile_path_obj = None

    count = importer.import_history(profile_path_obj, limit=limit)

    if output_json:
        print(json.dumps({"success": True, "imported_count": count}, ensure_ascii=False))
    else:
        print(f"✓ {count}件の履歴をインポートしました")

except FileNotFoundError as e:
    if output_json:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
    else:
        print(f"✗ エラー: {e}", file=sys.stderr)
    sys.exit(1)

except Exception as e:
    if output_json:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
    else:
        print(f"✗ エラー: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)

"$UV_CMD" run python -c "$PYTHON_SCRIPT" "$PROFILE_PATH" "$LIMIT" "$OUTPUT_JSON"
