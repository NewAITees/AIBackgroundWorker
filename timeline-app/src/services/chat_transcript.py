"""chat entry の Markdown transcript 整形と解析。"""

from __future__ import annotations

import re

_MARKER_RE = re.compile(
    r"<!--\s*chat-message:(?P<role>user|assistant)\s*-->\s*\n(?P<body>.*?)(?=(?:\n<!--\s*chat-message:)|\Z)",
    flags=re.DOTALL,
)


def build_chat_message_block(role: str, content: str) -> str:
    normalized_role = "assistant" if role == "assistant" else "user"
    heading = "Assistant" if normalized_role == "assistant" else "User"
    body = content.rstrip()
    return f"<!-- chat-message:{normalized_role} -->\n### {heading}\n\n{body}\n"


def build_chat_transcript(messages: list[dict[str, str]]) -> str:
    blocks = [
        build_chat_message_block(
            str(message.get("role", "user")), str(message.get("content", "")).strip()
        )
        for message in messages
        if str(message.get("content", "")).strip()
    ]
    return "\n".join(blocks).rstrip()


def append_chat_message(content: str, role: str, message: str) -> str:
    existing = content.rstrip()
    block = build_chat_message_block(role, message)
    if not existing:
        return block.rstrip()
    return f"{existing}\n\n{block}".rstrip()


def parse_chat_transcript(content: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for match in _MARKER_RE.finditer(content or ""):
        body = match.group("body").strip()
        if not body:
            continue
        body = re.sub(r"^###\s+(?:User|Assistant)\s*\n+", "", body, count=1)
        messages.append({"role": match.group("role"), "content": body.strip()})
    return messages
