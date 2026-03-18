"""
設定ローダー
config.yaml を読み込み、アプリ全体で使える設定オブジェクトを提供する

WSL / Windows パス変換:
  WSL  → Windows : /mnt/c/foo/bar  →  C:\\foo\\bar
  Windows → WSL  : C:\\foo\\bar    →  /mnt/c/foo/bar
"""

import re
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8100


class AIConfig(BaseModel):
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    timeout_seconds: int = 60


class WorkspaceDirsConfig(BaseModel):
    daily: str = "daily"
    articles: str = "articles"


class WorkspaceConfig(BaseModel):
    default_path: str = ""
    wsl_mode: bool = False
    dirs: WorkspaceDirsConfig = WorkspaceDirsConfig()


class LifelogConfig(BaseModel):
    root_dir: str = "lifelog-system"
    config_path: str = "lifelog-system/config/config.yaml"
    privacy_config_path: str = "lifelog-system/config/privacy.yaml"
    db_path: str = "lifelog-system/data/lifelog.db"
    activity_sync_seconds: int = 15
    info_db_path: str = "lifelog-system/data/ai_secretary.db"
    browser_import_seconds: int = 3600
    info_config_dir: str = "lifelog-system/config/info_collector"
    info_collect_seconds: int = 3600
    info_limit: int = 10
    hourly_summary_seconds: int = 3600
    hourly_summary_lookback_hours: int = 48


class AppConfig(BaseModel):
    environment: str = "dev"
    server: ServerConfig = ServerConfig()
    ai: AIConfig = AIConfig()
    workspace: WorkspaceConfig = WorkspaceConfig(dirs=WorkspaceDirsConfig())
    lifelog: LifelogConfig = LifelogConfig()


def load_config(path: Optional[Path] = None) -> AppConfig:
    """config.yaml を読み込む。ファイルがなければデフォルト値を返す"""
    target = path or _CONFIG_PATH
    if not target.exists():
        return AppConfig()

    with open(target, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return AppConfig(
        environment=raw.get("environment", "dev"),
        server=ServerConfig(**raw.get("server", {})),
        ai=AIConfig(**raw.get("ai", {})),
        workspace=WorkspaceConfig(
            **{
                **raw.get("workspace", {}),
                "dirs": WorkspaceDirsConfig(**raw.get("workspace", {}).get("dirs", {})),
            }
        ),
        lifelog=LifelogConfig(**raw.get("lifelog", {})),
    )


# アプリ起動時に一度だけロードするシングルトン
config: AppConfig = load_config()


# ---------------------------------------------------------------------------
# WSL / Windows パス変換ユーティリティ
# ---------------------------------------------------------------------------

_WSL_MOUNT_RE = re.compile(r"^/mnt/([a-zA-Z])/(.*)$")
_WIN_DRIVE_RE = re.compile(r"^([a-zA-Z]):[/\\](.*)$")


def wsl_to_windows(path: str) -> str:
    """WSL パスを Windows パスへ変換する。/mnt/c/foo -> C:\\foo"""
    m = _WSL_MOUNT_RE.match(path)
    if m:
        drive = m.group(1).upper()
        rest = m.group(2).replace("/", "\\")
        return f"{drive}:\\{rest}"
    return path  # 変換対象外はそのまま返す


def windows_to_wsl(path: str) -> str:
    """Windows パスを WSL パスへ変換する。C:\\foo -> /mnt/c/foo"""
    m = _WIN_DRIVE_RE.match(path)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return path  # 変換対象外はそのまま返す


def to_local_path(path: str) -> str:
    """
    受け取ったパスを、現在の実行環境（WSL or Windows）で使えるパスに変換する。
    - WSL mode のとき: Windows パスが来たら WSL パスへ変換
    - Windows mode のとき: WSL パスが来たら Windows パスへ変換
    """
    if config.workspace.wsl_mode:
        # WSL で動いている → Windows パスが来たら WSL に変換
        if _WIN_DRIVE_RE.match(path):
            return windows_to_wsl(path)
        return path
    else:
        # Windows で動いている → WSL パスが来たら Windows に変換
        if _WSL_MOUNT_RE.match(path):
            return wsl_to_windows(path)
        return path
