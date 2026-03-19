"""
timeline-app FastAPI エントリポイント
要件書 21.1.2 の M1 最小 API セット
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import ai_control, health, workspace, timeline, entries, chat
from .workers.activity_worker import activity_worker
from .workers.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    """FastAPI 起動時に scheduler を開始し、終了時に停止する。"""
    start_scheduler()
    await activity_worker.start()
    try:
        yield
    finally:
        await activity_worker.stop()
        shutdown_scheduler()


app = FastAPI(title="Timeline App", version="0.1.0", lifespan=lifespan)
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発中は全許可、本番では絞る
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(ai_control.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(entries.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

if _FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR), name="assets")


@app.get("/")
async def serve_index():
    """M1 Web フロントの index.html を返す。"""
    return FileResponse(_FRONTEND_DIR / "index.html")
