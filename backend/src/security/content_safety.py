"""Safe handling for user-controlled and retrieved text."""

from __future__ import annotations

import re

from config.settings import get_settings

_SUSPICIOUS_INSTRUCTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions?",
        r"abaikan\s+(semua\s+)?instruksi\s+(sebelumnya|di atas)",
        r"(reveal|show|print|tampilkan)\s+(the\s+)?system\s+prompt",
        r"you\s+are\s+now\s+",
        r"developer\s+message\s*:",
        r"system\s+message\s*:",
    )
)


def contains_suspicious_instruction(text: str) -> bool:
    """Flag common instruction-override patterns without blocking normal text."""
    return any(pattern.search(text) for pattern in _SUSPICIOUS_INSTRUCTION_PATTERNS)


def isolate_untrusted_text(text: str) -> str:
    """Prevent retrieved text from closing the prompt's document boundary."""
    return (
        text.replace("<UNTRUSTED_DOCUMENT", "&lt;UNTRUSTED_DOCUMENT")
        .replace("</UNTRUSTED_DOCUMENT>", "&lt;/UNTRUSTED_DOCUMENT&gt;")
        .replace("<END_UNTRUSTED_CONTEXT>", "&lt;END_UNTRUSTED_CONTEXT&gt;")
    )


def text_for_log(text: str, preview_length: int = 120) -> str:
    """Keep production logs useful without storing message content."""
    settings = get_settings()
    if settings.is_production():
        return f"[redacted length={len(text)}]"
    normalized = " ".join(text.split())
    return normalized[:preview_length]
