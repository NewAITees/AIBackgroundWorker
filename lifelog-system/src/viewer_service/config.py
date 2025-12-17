"""Viewer service configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings


class ViewerConfig(BaseSettings):
    """Viewer service設定."""

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8787
    reload: bool = False

    # Database paths
    lifelog_db: Path = Path("data/lifelog.db")
    info_db: Path = Path("data/ai_secretary.db")

    # Read-only mode
    read_only: bool = True

    # CORS settings
    allow_origins: list[str] = ["http://localhost:8787", "http://127.0.0.1:8787"]

    class Config:
        env_prefix = "VIEWER_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_config() -> ViewerConfig:
    """設定を取得."""
    return ViewerConfig()
