"""OllamaClient のユニットテスト（requests をモック）"""

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


def mock_tool_response(reply: str, candidates: list[dict] | None = None) -> MagicMock:
    """tool_calls 形式のモックレスポンスを返す。"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "save_entry_candidates",
                        "arguments": {
                            "reply": reply,
                            "entry_candidates": candidates or [],
                        },
                    }
                }
            ],
        },
        "done": True,
    }
    return resp


def mock_plain_response(content: str) -> MagicMock:
    """tool_calls なしの通常テキスト応答モック（フォールバック用）。"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "message": {"role": "assistant", "content": content, "tool_calls": []},
        "done": True,
    }
    return resp


class TestGenerateChatReply:
    def test_returns_reply_and_candidates(self):
        client = make_client()
        messages = [{"role": "user", "content": "今日は病院に行った"}]
        with patch(
            "requests.post",
            return_value=mock_tool_response(
                "お疲れ様でした。",
                [{"type": "event", "title": "病院受診", "content": "病院に行った"}],
            ),
        ):
            result = client.generate_chat_reply(messages)

        assert result.reply == "お疲れ様でした。"
        assert len(result.entry_candidates) == 1
        assert result.entry_candidates[0]["type"] == "event"

    def test_empty_candidates_ok(self):
        client = make_client()
        with patch("requests.post", return_value=mock_tool_response("了解です。", [])):
            result = client.generate_chat_reply([{"role": "user", "content": "こんにちは"}])
        assert result.reply == "了解です。"
        assert result.entry_candidates == []

    def test_fallback_to_content_when_no_tool_calls(self):
        client = make_client()
        with patch("requests.post", return_value=mock_plain_response("テキスト応答です。")):
            result = client.generate_chat_reply([{"role": "user", "content": "x"}])
        assert result.reply == "テキスト応答です。"
        assert result.entry_candidates == []

    def test_non_dict_candidate_is_ignored(self):
        client = make_client()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "save_entry_candidates",
                            "arguments": {
                                "reply": "はい。",
                                "entry_candidates": ["invalid", None, 42],
                            },
                        }
                    }
                ],
            }
        }
        with patch("requests.post", return_value=resp):
            result = client.generate_chat_reply([{"role": "user", "content": "x"}])
        assert result.entry_candidates == []

    def test_connection_error_raises_client_error(self):
        import requests as req

        client = make_client()
        with patch("requests.post", side_effect=req.RequestException("timeout")):
            with pytest.raises(OllamaClientError, match="Ollama への接続に失敗"):
                client.generate_chat_reply([{"role": "user", "content": "x"}])

    def test_empty_reply_raises_client_error(self):
        client = make_client()
        with patch("requests.post", return_value=mock_tool_response("", [])):
            with pytest.raises(OllamaClientError, match="reply がありません"):
                client.generate_chat_reply([{"role": "user", "content": "x"}])

    def test_history_is_truncated_to_12_messages(self):
        client = make_client()
        messages = [{"role": "user", "content": str(i)} for i in range(20)]
        captured = {}

        def capture(url, json, timeout):  # noqa: A002
            captured["payload"] = json
            return mock_tool_response("ok")

        with patch("requests.post", side_effect=capture):
            client.generate_chat_reply(messages)

        sent_messages = captured["payload"]["messages"]
        # system メッセージ 1 件 + 会話 12 件 = 13 件
        assert len(sent_messages) == 13
        assert sent_messages[0]["role"] == "system"
        assert sent_messages[1]["content"] == "8"
        assert sent_messages[-1]["content"] == "19"

    def test_tools_parameter_is_sent(self):
        client = make_client()
        captured = {}

        def capture(url, json, timeout):  # noqa: A002
            captured["payload"] = json
            return mock_tool_response("ok")

        with patch("requests.post", side_effect=capture):
            client.generate_chat_reply([{"role": "user", "content": "test"}])

        assert "tools" in captured["payload"]
        assert captured["payload"]["tools"][0]["function"]["name"] == "save_entry_candidates"

    def test_logs_model_and_caller(self):
        client = make_client()
        with (
            patch("requests.post", return_value=mock_tool_response("了解です。")),
            patch("src.ai.ollama_client.logger.info") as log_info,
        ):
            client.generate_chat_reply(
                [{"role": "user", "content": "今日やること"}],
                caller="chat_api",
                context={"thread_id": "thread-123"},
            )

        assert log_info.called
        message, payload = log_info.call_args[0]
        assert message == "llm_call %s"
        assert '"caller": "chat_api"' in payload
        assert '"model": "test-model"' in payload
        assert '"thread_id": "thread-123"' in payload

    def test_logs_direct_chat_with_tools_call(self):
        client = make_client()
        with (
            patch("requests.post", return_value=mock_tool_response("了解です。")),
            patch("src.ai.ollama_client.logger.info") as log_info,
        ):
            client._chat_with_tools(
                [{"role": "user", "content": "x"}],
                [
                    {
                        "type": "function",
                        "function": {"name": "dummy", "parameters": {"type": "object"}},
                    }
                ],
                caller="daily_digest_worker",
                purpose="daily_digest",
                context={"target_date": "2026-03-18"},
            )

        assert log_info.called
        _, payload = log_info.call_args[0]
        assert '"caller": "daily_digest_worker"' in payload
        assert '"purpose": "daily_digest"' in payload
        assert '"target_date": "2026-03-18"' in payload


class TestCheckHealth:
    def _tags_response(self, model_names: list[str]) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"models": [{"name": n} for n in model_names]}
        return resp

    def test_reachable_model_available(self):
        client = make_client()
        with patch("requests.get", return_value=self._tags_response(["test-model", "other"])):
            result = client.check_health()
        assert result["reachable"] is True
        assert result["model_available"] is True
        assert result["model"] == "test-model"

    def test_reachable_model_not_available(self):
        client = make_client()
        with patch("requests.get", return_value=self._tags_response(["other-model"])):
            result = client.check_health()
        assert result["reachable"] is True
        assert result["model_available"] is False

    def test_unreachable_returns_reachable_false(self):
        import requests as req

        client = make_client()
        with patch("requests.get", side_effect=req.RequestException("connection refused")):
            result = client.check_health()
        assert result["reachable"] is False
        assert "detail" in result
