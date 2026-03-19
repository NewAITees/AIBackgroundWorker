"""analysis_pipeline_worker の単体テスト。"""

from __future__ import annotations

import os

from src.config import config
from src.workers.analysis_pipeline_worker import AnalysisPipelineWorker


def test_sync_once_blocking_skips_when_ai_paused(monkeypatch):
    worker = AnalysisPipelineWorker()

    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker.ai_control_service.is_paused",
        lambda: True,
    )

    called = {"loaded": False}

    def _unexpected_load():
        called["loaded"] = True
        raise AssertionError("paused 中に pipeline を読み込んではいけない")

    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker._load_pipeline_functions", _unexpected_load
    )

    assert worker._sync_once_blocking() == 0
    assert worker.get_status()["last_analyzed"] == 0
    assert called["loaded"] is False


def test_sync_once_blocking_runs_pipeline_and_updates_status(monkeypatch, tmp_path):
    worker = AnalysisPipelineWorker()

    db_path = tmp_path / "ai_secretary.db"
    output_dir = tmp_path / "00_Raw"
    output_dir.mkdir()

    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker.ai_control_service.is_paused",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker._resolve_path",
        lambda raw_path: db_path if "ai_secretary.db" in raw_path else output_dir,
    )

    monkeypatch.setattr(config.ai, "ollama_base_url", "http://127.0.0.1:11436")
    monkeypatch.setattr(config.ai, "ollama_model", "qwen3.5:9b")
    monkeypatch.setattr(config.ai, "timeout_seconds", 77)
    monkeypatch.setattr(config.lifelog, "analyze_batch_size", 12)
    monkeypatch.setattr(config.lifelog, "deep_batch_size", 4)
    monkeypatch.setattr(config.lifelog, "deep_min_importance", 0.55)
    monkeypatch.setattr(config.lifelog, "deep_min_relevance", 0.65)
    monkeypatch.setattr(config.lifelog, "theme_min_articles", 2)
    monkeypatch.setattr(config.lifelog, "theme_skip_existing", False)

    calls: dict[str, object] = {}

    def _analyze_pending_articles(*, db_path, batch_size):
        calls["analyze"] = {"db_path": db_path, "batch_size": batch_size}
        assert os.environ["OLLAMA_BASE_URL"] == "http://127.0.0.1:11436"
        assert os.environ["OLLAMA_MODEL"] == "qwen3.5:9b"
        assert os.environ["OLLAMA_TIMEOUT"] == "77"
        return 3

    def _deep_research_articles(*, db_path, batch_size, min_importance, min_relevance):
        calls["deep"] = {
            "db_path": db_path,
            "batch_size": batch_size,
            "min_importance": min_importance,
            "min_relevance": min_relevance,
        }
        return 2

    def _generate_theme_reports(*, db_path, output_dir, min_articles, skip_existing):
        calls["report"] = {
            "db_path": db_path,
            "output_dir": output_dir,
            "min_articles": min_articles,
            "skip_existing": skip_existing,
        }
        return [output_dir / "r1.md", output_dir / "r2.md"]

    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker._load_pipeline_functions",
        lambda: (_analyze_pending_articles, _deep_research_articles, _generate_theme_reports),
    )

    old_base_url = os.environ.get("OLLAMA_BASE_URL")
    old_model = os.environ.get("OLLAMA_MODEL")
    old_timeout = os.environ.get("OLLAMA_TIMEOUT")
    old_yellowmable = os.environ.get("YELLOWMABLE_DIR")

    result = worker._sync_once_blocking()

    assert result == 7
    status = worker.get_status()
    assert status["db_path"] == str(db_path)
    assert status["report_output_dir"] == str(output_dir)
    assert status["last_analyzed"] == 3
    assert status["last_deep_researched"] == 2
    assert status["last_reports_generated"] == 2
    assert status["last_run_at"] is not None
    assert status["last_error"] is None

    assert calls["analyze"] == {"db_path": db_path, "batch_size": 12}
    assert calls["deep"] == {
        "db_path": db_path,
        "batch_size": 4,
        "min_importance": 0.55,
        "min_relevance": 0.65,
    }
    assert calls["report"] == {
        "db_path": db_path,
        "output_dir": output_dir,
        "min_articles": 2,
        "skip_existing": False,
    }

    assert os.environ.get("OLLAMA_BASE_URL") == old_base_url
    assert os.environ.get("OLLAMA_MODEL") == old_model
    assert os.environ.get("OLLAMA_TIMEOUT") == old_timeout
    assert os.environ.get("YELLOWMABLE_DIR") == old_yellowmable


def test_sync_once_blocking_records_error_and_reraises(monkeypatch, tmp_path):
    worker = AnalysisPipelineWorker()

    db_path = tmp_path / "ai_secretary.db"
    output_dir = tmp_path / "00_Raw"
    output_dir.mkdir()

    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker.ai_control_service.is_paused",
        lambda: False,
    )
    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker._resolve_path",
        lambda raw_path: db_path if "ai_secretary.db" in raw_path else output_dir,
    )

    def _boom(*, db_path, batch_size):
        raise RuntimeError("analysis failed")

    monkeypatch.setattr(
        "src.workers.analysis_pipeline_worker._load_pipeline_functions",
        lambda: (_boom, lambda **_: 0, lambda **_: []),
    )

    try:
        worker._sync_once_blocking()
        raise AssertionError("例外が再送出されるべき")
    except RuntimeError as exc:
        assert str(exc) == "analysis failed"

    status = worker.get_status()
    assert status["last_error"] == "analysis failed"
    assert status["last_analyzed"] == 0
    assert status["last_deep_researched"] == 0
    assert status["last_reports_generated"] == 0
