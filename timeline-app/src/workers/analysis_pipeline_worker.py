"""旧 info-integrated.timer の analyze/deep/theme-report を置き換える worker。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any

from ..config import config, to_local_path
from ..services.ai_control import ai_control_service


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _lifelog_root() -> Path:
    path = Path(to_local_path(config.lifelog.root_dir))
    if path.is_absolute():
        return path.resolve()
    return (_repo_root() / path).resolve()


def _resolve_path(raw_path: str) -> Path:
    path = Path(to_local_path(raw_path))
    if path.is_absolute():
        return path.resolve()
    return (_repo_root() / path).resolve()


def _load_pipeline_functions():
    import sys

    root_path = str(_lifelog_root())
    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    from src.info_collector.jobs.analyze_pending import analyze_pending_articles
    from src.info_collector.jobs.deep_research import deep_research_articles
    from src.info_collector.jobs.generate_theme_report import generate_theme_reports

    return analyze_pending_articles, deep_research_articles, generate_theme_reports


@dataclass
class AnalysisPipelineWorkerStatus:
    running: bool = False
    db_path: str | None = None
    report_output_dir: str | None = None
    last_analyzed: int = 0
    last_deep_researched: int = 0
    last_reports_generated: int = 0
    last_run_at: str | None = None
    last_error: str | None = None


class AnalysisPipelineWorker:
    def __init__(self) -> None:
        self._status = AnalysisPipelineWorkerStatus()
        self._lock = asyncio.Lock()

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._status.running,
            "db_path": self._status.db_path,
            "report_output_dir": self._status.report_output_dir,
            "last_analyzed": self._status.last_analyzed,
            "last_deep_researched": self._status.last_deep_researched,
            "last_reports_generated": self._status.last_reports_generated,
            "last_run_at": self._status.last_run_at,
            "last_error": self._status.last_error,
        }

    async def sync_once(self) -> int:
        async with self._lock:
            self._status.running = True
            try:
                return await asyncio.to_thread(self._sync_once_blocking)
            finally:
                self._status.running = False

    def _sync_once_blocking(self) -> int:
        self._status.last_error = None
        self._status.last_analyzed = 0
        self._status.last_deep_researched = 0
        self._status.last_reports_generated = 0

        if ai_control_service.is_paused():
            return 0

        db_path = _resolve_path(config.lifelog.info_db_path)
        output_dir = _resolve_path(config.lifelog.report_output_dir)
        self._status.db_path = str(db_path)
        self._status.report_output_dir = str(output_dir)

        (
            analyze_pending_articles,
            deep_research_articles,
            generate_theme_reports,
        ) = _load_pipeline_functions()

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
            analyzed = analyze_pending_articles(
                db_path=db_path,
                batch_size=config.lifelog.analyze_batch_size,
            )
            deep = deep_research_articles(
                db_path=db_path,
                batch_size=config.lifelog.deep_batch_size,
                min_importance=config.lifelog.deep_min_importance,
                min_relevance=config.lifelog.deep_min_relevance,
            )
            reports = generate_theme_reports(
                db_path=db_path,
                output_dir=output_dir,
                min_articles=config.lifelog.theme_min_articles,
                skip_existing=config.lifelog.theme_skip_existing,
            )
        except Exception as exc:  # noqa: BLE001
            self._status.last_error = str(exc)
            raise
        finally:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self._status.last_analyzed = int(analyzed)
        self._status.last_deep_researched = int(deep)
        self._status.last_reports_generated = len(reports)
        self._status.last_run_at = datetime.now(UTC).isoformat()
        return int(analyzed) + int(deep) + len(reports)


analysis_pipeline_worker = AnalysisPipelineWorker()
