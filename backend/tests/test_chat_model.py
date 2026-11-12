"""Model-specific OpenAI settings must remain compatible with the API."""

from src.services import chat_model


def test_luna_omits_temperature_and_disables_reasoning(monkeypatch):
    calls = []
    monkeypatch.setattr(chat_model, "ChatOpenAI", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(
        chat_model, "build_instrumented_http_client", lambda: "instrumented-client"
    )

    chat_model.create_chat_model("gpt-6-luna", "test-key", max_tokens=200)

    assert calls == [{
        "model": "gpt-6-luna",
        "api_key": "test-key",
        "reasoning_effort": "none",
        "max_tokens": 200,
        "http_client": "instrumented-client",
    }]


def test_legacy_model_keeps_zero_temperature(monkeypatch):
    calls = []
    monkeypatch.setattr(chat_model, "ChatOpenAI", lambda **kwargs: calls.append(kwargs))

    chat_model.create_chat_model("gpt-4o-mini", "test-key", instrumented=False)

    assert calls == [{
        "model": "gpt-4o-mini",
        "api_key": "test-key",
        "temperature": 0,
    }]
