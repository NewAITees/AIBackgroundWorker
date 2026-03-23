"""設定 API。AI接続・worker有効化・RSSフィードの読み書きを提供する。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import _CONFIG_PATH, config
from ..services.worker_control_service import worker_control_service

router = APIRouter()

_RSS_PATH = (
    Path(__file__).resolve().parents[3] / "lifelog-system/config/info_collector/rss_feeds.txt"
)
_SEARCH_QUERIES_PATH = (
    Path(__file__).resolve().parents[3] / "lifelog-system/config/info_collector/search_queries.txt"
)


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------


class AISettingsUpdate(BaseModel):
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    timeout_seconds: int | None = None
    personality: str | None = None


class WorkerStatesUpdate(BaseModel):
    workers: dict[str, bool]


class PipelineSettingsUpdate(BaseModel):
    info_limit: int | None = None
    analyze_batch_size: int | None = None
    deep_limit: int | None = None


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    return {
        "ai": {
            "ollama_base_url": config.ai.ollama_base_url,
            "ollama_model": config.ai.ollama_model,
            "timeout_seconds": config.ai.timeout_seconds,
            "personality": config.ai.personality,
        },
        "pipeline": {
            "info_limit": config.lifelog.info_limit,
            "analyze_batch_size": config.lifelog.analyze_batch_size,
            "deep_limit": config.lifelog.deep_limit,
        },
        **worker_control_service.get_all(),
        "feeds": _read_feeds(),
        "search_queries": _read_search_queries(),
    }


# ---------------------------------------------------------------------------
# PATCH /api/settings/ai
# ---------------------------------------------------------------------------


@router.patch("/settings/ai")
async def update_ai_settings(req: AISettingsUpdate) -> dict[str, Any]:
    """AI接続設定を更新して config.yaml に永続化する。"""
    if req.ollama_base_url is not None:
        config.ai.ollama_base_url = req.ollama_base_url
    if req.ollama_model is not None:
        config.ai.ollama_model = req.ollama_model
    if req.timeout_seconds is not None:
        config.ai.timeout_seconds = req.timeout_seconds
    if req.personality is not None:
        config.ai.personality = req.personality

    _save_config()
    return {
        "ollama_base_url": config.ai.ollama_base_url,
        "ollama_model": config.ai.ollama_model,
        "timeout_seconds": config.ai.timeout_seconds,
        "personality": config.ai.personality,
    }


# ---------------------------------------------------------------------------
# PATCH /api/settings/workers
# ---------------------------------------------------------------------------


@router.patch("/settings/pipeline")
async def update_pipeline_settings(req: PipelineSettingsUpdate) -> dict[str, Any]:
    """パイプライン設定を更新して config.yaml に永続化する。"""
    if req.info_limit is not None:
        config.lifelog.info_limit = req.info_limit
    if req.analyze_batch_size is not None:
        config.lifelog.analyze_batch_size = req.analyze_batch_size
    if req.deep_limit is not None:
        config.lifelog.deep_limit = req.deep_limit

    _save_config()
    return {
        "info_limit": config.lifelog.info_limit,
        "analyze_batch_size": config.lifelog.analyze_batch_size,
        "deep_limit": config.lifelog.deep_limit,
    }


@router.patch("/settings/workers")
async def update_worker_states(req: WorkerStatesUpdate) -> dict[str, Any]:
    worker_control_service.update_all(req.workers)
    return worker_control_service.get_all()


# ---------------------------------------------------------------------------
# GET /api/settings/feeds
# ---------------------------------------------------------------------------


@router.get("/settings/feeds")
async def list_feeds() -> dict[str, Any]:
    return {"feeds": _read_feeds()}


@router.get("/settings/search-queries")
async def list_search_queries() -> dict[str, Any]:
    return {"search_queries": _read_search_queries()}


# ---------------------------------------------------------------------------
# POST /api/settings/feeds
# ---------------------------------------------------------------------------


class FeedAddRequest(BaseModel):
    url: str


@router.post("/settings/feeds", status_code=201)
async def add_feed(req: FeedAddRequest) -> dict[str, Any]:
    url = req.url.strip()
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="有効な URL を入力してください")
    feeds = _read_feeds()
    if url in feeds:
        raise HTTPException(status_code=409, detail="既に登録済みです")
    feeds.append(url)
    _write_feeds(feeds)
    return {"feeds": feeds}


# ---------------------------------------------------------------------------
# DELETE /api/settings/feeds
# ---------------------------------------------------------------------------


class FeedDeleteRequest(BaseModel):
    url: str


@router.delete("/settings/feeds")
async def delete_feed(req: FeedDeleteRequest) -> dict[str, Any]:
    feeds = _read_feeds()
    updated = [f for f in feeds if f != req.url.strip()]
    if len(updated) == len(feeds):
        raise HTTPException(status_code=404, detail="フィードが見つかりません")
    _write_feeds(updated)
    return {"feeds": updated}


class SearchQueryAddRequest(BaseModel):
    query: str


@router.post("/settings/search-queries", status_code=201)
async def add_search_query(req: SearchQueryAddRequest) -> dict[str, Any]:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="検索クエリを入力してください")
    queries = _read_search_queries()
    if query in queries:
        raise HTTPException(status_code=409, detail="既に登録済みです")
    queries.append(query)
    _write_search_queries(queries)
    return {"search_queries": queries}


class SearchQueryDeleteRequest(BaseModel):
    query: str


@router.delete("/settings/search-queries")
async def delete_search_query(req: SearchQueryDeleteRequest) -> dict[str, Any]:
    queries = _read_search_queries()
    updated = [q for q in queries if q != req.query.strip()]
    if len(updated) == len(queries):
        raise HTTPException(status_code=404, detail="検索クエリが見つかりません")
    _write_search_queries(updated)
    return {"search_queries": updated}


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _read_feeds() -> list[str]:
    if not _RSS_PATH.exists():
        return []
    lines = _RSS_PATH.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _write_feeds(feeds: list[str]) -> None:
    header = "# RSSフィードURLを1行ずつ記載してください（コメント行は無視されます）\n"
    _RSS_PATH.write_text(header + "\n".join(feeds) + "\n", encoding="utf-8")


def _read_search_queries() -> list[str]:
    if not _SEARCH_QUERIES_PATH.exists():
        return []
    lines = _SEARCH_QUERIES_PATH.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _write_search_queries(queries: list[str]) -> None:
    header = "# ベースとなる検索クエリを1行ずつ記載してください（コメント行は無視されます）\n"
    _SEARCH_QUERIES_PATH.write_text(header + "\n".join(queries) + "\n", encoding="utf-8")


def _save_config() -> None:
    """現在の config オブジェクトを config.yaml に書き戻す。"""
    if not _CONFIG_PATH.exists():
        raw: dict[str, Any] = {}
    else:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    raw.setdefault("ai", {})
    raw["ai"]["ollama_base_url"] = config.ai.ollama_base_url
    raw["ai"]["ollama_model"] = config.ai.ollama_model
    raw["ai"]["timeout_seconds"] = config.ai.timeout_seconds
    raw["ai"]["personality"] = config.ai.personality

    raw.setdefault("lifelog", {})
    raw["lifelog"]["info_limit"] = config.lifelog.info_limit
    raw["lifelog"]["analyze_batch_size"] = config.lifelog.analyze_batch_size
    raw["lifelog"]["deep_limit"] = config.lifelog.deep_limit

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, sort_keys=False)
