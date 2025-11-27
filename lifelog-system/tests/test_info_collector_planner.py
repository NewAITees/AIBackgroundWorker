import tempfile
from pathlib import Path

from src.info_collector.repository import InfoCollectorRepository
from src.info_collector.search_planner import OllamaSearchPlanner


class _FailingClient:
    def generate(self, *args, **kwargs):
        raise RuntimeError("no ollama")


def test_plan_queries_without_ollama_uses_fallback(tmp_path: Path):
    interests_file = tmp_path / "interests.txt"
    interests_file.write_text("foo topic\n", encoding="utf-8")

    repo = InfoCollectorRepository(db_path=str(tmp_path / "info.db"))
    planner = OllamaSearchPlanner(
        repository=repo,
        interests_path=interests_file,
        base_queries=["base search"],
    )

    queries = planner.plan_queries(use_ollama=False, limit=5)

    # Interests and base queries should appear
    assert "foo topic" in queries
    assert "base search" in queries
    assert len(queries) <= 5


def test_plan_queries_falls_back_when_ollama_fails(tmp_path: Path):
    interests_file = tmp_path / "interests.txt"
    interests_file.write_text("fallback interest\n", encoding="utf-8")

    repo = InfoCollectorRepository(db_path=str(tmp_path / "info.db"))
    planner = OllamaSearchPlanner(
        repository=repo,
        interests_path=interests_file,
        base_queries=["base query"],
        ollama_client=_FailingClient(),  # force failure
    )

    queries = planner.plan_queries(use_ollama=True, limit=3)

    # Should still return non-empty fallback queries
    assert queries
    assert "fallback interest" in queries or "base query" in queries
    assert len(queries) <= 3
