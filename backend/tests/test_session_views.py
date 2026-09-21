from src.services.session_views import build_session_title, serialize_messages


def test_build_session_title_uses_first_user_message() -> None:
    turns = [
        {"role": "assistant", "content": "Selamat datang"},
        {"role": "user", "content": "Apa syarat mengambil PI?"},
    ]

    assert build_session_title(turns) == "Apa syarat mengambil PI?"


def test_build_session_title_truncates_only_long_questions() -> None:
    question = "a" * 41

    assert build_session_title([{"role": "user", "content": question}]) == (
        "a" * 40 + "..."
    )


def test_serialize_messages_preserves_sources_and_maps_assistant_to_bot() -> None:
    messages = serialize_messages(
        [
            {"role": "user", "content": "Halo"},
            {
                "role": "assistant",
                "content": "Hai",
                "sources": [{"parent_id": "pi-001"}],
            },
        ]
    )

    assert messages == [
        {"role": "user", "text": "Halo", "sources": []},
        {
            "role": "bot",
            "text": "Hai",
            "sources": [{"parent_id": "pi-001"}],
        },
    ]
