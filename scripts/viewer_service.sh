#!/bin/bash
# Viewer Service起動スクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LIFELOG_DIR="$PROJECT_ROOT/lifelog-system"

cd "$LIFELOG_DIR"

# デフォルト設定
HOST="${VIEWER_HOST:-127.0.0.1}"
PORT="${VIEWER_PORT:-8787}"
LIFELOG_DB="${LIFELOG_DB:-$LIFELOG_DIR/data/lifelog.db}"
INFO_DB="${INFO_DB:-$LIFELOG_DIR/data/ai_secretary.db}"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Viewer Service起動スクリプト

OPTIONS:
    start       サービスを起動
    stop        サービスを停止
    status      サービスの状態を確認
    logs        ログを表示
    help        このヘルプを表示

ENVIRONMENT VARIABLES:
    VIEWER_HOST           ホスト (default: 127.0.0.1)
    VIEWER_PORT           ポート (default: 8787)
    LIFELOG_DB            lifelog.dbのパス
    INFO_DB               ai_secretary.dbのパス

EXAMPLES:
    # 起動
    $0 start

    # カスタムポートで起動
    VIEWER_PORT=9000 $0 start

    # 停止
    $0 stop

    # ログ表示
    $0 logs

EOF
}

start_service() {
    echo "Starting Viewer Service..."
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Lifelog DB: $LIFELOG_DB"
    echo "  Info DB: $INFO_DB"

    # 依存関係のインストール確認
    if ! uv pip show fastapi >/dev/null 2>&1; then
        echo "Installing dependencies..."
        uv sync
    fi

    # サービス起動
    uv run python -m src.viewer_service.main \
        --host "$HOST" \
        --port "$PORT" \
        --lifelog-db "$LIFELOG_DB" \
        --info-db "$INFO_DB"
}

stop_service() {
    echo "Stopping Viewer Service..."
    pkill -f "viewer_service.main" || echo "Service not running"
}

status_service() {
    if pgrep -f "viewer_service.main" >/dev/null; then
        echo "Viewer Service is running"
        echo "PID: $(pgrep -f viewer_service.main)"
        echo "URL: http://$HOST:$PORT"
    else
        echo "Viewer Service is not running"
    fi
}

show_logs() {
    echo "Showing logs (Ctrl+C to exit)..."
    tail -f "$LIFELOG_DIR/logs/viewer_service.log" 2>/dev/null || echo "No logs found"
}

case "${1:-}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    status)
        status_service
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
