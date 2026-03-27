"""ニュース記事フィードバック API。"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ..config import config, to_local_path
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from ..routers.workspace import resolve_workspace_path
from ..storage.persistence import persist_entry

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


def _feedback_payload(state: dict | None) -> dict:
    state = state or {}
    return {
        "sentiment": state.get("sentiment"),
        "report_status": state.get("report_status", "none"),
        "report_entry_id": state.get("report_entry_id"),
    }


def _analysis_payload(state: dict | None) -> dict | None:
    if not state:
        return None
    return {
        "category": state.get("category"),
        "importance_score": state.get("importance_score"),
        "relevance_score": state.get("relevance_score"),
        "llm_importance_score": state.get("llm_importance_score"),
        "llm_relevance_score": state.get("llm_relevance_score"),
        "source_bonus": state.get("source_bonus", 0.0),
        "category_bonus": state.get("category_bonus", 0.0),
        "total_bonus": state.get("total_bonus", 0.0),
        "importance_reason": state.get("importance_reason", ""),
        "relevance_reason": state.get("relevance_reason", ""),
    }


def _persist_report_entries(report_rows: list[dict]) -> list[str]:
    workspace_path = resolve_workspace_path()
    if not workspace_path:
        logger.warning("workspace 未設定のため report entry の timeline 反映をスキップ")
        return []

    entry_ids: list[str] = []
    for report in report_rows:
        body = str(report.get("content") or "").strip()
        if not body:
            continue
        created_at = datetime.fromisoformat(str(report["created_at"]))
        if created_at.tzinfo is None:
            created_at = created_at.astimezone(UTC)
        else:
            created_at = created_at.astimezone(UTC)
        entry_id = f"report-{report['id']}"
        persist_entry(
            workspace_path,
            Entry(
                id=entry_id,
                type=EntryType.news,
                title=str(report.get("title") or "レポート")[:120],
                summary=f"{str(report.get('category') or 'report').strip()} レポート",
                content=body,
                timestamp=created_at,
                status=EntryStatus.active,
                source=EntrySource.imported,
                workspace_path=workspace_path,
                meta=EntryMeta(source_path="lifelog-system/data/ai_secretary.db"),
            ),
        )
        entry_ids.append(entry_id)
    return entry_ids


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.get("/news/articles")
async def get_articles(ids: str = "") -> list[dict]:
    """
    `ids` に渡した `collected-info-{id}` 形式のカンマ区切りIDから記事詳細を返す。
    各記事にフィードバック状態を付与する。
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
    feedback_map = repo.get_feedback_state_map(article_ids)
    analysis_map = repo.get_article_analysis_map(article_ids)

    for article in articles:
        article["feedback"] = _feedback_payload(feedback_map.get(article["id"]))
        article["analysis"] = _analysis_payload(analysis_map.get(article["id"]))

    return articles


@router.post("/news/articles/{article_id}/feedback")
async def post_feedback(article_id: int, body: FeedbackRequest) -> dict:
    """記事に positive / negative フィードバックを排他的トグルで記録する。"""
    repo = _load_repo()
    state = repo.toggle_feedback(article_id, body.type)
    return {"status": "ok", "article_id": article_id, "feedback": _feedback_payload(state)}


@router.get("/news/feedback/stats")
async def get_feedback_stats() -> dict:
    """source/category ごとの時間減衰つきフィードバック統計を返す。"""
    repo = _load_repo()
    return repo.get_feedback_stats()


@router.get("/news/feedback/progress")
async def get_feedback_progress(limit: int = 10) -> dict:
    """学習の進み具合を件数サマリと最近のイベント付きで返す。"""
    repo = _load_repo()
    safe_limit = max(1, min(limit, 50))
    return repo.get_feedback_progress(recent_limit=safe_limit)


@router.post("/news/articles/{article_id}/generate_report")
async def generate_report(article_id: int, background_tasks: BackgroundTasks) -> dict:
    """
    記事を強制的にレポート生成パイプラインに通す。
    - sentiment=positive / report_status=requested を記録
    - requested/running/done は多重実行しない
    - article_analysis に importance=1.0 を設定（Stage1 閾値を通過させる）
    - バックグラウンドで Stage2（深掘り）+ Stage3（レポート生成）を実行
    """
    repo = _load_repo()
    queued, state = repo.request_report(article_id)
    if not queued:
        return {
            "status": "already_requested",
            "article_id": article_id,
            "feedback": _feedback_payload(state),
        }

    repo.force_article_for_research(article_id)
    last_report_id = repo.get_latest_report_id()

    background_tasks.add_task(_run_pipeline_for_article, article_id, last_report_id)

    return {"status": "queued", "article_id": article_id, "feedback": _feedback_payload(state)}


def _run_pipeline_for_article(article_id: int, last_report_id: int) -> None:
    """Stage2+Stage3 をバックグラウンドで実行する。"""
    db_path = _resolve_path(config.lifelog.info_db_path)
    output_dir = _resolve_path(config.lifelog.report_output_dir)

    # lifelog-system のパイプライン関数をロード
    repo = _load_repo()  # sys.path を通す
    repo.mark_report_running(article_id)
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
        new_reports = repo.get_reports_after_id(last_report_id)
        entry_ids = _persist_report_entries(new_reports)
        repo.mark_report_done(article_id, entry_ids[0] if entry_ids else None)
        logger.info("Report generation completed for article_id=%d", article_id)
    except Exception:
        repo.mark_report_failed(article_id)
        logger.exception("Report generation failed for article_id=%d", article_id)
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
