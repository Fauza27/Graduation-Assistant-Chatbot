from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class IntentType(str, Enum):
    NEEDS_RETRIEVAL = "needs_retrieval"
    CONVERSATIONAL = "conversational"
    CLARIFICATION = "clarification"


@dataclass
class Turn:
    """
    Merepresentasikan satu pesan dalam percakapan.
    """

    role: Literal["user", "assistant"]
    content: str
    intent: IntentType | None = None
    retrieved_doc_contents: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_lc_message(self) -> dict[str, str]:
        return {
            "role": self.role,
            "content": self.content,
        }


class ConversationMemory:
    """
    Short-term conversation memory.

    max_turns = jumlah maksimal pasangan Q&A lengkap.

    Sebuah pertanyaan user yang sedang aktif dapat tetap disimpan
    sebagai pesan tambahan dan tidak dihitung sebagai Q&A lengkap.
    """

    def __init__(self, max_turns: int = 5) -> None:
        if not isinstance(max_turns, int) or isinstance(max_turns, bool):
            raise TypeError("max_turns harus berupa integer")

        if max_turns < 1:
            raise ValueError("max_turns harus minimal 1")

        self.max_turns = max_turns
        self._turns: list[Turn] = []

    @property
    def turns(self) -> tuple[Turn, ...]:
        """
        Read-only view terhadap struktur urutan turn.
        """
        return tuple(self._turns)

    @property
    def is_empty(self) -> bool:
        return not self._turns

    @property
    def message_count(self) -> int:
        return len(self._turns)

    @property
    def turn_count(self) -> int:
        """
        Jumlah Q&A lengkap yang sedang tersimpan.
        """
        return len(self._get_complete_exchanges())

    @property
    def has_prior_context(self) -> bool:
        """
        True jika terdapat minimal satu Q&A lengkap.
        """
        return self.turn_count > 0

    def add_user_turn(
        self,
        content: str,
        intent: IntentType | None = None,
    ) -> None:
        self._turns.append(
            Turn(
                role="user",
                content=content,
                intent=intent,
            )
        )

        self._trim_to_max_turns()

    def add_assistant_turn(
        self,
        content: str,
        retrieved_doc_contents: list[str] | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> None:
        self._turns.append(
            Turn(
                role="assistant",
                content=content,
                retrieved_doc_contents=list(retrieved_doc_contents or []),
                sources=list(sources or []),
            )
        )

        self._trim_to_max_turns()

    def _get_complete_exchanges(self) -> list[tuple[Turn, Turn]]:
        """
        Kelompokkan turn menjadi pasangan User → Assistant.

        Hanya pasangan lengkap yang dikembalikan.

        Contoh:

        User 1
        Assistant 1
        User 2
        Assistant 2
        User 3

        Hasil:

        [
            (User 1, Assistant 1),
            (User 2, Assistant 2),
        ]
        """
        exchanges: list[tuple[Turn, Turn]] = []

        pending_user: Turn | None = None

        for turn in self._turns:
            if turn.role == "user":
                pending_user = turn

            elif turn.role == "assistant" and pending_user is not None:
                exchanges.append((pending_user, turn))
                pending_user = None

        return exchanges

    def _get_current_pending_user(self) -> Turn | None:
        """
        Ambil pertanyaan user terakhir yang belum memiliki jawaban assistant.
        """
        if not self._turns:
            return None

        last_turn = self._turns[-1]

        if last_turn.role == "user":
            return last_turn

        return None

    def _trim_to_max_turns(self) -> None:
        """
        Trim memory berdasarkan pasangan Q&A, bukan jumlah pesan mentah.

        Contoh max_turns = 2:

        User 1 → Assistant 1
        User 2 → Assistant 2
        User 3 → Assistant 3

        Setelah trim:

        User 2 → Assistant 2
        User 3 → Assistant 3

        Jika ada pertanyaan aktif:

        User 2 → Assistant 2
        User 3 → Assistant 3
        User 4 (pending)

        Pertanyaan User 4 tetap dipertahankan.
        """
        exchanges = self._get_complete_exchanges()
        pending_user = self._get_current_pending_user()

        # Ambil hanya Q&A terbaru.
        exchanges_to_keep = exchanges[-self.max_turns:]

        # Flatten kembali menjadi list Turn.
        new_turns: list[Turn] = []

        for user_turn, assistant_turn in exchanges_to_keep:
            new_turns.extend([user_turn, assistant_turn])

        # Pertahankan pertanyaan aktif jika ada.
        if pending_user is not None:
            new_turns.append(pending_user)

        self._turns = new_turns

    def get_history_for_llm(
        self,
        exclude_current_user_turn: bool = True,
    ) -> list[dict[str, str]]:
        """
        Ambil history untuk LLM.

        History dibatasi berdasarkan pasangan Q&A dari settings.
        """
        from config.settings import get_settings

        settings = get_settings()

        exchanges = self._get_complete_exchanges()

        exchanges_to_keep = exchanges[-settings.MAX_HISTORY_TURNS:]

        history: list[dict[str, str]] = []

        for user_turn, assistant_turn in exchanges_to_keep:
            history.append(user_turn.to_lc_message())
            history.append(assistant_turn.to_lc_message())

        # Secara optional tambahkan pertanyaan pending.
        if not exclude_current_user_turn:
            pending_user = self._get_current_pending_user()

            if pending_user is not None:
                history.append(pending_user.to_lc_message())

        return history

    def get_last_retrieved_docs(self) -> list[str]:
        for turn in reversed(self._turns):
            if (
                turn.role == "assistant"
                and turn.retrieved_doc_contents
            ):
                return list(turn.retrieved_doc_contents)

        return []

    def get_last_question(self) -> str | None:
        for turn in reversed(self._turns):
            if turn.role == "user":
                return turn.content

        return None

    def get_last_answer(self) -> str | None:
        for turn in reversed(self._turns):
            if turn.role == "assistant":
                return turn.content

        return None

    def get_previous_question(self) -> str | None:
        found_latest = False

        for turn in reversed(self._turns):
            if turn.role != "user":
                continue

            if found_latest:
                return turn.content

            found_latest = True

        return None

    @property
    def last_user_question(self) -> str | None:
        """Return the latest user question."""
        return self.get_last_question()

    @property
    def previous_user_question(self) -> str | None:
        """Return the user question before the latest one."""
        return self.get_previous_question()

    def get_conversation_summary(
        self,
        max_content_length: int = 200,
        exclude_current_user_turn: bool = True,
    ) -> str:
        """
        Buat summary dari Q&A yang tersimpan.
        """
        if max_content_length < 1:
            raise ValueError(
                "max_content_length harus minimal 1"
            )

        turns = self._turns

        if (
            exclude_current_user_turn
            and turns
            and turns[-1].role == "user"
        ):
            turns = turns[:-1]

        lines: list[str] = []

        for turn in turns:
            content = turn.content

            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."

            prefix = (
                "User"
                if turn.role == "user"
                else "Assistant"
            )

            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    def reset(self) -> None:
        self._turns.clear()

    def to_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "role": turn.role,
                "content": turn.content,
                "intent": (
                    turn.intent.value
                    if turn.intent is not None
                    else None
                ),
                "retrieved_doc_contents": list(
                    turn.retrieved_doc_contents
                ),
                "sources": list(turn.sources),
                "timestamp": turn.timestamp,
            }
            for turn in self._turns
        ]

    @classmethod
    def from_dict(
        cls,
        turns_data: list[dict[str, Any]],
        max_turns: int = 5,
    ) -> "ConversationMemory":
        memory = cls(max_turns=max_turns)

        for turn_data in turns_data:
            role = turn_data.get("role")

            if role not in ("user", "assistant"):
                raise ValueError(
                    f"Role tidak valid: {role!r}"
                )

            intent_value = turn_data.get("intent")

            memory._turns.append(
                Turn(
                    role=role,
                    content=str(
                        turn_data.get("content", "")
                    ),
                    intent=(
                        IntentType(intent_value)
                        if intent_value is not None
                        else None
                    ),
                    retrieved_doc_contents=list(
                        turn_data.get(
                            "retrieved_doc_contents",
                            [],
                        )
                        or []
                    ),
                    sources=list(
                        turn_data.get("sources", [])
                        or []
                    ),
                    timestamp=float(
                        turn_data.get(
                            "timestamp",
                            time.time(),
                        )
                    ),
                )
            )

        # Terapkan trimming juga untuk data lama dari database.
        memory._trim_to_max_turns()

        return memory

    def __repr__(self) -> str:
        pending = self._get_current_pending_user() is not None

        return (
            "ConversationMemory("
            f"turns={self.turn_count}, "
            f"max={self.max_turns}, "
            f"messages={self.message_count}, "
            f"pending_user={pending}"
            ")"
        )