"""Create OpenAI chat clients with model-compatible parameters."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from src.monitoring.openai_client import build_instrumented_http_client


def create_chat_model(
    model: str,
    api_key: str,
    *,
    max_tokens: int | None = None,
    instrumented: bool = True,
) -> ChatOpenAI:
    """Use deterministic settings without sending unsupported parameters."""
    options = {"model": model, "api_key": api_key}
    if model == "gpt-6-luna":
        options["reasoning_effort"] = "none"
    else:
        options["temperature"] = 0
    if max_tokens is not None:
        options["max_tokens"] = max_tokens
    if instrumented:
        options["http_client"] = build_instrumented_http_client()
    return ChatOpenAI(**options)
