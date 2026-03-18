"""OllamaClient のユニットテスト（requests をモック）"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ai.ollama_client import OllamaClient, OllamaClientError
from src.config import AIConfig


def make_client(**kwargs) -> OllamaClient:
    settings = AIConfig(
        ollama_base_url="http://localhost:11434",
        ollama_model="test-model",
        timeout_seconds=10,
        **kwargs,
    )
    return OllamaClient(settings)


def mock_response(body: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"response": json.dumps(body)}
    return resp


class TestGenerateChatReply:
    def test_returns_reply_and_candidates(self):
        client = make_client()
        messages = [{"role": "user", "content": "今日は病院に行った"}]
        body = {
            "reply": "お疲れ様でした。",
            "entry_candidates": [{"type": "event", "title": "病院受診", "content": "病院に行った"}],
        }
        with patch("requests.post", return_value=mock_response(body)):
            result = client.generate_chat_reply(messages)

        assert result.reply == "お疲れ様でした。"
        assert len(result.entry_candidates) == 1
        assert result.entry_candidates[0]["type"] == "event"

    def test_empty_candidates_ok(self):
        client = make_client()
        body = {"reply": "了解です。", "entry_candidates": []}
        with patch("requests.post", return_value=mock_response(body)):
            result = client.generate_chat_reply([{"role": "user", "content": "こんにちは"}])
        assert result.reply == "了解です。"
        assert result.entry_candidates == []

    def test_missing_candidates_key_defaults_to_empty(self):
        client = make_client()
        body = {"reply": "はい。"}
        with patch("requests.post", return_value=mock_response(body)):
            result = client.generate_chat_reply([{"role": "user", "content": "x"}])
        assert result.entry_candidates == []

    def test_non_dict_candidate_is_ignored(self):
        client = make_client()
        body = {"reply": "はい。", "entry_candidates": ["invalid", None, 42]}
        with patch("requests.post", return_value=mock_response(body)):
            result = client.generate_chat_reply([{"role": "user", "content": "x"}])
        assert result.entry_candidates == []

    def test_connection_error_raises_client_error(self):
        import requests as req

        client = make_client()
        with patch("requests.post", side_effect=req.RequestException("timeout")):
            with pytest.raises(OllamaClientError, match="Ollama への接続に失敗"):
                client.generate_chat_reply([{"role": "user", "content": "x"}])

    def test_invalid_json_response_raises_client_error(self):
        client = make_client()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"response": "これはJSONではない"}
        with patch("requests.post", return_value=resp):
            with pytest.raises(OllamaClientError, match="JSON 解析に失敗"):
                client.generate_chat_reply([{"role": "user", "content": "x"}])

    def test_empty_reply_raises_client_error(self):
        client = make_client()
        body = {"reply": "", "entry_candidates": []}
        with patch("requests.post", return_value=mock_response(body)):
            with pytest.raises(OllamaClientError, match="reply がありません"):
                client.generate_chat_reply([{"role": "user", "content": "x"}])

    def test_history_is_truncated_to_12_messages(self):
        client = make_client()
        messages = [{"role": "user", "content": str(i)} for i in range(20)]
        body = {"reply": "ok", "entry_candidates": []}
        captured = {}

        def capture(url, json, timeout):  # noqa: A002
            captured["payload"] = json
            return mock_response(body)

        with patch("requests.post", side_effect=capture):
            client.generate_chat_reply(messages)

        # プロンプト内に最大12件分のメッセージが含まれる
        prompt = captured["payload"]["prompt"]
        # 最後の12件のみ使われるので、先頭のメッセージは含まれない
        assert "user: 0" not in prompt
        assert "user: 19" in prompt

    def test_prompt_contains_json_format_instruction(self):
        client = make_client()
        body = {"reply": "ok", "entry_candidates": []}
        captured = {}

        def capture(url, json, timeout):  # noqa: A002
            captured["payload"] = json
            return mock_response(body)

        with patch("requests.post", side_effect=capture):
            client.generate_chat_reply([{"role": "user", "content": "test"}])

        assert "JSON" in captured["payload"]["prompt"]
        assert captured["payload"]["format"] == "json"
