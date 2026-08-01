from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class IntentType(str, Enum):
    NEEDS_RETRIEVAL = "needs_retrieval"
    CONVERSATIONAL = "conversational"
    CLARIFICATION = "clarification"


@dataclass
class Turn:
    role: Literal["user", "assistant"]
    content: str
    intent: IntentType | None = None
    retrieved_doc_contents: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_lc_message(self) -> dict:
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns = max_turns
        self._turns: list[Turn] = []

    def add_user_turn(
        self,
        content: str,
        intent: IntentType | None = None,
    ) -> None:
        self._turns.append(Turn(role="user", content=content, intent=intent))
        self._enforce_window()

    def add_assistant_turn(
        self,
        content: str,
        retrieved_doc_contents: list[str] | None = None,
    ) -> None:
        self._turns.append(Turn(
            role="assistant",
            content=content,
            retrieved_doc_contents=retrieved_doc_contents or [],
        ))
        self._enforce_window()

    def _enforce_window(self) -> None:
        max_messages = self.max_turns * 2
        if len(self._turns) > max_messages:
            self._turns = self._turns[-max_messages:]

    def get_history_for_llm(self) -> list[dict]:
        from config.settings import get_settings
        settings = get_settings()
        
        if len(self._turns) <= 1:
            return []
            
        # The last turn is the current user question, we exclude it
        history_turns = self._turns[:-1]
        
        # Apply sliding window based on MAX_HISTORY_TURNS (each turn is a Q&A pair)
        max_messages = settings.MAX_HISTORY_TURNS * 2
        if len(history_turns) > max_messages:
            history_turns = history_turns[-max_messages:]
            
        return [t.to_lc_message() for t in history_turns]

    def get_last_retrieved_docs(self) -> list[str]:
        for turn in reversed(self._turns):
            if turn.role == "assistant" and turn.retrieved_doc_contents:
                return turn.retrieved_doc_contents
        return []

    def get_conversation_summary(self) -> str:
        if not self._turns:
            return ""

        lines = []
        for turn in self._turns[:-1]:
            # FIX: prefix sudah berisi spasi dan label lengkap
            prefix = "User" if turn.role == "user" else "Assistant"
            content = (
                turn.content[:200] + "..."
                if len(turn.content) > 200
                else turn.content
            )
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

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

    @property
    def turn_count(self) -> int:
        return len(self._turns) // 2

    @property
    def is_empty(self) -> bool:
        return len(self._turns) == 0

    @property
    def has_prior_context(self) -> bool:
        """Check if there's at least one complete Q&A pair before the current turn."""
        # We need at least: [user, assistant, user] = 3 turns
        # The last turn is the current user question
        assistant_turns = [t for t in self._turns if t.role == "assistant"]
        return len(assistant_turns) > 0

    def get_previous_question(self) -> str | None:
        """Get the question BEFORE the current one (second-to-last user turn)."""
        user_turns = [t for t in self._turns if t.role == "user"]
        if len(user_turns) >= 2:
            return user_turns[-2].content
        return None

    def reset(self) -> None:
        self._turns = []

    def to_dict(self) -> list[dict]:
        """Convert turns to dictionary format for JSONB storage."""
        return [
            {
                "role": turn.role,
                "content": turn.content,
                "intent": turn.intent.value if turn.intent else None,
                "retrieved_doc_contents": turn.retrieved_doc_contents,
                "timestamp": turn.timestamp
            }
            for turn in self._turns
        ]

    @classmethod
    def from_dict(cls, turns_data: list[dict], max_turns: int = 5) -> "ConversationMemory":
        """Reconstruct ConversationMemory from dictionary data."""
        memory = cls(max_turns=max_turns)
        for turn_data in turns_data:
            turn = Turn(
                role=turn_data["role"],
                content=turn_data["content"],
                intent=IntentType(turn_data["intent"]) if turn_data.get("intent") else None,
                retrieved_doc_contents=turn_data.get("retrieved_doc_contents", []),
                timestamp=turn_data.get("timestamp", time.time())
            )
            memory._turns.append(turn)
        return memory

    def __repr__(self) -> str:
        return (
            f"ConversationMemory("
            f"turns={self.turn_count}, "
            f"max={self.max_turns}, "
            f"messages={len(self._turns)})"
        )