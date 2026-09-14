from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from src.generation.token_utils import count_tokens, truncate_to_tokens


class IntentType(str, Enum):
    NEEDS_RETRIEVAL = "needs_retrieval"
    CONVERSATIONAL = "conversational"
    CLARIFICATION = "clarification"


@dataclass
class Turn:
    """Satu pesan user atau assistant dalam percakapan."""

    role: Literal["user", "assistant"]
    content: str
    intent: IntentType | None = None
    retrieved_doc_contents: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_lc_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """Two-level memory: ringkasan lama dan percakapan terbaru.

    ``max_history_tokens`` membatasi gabungan ringkasan dan recent turns yang
    dikirim ke LLM. Class ini menentukan turn yang perlu diringkas, sedangkan
    pemanggilan LLM dilakukan oleh ``ConversationSummarizer`` agar penyimpanan
    state tetap terpisah dari layanan eksternal.
    """

    SERIALIZATION_VERSION = 2
    _STATE_MARKER = "conversation_memory"

    def __init__(
        self,
        max_history_tokens: int = 2500,
        min_recent_turns: int = 2,
        summary_max_tokens: int = 500,
        summary: str = "",
    ) -> None:
        self._validate_positive_int("max_history_tokens", max_history_tokens)
        self._validate_positive_int("min_recent_turns", min_recent_turns)
        self._validate_positive_int("summary_max_tokens", summary_max_tokens)

        if summary_max_tokens >= max_history_tokens:
            raise ValueError(
                "summary_max_tokens harus lebih kecil dari max_history_tokens"
            )

        self.max_history_tokens = max_history_tokens
        self.min_recent_turns = min_recent_turns
        self.summary_max_tokens = summary_max_tokens
        self.summary = summary.strip()
        self._turns: list[Turn] = []

    @staticmethod
    def _validate_positive_int(name: str, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} harus berupa integer")
        if value < 1:
            raise ValueError(f"{name} harus minimal 1")

    @property
    def turns(self) -> tuple[Turn, ...]:
        """Read-only view terhadap recent turns."""
        return tuple(self._turns)

    @property
    def is_empty(self) -> bool:
        return not self.summary and not self._turns

    @property
    def message_count(self) -> int:
        return len(self._turns)

    @property
    def turn_count(self) -> int:
        """Jumlah pasangan Q&A lengkap yang tersimpan sebagai recent turns."""
        return len(self._get_complete_exchanges())

    @property
    def has_prior_context(self) -> bool:
        return bool(self.summary) or self.turn_count > 0

    @property
    def history_token_count(self) -> int:
        """Perkiraan token untuk ringkasan dan seluruh recent messages."""
        texts = [self.summary] if self.summary else []
        texts.extend(turn.content for turn in self._turns)
        return sum(count_tokens(text) for text in texts)

    @property
    def needs_compaction(self) -> bool:
        return (
            self.history_token_count > self.max_history_tokens
            and bool(self.get_turns_to_summarize())
        )

    def add_user_turn(
        self,
        content: str,
        intent: IntentType | None = None,
    ) -> None:
        self._turns.append(Turn(role="user", content=content, intent=intent))

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

    def _get_complete_exchanges(self) -> list[tuple[Turn, Turn]]:
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
        if self._turns and self._turns[-1].role == "user":
            return self._turns[-1]
        return None

    def get_turns_to_summarize(self) -> tuple[Turn, ...]:
        """Return complete exchanges lama yang aman dipindah ke summary."""
        exchanges = self._get_complete_exchanges()
        removable_count = max(0, len(exchanges) - self.min_recent_turns)
        old_exchanges = exchanges[:removable_count]
        return tuple(turn for exchange in old_exchanges for turn in exchange)

    def apply_summary(
        self,
        summary: str,
        summarized_turns: tuple[Turn, ...],
    ) -> None:
        """Ganti summary dan hapus recent turns yang sudah diringkas."""
        count = len(summarized_turns)
        if count == 0:
            return
        if tuple(self._turns[:count]) != summarized_turns:
            raise ValueError("Recent turns berubah selama proses summarization")

        remaining = self._turns[count:]
        recent_tokens = sum(count_tokens(turn.content) for turn in remaining)
        available_summary_tokens = max(
            0,
            min(
                self.summary_max_tokens,
                self.max_history_tokens - recent_tokens,
            ),
        )

        self.summary = truncate_to_tokens(summary.strip(), available_summary_tokens)
        self._turns = remaining

    def get_history_for_llm(
        self,
        exclude_current_user_turn: bool = True,
    ) -> list[dict[str, str]]:
        """Return recent messages; token limiting dilakukan lewat compaction."""
        turns = self._turns
        if exclude_current_user_turn and self._get_current_pending_user() is not None:
            turns = turns[:-1]
        return [turn.to_lc_message() for turn in turns]

    def get_last_retrieved_docs(self) -> list[str]:
        for turn in reversed(self._turns):
            if turn.role == "assistant" and turn.retrieved_doc_contents:
                return list(turn.retrieved_doc_contents)
        return []

    def get_last_question(self) -> str | None:
        return next(
            (turn.content for turn in reversed(self._turns) if turn.role == "user"),
            None,
        )

    def get_last_answer(self) -> str | None:
        return next(
            (turn.content for turn in reversed(self._turns) if turn.role == "assistant"),
            None,
        )

    def get_previous_question(self) -> str | None:
        questions = [turn.content for turn in self._turns if turn.role == "user"]
        return questions[-2] if len(questions) >= 2 else None

    @property
    def last_user_question(self) -> str | None:
        return self.get_last_question()

    @property
    def previous_user_question(self) -> str | None:
        return self.get_previous_question()

    def get_conversation_summary(
        self,
        max_content_length: int = 200,
        exclude_current_user_turn: bool = True,
    ) -> str:
        """Gabungkan summary lama dan recent turns untuk query reformulation."""
        if max_content_length < 1:
            raise ValueError("max_content_length harus minimal 1")

        lines = [f"Ringkasan lama: {self.summary}"] if self.summary else []
        turns = self._turns
        if exclude_current_user_turn and self._get_current_pending_user() is not None:
            turns = turns[:-1]

        for turn in turns:
            content = turn.content
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            prefix = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    def reset(self) -> None:
        self.summary = ""
        self._turns.clear()

    def to_dict(self) -> list[dict[str, Any]]:
        """Serialize ke JSON array agar kompatibel dengan schema database lama."""
        turns = [self._serialize_turn(turn) for turn in self._turns]
        state = {
            "_type": self._STATE_MARKER,
            "version": self.SERIALIZATION_VERSION,
            "summary": self.summary,
        }

        # Simpan metadata di record pertama agar jsonb_array_length tetap
        # merepresentasikan jumlah pesan seperti pada format database lama.
        if turns:
            turns[0]["_memory"] = state
            return turns
        return [state] if self.summary else []

    @staticmethod
    def _serialize_turn(turn: Turn) -> dict[str, Any]:
        return {
            "role": turn.role,
            "content": turn.content,
            "intent": turn.intent.value if turn.intent is not None else None,
            "retrieved_doc_contents": list(turn.retrieved_doc_contents),
            "sources": list(turn.sources),
            "timestamp": turn.timestamp,
        }

    @classmethod
    def serialized_turns(
        cls,
        data: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Extract turn records dari format legacy maupun format versioned."""
        if not data:
            return []
        if isinstance(data, dict):
            records = data.get("turns", [])
        elif isinstance(data, list):
            records = data
        else:
            raise TypeError("Data memory harus berupa list atau dict")
        return [
            record
            for record in records
            if isinstance(record, dict)
            and record.get("role") in {"user", "assistant"}
        ]

    @classmethod
    def from_dict(
        cls,
        data: list[dict[str, Any]] | dict[str, Any],
        *,
        max_history_tokens: int = 2500,
        min_recent_turns: int = 2,
        summary_max_tokens: int = 500,
    ) -> "ConversationMemory":
        summary = ""
        if isinstance(data, dict):
            summary = str(data.get("summary", ""))
        elif data and isinstance(data[0], dict):
            state = data[0].get("_memory", data[0])
            if isinstance(state, dict) and state.get("_type") == cls._STATE_MARKER:
                summary = str(state.get("summary", ""))

        memory = cls(
            max_history_tokens=max_history_tokens,
            min_recent_turns=min_recent_turns,
            summary_max_tokens=summary_max_tokens,
            summary=summary,
        )

        for turn_data in cls.serialized_turns(data):
            intent_value = turn_data.get("intent")
            memory._turns.append(
                Turn(
                    role=turn_data["role"],
                    content=str(turn_data.get("content", "")),
                    intent=IntentType(intent_value) if intent_value is not None else None,
                    retrieved_doc_contents=list(
                        turn_data.get("retrieved_doc_contents", []) or []
                    ),
                    sources=list(turn_data.get("sources", []) or []),
                    timestamp=float(turn_data.get("timestamp", time.time())),
                )
            )

        return memory

    def __repr__(self) -> str:
        return (
            "ConversationMemory("
            f"recent_turns={self.turn_count}, "
            f"tokens={self.history_token_count}/{self.max_history_tokens}, "
            f"summary={bool(self.summary)}, "
            f"messages={self.message_count}"
            ")"
        )


def get_memory_config() -> dict[str, int]:
    """Ambil konfigurasi memory dalam satu bentuk yang dapat dipakai ulang."""
    from config.settings import get_settings

    settings = get_settings()
    return {
        "max_history_tokens": settings.MEMORY_MAX_HISTORY_TOKENS,
        "min_recent_turns": settings.MEMORY_MIN_RECENT_TURNS,
        "summary_max_tokens": settings.MEMORY_SUMMARY_MAX_TOKENS,
    }


def create_conversation_memory() -> ConversationMemory:
    return ConversationMemory(**get_memory_config())
