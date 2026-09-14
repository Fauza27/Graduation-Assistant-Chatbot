"""Build an explicit retrieval plan from a user question and memory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from src.generation.intent_classifier.reformulator import (
    RewriteMethod,
    needs_rewrite,
    normalize_query,
    reformulate_query,
)
from src.generation.memory import ConversationMemory


class QueryComplexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


RewriteFunction = Callable[
    [str, ConversationMemory],
    tuple[str, RewriteMethod],
]


@dataclass(frozen=True)
class QueryPlan:
    """Seluruh bentuk query yang dibutuhkan oleh retrieval pipeline."""

    original_query: str
    normalized_query: str
    resolved_query: str
    search_queries: tuple[str, ...]
    rerank_query: str
    rewrite_method: RewriteMethod
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    is_decomposed: bool = False

    @property
    def cache_key(self) -> str:
        """Representasi stabil dari seluruh query yang memengaruhi retrieval."""
        return "\n".join(self.search_queries)


def build_query_plan(
    question: str,
    memory: ConversationMemory,
    rewrite: RewriteFunction = reformulate_query,
) -> QueryPlan:
    """Normalize dan selesaikan referensi percakapan sebelum retrieval."""
    original_query = question.strip()
    normalized_query = normalize_query(original_query)
    resolved_query = normalized_query
    rewrite_method = RewriteMethod.NONE

    if needs_rewrite(normalized_query) and memory.has_prior_context:
        resolved_query, rewrite_method = rewrite(normalized_query, memory)

    return QueryPlan(
        original_query=original_query,
        normalized_query=normalized_query,
        resolved_query=resolved_query,
        search_queries=(resolved_query,),
        rerank_query=original_query,
        rewrite_method=rewrite_method,
    )
