"""ニュース記事フィードバック API。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..config import config, to_local_path

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# パス解決ヘルパー
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(raw_path: str) -> Path:
    path = Path(to_local_path(raw_path))
    if path.is_absolute():
        return path.resolve()
    return (_repo_root() / path).resolve()


def _load_repo():
    """InfoCollectorRepository を動的ロードする（lifelog-system の sys.path 操作）。"""
    import sys

    lifelog_root = str(_resolve_path(config.lifelog.root_dir))
    if lifelog_root not in sys.path:
        sys.path.insert(0, lifelog_root)

    import src as shared_src

    lifelog_src_path = str(Path(lifelog_root) / "src")
    if lifelog_src_path not in shared_src.__path__:
        shared_src.__path__.append(lifelog_src_path)

    from src.info_collector.repository import InfoCollectorRepository

    db_path = _resolve_path(config.lifelog.info_db_path)
    return InfoCollectorRepository(str(db_path))


def _load_pipeline_functions():
    from src.info_collector.jobs.analyze_pending import analyze_pending_articles
    from src.info_collector.jobs.deep_research import deep_research_articles
    from src.info_collector.jobs.generate_theme_report import generate_theme_reports

    return analyze_pending_articles, deep_research_articles, generate_theme_reports


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------

FeedbackType = Literal["positive", "negative"]


class FeedbackRequest(BaseModel):
    type: FeedbackType


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.get("/news/articles")
async def get_articles(ids: str = "") -> list[dict]:
    """
    `ids` に渡した `collected-info-{id}` 形式のカンマ区切りIDから記事詳細を返す。
    各記事にフィードバック状態（feedback_type）を付与する。
    """
    if not ids:
        return []

    article_ids: list[int] = []
    for raw in ids.split(","):
        raw = raw.strip()
        prefix = "collected-info-"
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
        try:
            article_ids.append(int(raw))
        except ValueError:
            continue

    if not article_ids:
        return []

    repo = _load_repo()
    articles = repo.get_articles_by_ids(article_ids)
    feedback_map = repo.get_feedback_map(article_ids)

    for article in articles:
        article["feedback"] = feedback_map.get(article["id"])

    return articles


@router.post("/news/articles/{article_id}/feedback")
async def post_feedback(article_id: int, body: FeedbackRequest) -> dict:
    """記事に positive / negative フィードバックを記録する。"""
    repo = _load_repo()
    repo.add_feedback(article_id, body.type)
    return {"status": "ok", "article_id": article_id, "feedback_type": body.type}


@router.post("/news/articles/{article_id}/generate_report")
async def generate_report(article_id: int, background_tasks: BackgroundTasks) -> dict:
    """
    記事を強制的にレポート生成パイプラインに通す。
    - article_feedback に report_requested を記録
    - article_analysis に importance=1.0 を設定（Stage1 閾値を通過させる）
    - バックグラウンドで Stage2（深掘り）+ Stage3（レポート生成）を実行
    """
    repo = _load_repo()
    repo.add_feedback(article_id, "report_requested")
    repo.force_article_for_research(article_id)

    background_tasks.add_task(_run_pipeline_for_article, article_id)

    return {"status": "queued", "article_id": article_id}


def _run_pipeline_for_article(article_id: int) -> None:
    """Stage2+Stage3 をバックグラウンドで実行する。"""
    db_path = _resolve_path(config.lifelog.info_db_path)
    output_dir = _resolve_path(config.lifelog.report_output_dir)

    # lifelog-system のパイプライン関数をロード
    _load_repo()  # sys.path を通す
    _, deep_research_articles, generate_theme_reports = _load_pipeline_functions()

    previous_env = {
        "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL"),
        "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL"),
        "OLLAMA_TIMEOUT": os.environ.get("OLLAMA_TIMEOUT"),
        "YELLOWMABLE_DIR": os.environ.get("YELLOWMABLE_DIR"),
    }
    os.environ["OLLAMA_BASE_URL"] = config.ai.ollama_base_url
    os.environ["OLLAMA_MODEL"] = config.ai.ollama_model
    os.environ["OLLAMA_TIMEOUT"] = str(config.ai.timeout_seconds)
    os.environ["YELLOWMABLE_DIR"] = str(output_dir.parent)

    try:
        # force_article_for_research で importance=1.0 にしてあるので
        # min_importance=0.0 で確実にこの記事が Stage2 対象になる
        deep_research_articles(
            db_path=db_path,
            batch_size=1,
            min_importance=0.0,
            min_relevance=0.0,
        )
        generate_theme_reports(
            db_path=db_path,
            output_dir=output_dir,
            min_articles=1,
            skip_existing=False,
        )
        logger.info("Report generation completed for article_id=%d", article_id)
    except Exception:
        logger.exception("Report generation failed for article_id=%d", article_id)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
