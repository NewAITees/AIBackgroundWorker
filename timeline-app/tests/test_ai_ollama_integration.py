"""
OllamaClient 統合テスト

Ollama が実際に起動している環境でのみ実行する。
通常の pytest では自動的に skip される。

実行方法:
  uv run pytest -m integration -v
"""

import pytest

from src.ai.ollama_client import OllamaClient
from src.config import AIConfig


@pytest.fixture()
def client() -> OllamaClient:
    return OllamaClient(
        AIConfig(
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="qwen2.5:7b",
            timeout_seconds=60,
        )
    )


@pytest.mark.integration
class TestOllamaClientIntegration:
    def test_basic_reply_is_returned(self, client: OllamaClient):
        """Ollama が返す reply が空でないこと。"""
        result = client.generate_chat_reply([{"role": "user", "content": "こんにちは"}])
        assert result.reply
        assert isinstance(result.reply, str)

    def test_reply_is_japanese(self, client: OllamaClient):
        """日本語プロンプトに対して日本語で返答すること（ASCII のみでないこと）。"""
        result = client.generate_chat_reply([{"role": "user", "content": "今日の気分を一言で教えて"}])
        assert any(ord(c) > 127 for c in result.reply), "日本語文字が含まれていない"

    def test_todo_candidate_inferred(self, client: OllamaClient):
        """締切付きタスクへの言及から todo 候補が推定されること。"""
        result = client.generate_chat_reply(
            [{"role": "user", "content": "明日までにA社へ見積もりを返信しないといけない"}]
        )
        types = [c["type"] for c in result.entry_candidates]
        assert "todo" in types, f"todo が推定されなかった。candidates={result.entry_candidates}"

    def test_diary_candidate_inferred(self, client: OllamaClient):
        """感情・出来事への言及から diary または event 候補が推定されること。"""
        result = client.generate_chat_reply([{"role": "user", "content": "今日は久しぶりに友人と会えてとても嬉しかった"}])
        types = [c["type"] for c in result.entry_candidates]
        assert any(
            t in types for t in ("diary", "event")
        ), f"diary/event が推定されなかった。candidates={result.entry_candidates}"

    def test_candidates_have_required_fields(self, client: OllamaClient):
        """返ってきた candidates が type と content を持つこと。"""
        result = client.generate_chat_reply([{"role": "user", "content": "来週月曜に歯医者の予約がある"}])
        for c in result.entry_candidates:
            assert "type" in c, f"type がない: {c}"
            assert "content" in c, f"content がない: {c}"
            assert c["type"] in ("diary", "event", "todo", "memo"), f"不正な type: {c['type']}"

    def test_multi_turn_conversation(self, client: OllamaClient):
        """複数ターンの会話で文脈を引き継いで返答すること。"""
        history = [
            {"role": "user", "content": "プロジェクトXの締め切りは来週金曜だ"},
            {"role": "assistant", "content": "承知しました。来週金曜が締め切りですね。"},
            {"role": "user", "content": "そのためにやることを整理したい"},
        ]
        result = client.generate_chat_reply(history)
        assert result.reply
        # プロジェクトXか締め切りに関連した文脈が返ること（緩い確認）
        assert len(result.reply) > 5
