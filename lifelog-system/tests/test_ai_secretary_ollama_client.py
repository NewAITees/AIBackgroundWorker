import json
from unittest.mock import MagicMock, patch

from src.ai_secretary.ollama_client import OllamaClient


def test_generate_logs_model_and_env_caller(monkeypatch):
    monkeypatch.setenv("TIMELINE_LLM_CALLER", "analysis_pipeline_worker")
    monkeypatch.setenv("TIMELINE_LLM_PURPOSE", "info_pipeline")

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_lines.return_value = [
        json.dumps({"response": "hello", "done": False}),
        json.dumps({"done": True}),
    ]

    client = OllamaClient(base_url="http://localhost:11434", model="test-model", timeout=5)
    with (
        patch("src.ai_secretary.ollama_client.requests.post", return_value=response),
        patch("src.ai_secretary.ollama_client.server_logger.info") as log_info,
    ):
        result = client.generate("test prompt")

    assert result == "hello"
    assert log_info.called
    message, payload = log_info.call_args[0]
    assert message == "llm_call %s"
    assert '"caller": "analysis_pipeline_worker"' in payload
    assert '"purpose": "info_pipeline"' in payload
    assert '"model": "test-model"' in payload
