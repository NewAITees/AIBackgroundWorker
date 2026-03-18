#!/bin/bash
# Lifelog System Daemon Control Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="${LIFELOG_PROJECT_DIR:-$ROOT_DIR/lifelog-system}"
CLEANUP_SCRIPT="$ROOT_DIR/scripts/logs/cleanup_logs.sh"
PID_FILE="${LIFELOG_PID_FILE:-$ROOT_DIR/lifelog.pid}"
LOG_FILE="${LIFELOG_LOG_FILE:-$ROOT_DIR/logs/lifelog_daemon.log}"
WIN_LOGGER_PID_FILE="${WIN_LOGGER_PID_FILE:-$ROOT_DIR/windows_logger.pid}"
WIN_LOG_FILE="${WIN_LOG_FILE:-$ROOT_DIR/logs/windows_logger.log}"
WIN_JSON_FILE="${WIN_JSON_FILE:-$ROOT_DIR/logs/windows_foreground.jsonl}"

# 環境変数でWindows側の前面ウィンドウロガーを起動するか制御
# ENABLE_WINDOWS_FOREGROUND_LOGGER=1 で有効化
WIN_LOGGER_ENABLED="${ENABLE_WINDOWS_FOREGROUND_LOGGER:-0}"
WIN_LOGGER_INTERVAL="${WINDOWS_FOREGROUND_INTERVAL:-5}"      # 秒
WIN_LOGGER_STOP_AFTER="${WINDOWS_FOREGROUND_STOP_AFTER:-0}"  # 秒、0以下なら無制限

# ログディレクトリ作成
mkdir -p "$PROJECT_DIR/logs"

start() {
    echo "lifelog の常駐起動は timeline-app に統合しました。"
    echo "代わりに次を使ってください:"
    echo "  cd \"$ROOT_DIR/timeline-app\" && ./scripts/start.sh"
    return 0
}

stop() {
    echo "停止は timeline-app 側のプロセスを止めてください。"
    return 0
}

status() {
    echo "status は timeline-app の /api/health で確認してください。"
    echo "  http://127.0.0.1:8100/api/health"
    return 0
}

restart() {
    echo "restart も timeline-app 側で行ってください。"
    echo "  cd \"$ROOT_DIR/timeline-app\" && ./scripts/start.sh"
    return 0
}

start_windows_logger() {
    # 既に動作中なら何もしない
    if [ -f "$WIN_LOGGER_PID_FILE" ]; then
        PID=$(cat "$WIN_LOGGER_PID_FILE")
        if ps -p "$PID" >/dev/null 2>&1; then
            echo "Windows foreground logger already running (PID: $PID)"
            return
        else
            rm -f "$WIN_LOGGER_PID_FILE"
        fi
    fi

    # WSLからpowershell.exeを呼び出せる場合のみ
    if ! command -v powershell.exe >/dev/null 2>&1; then
        echo "powershell.exe not found; skipping Windows foreground logger"
        return
    fi

    if [ ! -f "$PROJECT_DIR/scripts/windows/foreground_logger.ps1" ]; then
        echo "foreground_logger.ps1 not found; skipping Windows foreground logger"
        return
    fi

    # wslpathが無い場合はスキップ
    if ! command -v wslpath >/dev/null 2>&1; then
        echo "wslpath not available; skipping Windows foreground logger"
        return
    fi

    WIN_SCRIPT=$(wslpath -w "$PROJECT_DIR/scripts/windows/foreground_logger.ps1")
    WIN_OUTPUT=$(wslpath -w "$WIN_JSON_FILE")

    echo "Starting Windows foreground logger (interval=${WIN_LOGGER_INTERVAL}s)"
    nohup powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass \
        -File "$WIN_SCRIPT" \
        -IntervalSeconds "$WIN_LOGGER_INTERVAL" \
        -StopAfterSeconds "$WIN_LOGGER_STOP_AFTER" \
        -OutputPath "$WIN_OUTPUT" \
        >> "$WIN_LOG_FILE" 2>&1 &

    echo $! > "$WIN_LOGGER_PID_FILE"
    echo "Windows logger started (PID: $(cat "$WIN_LOGGER_PID_FILE"))"
    echo "Windows logger log: $WIN_LOG_FILE"
    echo "Windows foreground JSONL: $WIN_JSON_FILE"
}

stop_windows_logger() {
    if [ ! -f "$WIN_LOGGER_PID_FILE" ]; then
        echo "Windows foreground logger is not running"
        return
    fi
    PID=$(cat "$WIN_LOGGER_PID_FILE")
    if ps -p "$PID" >/dev/null 2>&1; then
        echo "Stopping Windows foreground logger (PID: $PID)..."
        kill "$PID" || true
    fi
    rm -f "$WIN_LOGGER_PID_FILE"
}

logs() {
    echo "timeline-app を直接起動した端末ログ、または worker 状態を確認してください。"
    return 0
}

status_windows_logger() {
    if [ ! -f "$WIN_LOGGER_PID_FILE" ]; then
        echo "Windows foreground logger is not running"
        return 1
    fi
    PID=$(cat "$WIN_LOGGER_PID_FILE")
    if ps -p "$PID" >/dev/null 2>&1; then
        echo "Windows foreground logger is running (PID: $PID)"
        if [ -f "$WIN_LOG_FILE" ]; then
            echo "Last log:"
            tail -n 1 "$WIN_LOG_FILE"
        fi
        return 0
    else
        echo "Windows foreground logger is not running (stale PID file)"
        rm -f "$WIN_LOGGER_PID_FILE"
        return 1
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    winlogger-stop)
        stop_windows_logger
        ;;
    winlogger-status)
        status_windows_logger
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|winlogger-stop|winlogger-status}"
        exit 1
        ;;
esac
