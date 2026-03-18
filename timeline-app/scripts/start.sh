#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${TIMELINE_APP_HOST:-127.0.0.1}"
PORT="${TIMELINE_APP_PORT:-8100}"

echo "timeline-app を起動します: http://${HOST}:${PORT}"
echo "バックグラウンド worker も FastAPI lifespan で同時起動します"
uv run uvicorn src.main:app --host "$HOST" --port "$PORT" --app-dir "$ROOT_DIR"
