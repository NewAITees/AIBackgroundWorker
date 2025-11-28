"""Viewer service main application.

FastAPIベースの統合ビューサービス。
ライフログ、ブラウザ履歴、外部情報を統合して表示する。
"""

import argparse
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .config import ViewerConfig, get_config
from .api.routes import router


def create_app(config: ViewerConfig) -> FastAPI:
    """FastAPIアプリケーションを作成."""
    app = FastAPI(
        title="AIBackgroundWorker Viewer",
        description="統合ビューサービス - ライフログ・ブラウザ・外部情報",
        version="0.1.0",
    )

    # CORS設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allow_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # DBパスをアプリケーション状態に保存
    app.state.lifelog_db = config.lifelog_db
    app.state.info_db = config.info_db

    # ルートエンドポイント
    @app.get("/")
    async def root(request: Request):
        """ルートエンドポイント - ダッシュボード表示."""
        templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "api_base": f"http://{config.host}:{config.port}",
            },
        )

    # APIルーターを追加
    app.include_router(router, prefix="/api")

    # 静的ファイル
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


def main():
    """メイン関数."""
    parser = argparse.ArgumentParser(description="Viewer Service")
    parser.add_argument("--host", default="127.0.0.1", help="ホスト")
    parser.add_argument("--port", type=int, default=8787, help="ポート")
    parser.add_argument("--reload", action="store_true", help="リロードモード")
    parser.add_argument("--lifelog-db", type=Path, help="lifelog.dbパス")
    parser.add_argument("--info-db", type=Path, help="ai_secretary.dbパス")

    args = parser.parse_args()

    # 設定を作成
    config = get_config()
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.reload:
        config.reload = args.reload
    if args.lifelog_db:
        config.lifelog_db = args.lifelog_db
    if args.info_db:
        config.info_db = args.info_db

    # アプリケーションを作成
    app = create_app(config)

    # Uvicornで起動
    import uvicorn

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
