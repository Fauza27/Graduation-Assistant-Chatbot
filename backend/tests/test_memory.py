from src.generation.chain import build_messages
from src.generation.memory import ConversationMemory


def _add_exchange(memory: ConversationMemory, question: str, answer: str) -> None:
    memory.add_user_turn(question)
    memory.add_assistant_turn(answer)


class TestConversationMemory:
    def test_compaction_keeps_recent_exchanges_and_applies_summary(self):
        memory = ConversationMemory(
            max_history_tokens=40,
            min_recent_turns=2,
            summary_max_tokens=10,
        )
        _add_exchange(memory, "syarat KKP " * 12, "jawaban KKP " * 12)
        _add_exchange(memory, "syarat PI", "jawaban PI")
        _add_exchange(memory, "alur skripsi", "jawaban skripsi")

        old_turns = memory.get_turns_to_summarize()

        assert memory.needs_compaction is True
        assert len(old_turns) == 2

        memory.apply_summary("User membahas syarat KKP.", old_turns)

        assert memory.summary
        assert memory.turn_count == 2
        assert memory.turns[0].content == "syarat PI"
        assert memory.history_token_count <= memory.max_history_tokens

    def test_versioned_round_trip_preserves_summary_and_turns(self):
        memory = ConversationMemory(summary="User sebelumnya membahas KKP.")
        _add_exchange(memory, "Bagaimana prosedurnya?", "Prosedurnya adalah...")

        restored = ConversationMemory.from_dict(memory.to_dict())

        assert restored.summary == memory.summary
        assert [turn.content for turn in restored.turns] == [
            "Bagaimana prosedurnya?",
            "Prosedurnya adalah...",
        ]

    def test_legacy_array_remains_readable(self):
        restored = ConversationMemory.from_dict(
            [
                {"role": "user", "content": "Apa itu PI?"},
                {"role": "assistant", "content": "PI adalah..."},
            ]
        )

        assert restored.summary == ""
        assert restored.turn_count == 1

    def test_summary_is_included_in_generation_prompt(self):
        messages = build_messages(
            question="Bagaimana prosedurnya?",
            context="Dokumen prosedur",
            history=[],
            conversation_summary="User membahas persyaratan KKP.",
        )

        assert "User membahas persyaratan KKP." in messages[-1].content
