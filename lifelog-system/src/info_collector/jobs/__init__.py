"""Batch jobs for info collector (analysis, deep research, reports)."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["analyze_pending_articles", "deep_research_articles", "generate_daily_report"]

_EXPORT_MAP = {
    "analyze_pending_articles": ("src.info_collector.jobs.analyze_pending", "analyze_pending_articles"),
    "deep_research_articles": ("src.info_collector.jobs.deep_research", "deep_research_articles"),
    "generate_daily_report": ("src.info_collector.jobs.generate_report", "generate_daily_report"),
}


def __getattr__(name: str) -> Any:
    """Lazily resolve exported callables to avoid eager submodule imports."""
    target = _EXPORT_MAP.get(name)
    if not target:
        raise AttributeError(name)
    module_name, attr_name = target
    module = import_module(module_name)
    return getattr(module, attr_name)
