"""Pure transformations for session data returned by the session API."""

from __future__ import annotations

from typing import Any

DEFAULT_SESSION_TITLE = "Sesi Tanpa Judul"
SESSION_TITLE_LIMIT = 40


def build_session_title(turns: list[dict[str, Any]]) -> str:
    """Create a short session title from the first user message."""
    first_question = next(
        (
            str(turn.get("content", "")).strip()
            for turn in turns
            if turn.get("role") == "user"
        ),
        "",
    )
    if not first_question:
        return DEFAULT_SESSION_TITLE
    if len(first_question) <= SESSION_TITLE_LIMIT:
        return first_question
    return f"{first_question[:SESSION_TITLE_LIMIT]}..."


def serialize_messages(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert stored turns to the stable message shape used by the frontend."""
    return [
        {
            "role": "bot" if turn.get("role") == "assistant" else turn.get("role"),
            "text": turn.get("content", ""),
            "sources": turn.get("sources", turn.get("retrieved_doc_contents", [])),
        }
        for turn in turns
    ]
