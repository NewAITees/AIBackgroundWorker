"""
timeline-app FastAPI エントリポイント
要件書 21.1.2 の M1 最小 API セット
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health, workspace, timeline, entries, chat

app = FastAPI(title="Timeline App", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発中は全許可、本番では絞る
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(entries.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
