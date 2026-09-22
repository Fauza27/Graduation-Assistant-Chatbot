"""Build an explicit retrieval plan from a user question and memory."""

from __future__ import annotations

import re
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

MAX_SEARCH_QUERIES = 3

_CLAUSE_START = (
    r"(?:apa|apakah|bagaimana|berapa|kapan|siapa|"
    r"di\s+mana|dimana|mengapa|adakah)\b"
)
_CLAUSE_SEPARATOR = re.compile(
    rf"(?:[,;]\s*(?:(?:dan|serta)\s+)?|"
    rf"\s+(?:dan|serta)\s+)(?={_CLAUSE_START})",
    re.IGNORECASE,
)

_DOMAIN_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "tugas akhir non skripsi",
        (
            "tugas akhir non skripsi",
            "non skripsi",
            "non-skripsi",
            "nonskripsi",
        ),
    ),
    (
        "Penulisan Ilmiah",
        ("penulisan ilmiah", "laporan pi", "ujian pi", "seminar pi"),
    ),
    (
        "KKP",
        ("kkp", "kuliah kerja praktik", "kuliah kerja praktek"),
    ),
    (
        "skripsi",
        ("skripsi", "tugas akhir skripsi", "proposal skripsi"),
    ),
)

_NON_SKRIPSI_TRACK_TERMS = (
    "jalur karya ilmiah",
    "karya ilmiah",
    "prosiding",
    "jalur profesional",
    "pekerja profesional",
    "it profesional",
    "jalur wirausaha",
    "wirausaha",
    "startup",
    "business model canvas",
)


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

    search_queries = decompose_query(resolved_query)

    return QueryPlan(
        original_query=original_query,
        normalized_query=normalized_query,
        resolved_query=resolved_query,
        search_queries=search_queries,
        rerank_query=resolved_query,
        rewrite_method=rewrite_method,
        complexity=(
            QueryComplexity.COMPLEX
            if len(search_queries) > 1
            else QueryComplexity.SIMPLE
        ),
        is_decomposed=len(search_queries) > 1,
    )


def decompose_query(query: str) -> tuple[str, ...]:
    """Pisahkan kebutuhan eksplisit tanpa memanggil LLM.

    Pemisahan hanya dilakukan ketika klausa berikutnya dimulai dengan kata
    tanya. Frasa seperti "dosen pembimbing dan penguji" tetap satu query.
    """
    raw_clauses = _CLAUSE_SEPARATOR.split(query)
    clauses = [clause.strip(" ,;?.") for clause in raw_clauses]
    clauses = [clause for clause in clauses if len(clause.split()) >= 2]

    if len(clauses) < 2:
        return (query,)

    if len(clauses) > MAX_SEARCH_QUERIES:
        clauses = [
            *clauses[: MAX_SEARCH_QUERIES - 1],
            " dan ".join(clauses[MAX_SEARCH_QUERIES - 1 :]),
        ]

    domain = _find_single_domain(query)
    queries: list[str] = []

    for clause in clauses:
        if domain and not _contains_domain(clause):
            clause = f"{clause} terkait {domain}"
        if clause not in queries:
            queries.append(clause)

    return tuple(queries) if len(queries) > 1 else (query,)


def _find_single_domain(query: str) -> str | None:
    query_lower = query.lower()
    matched: list[str] = []

    for canonical, terms in _DOMAIN_TERMS:
        searchable = query_lower
        if canonical == "skripsi":
            non_skripsi_terms = _DOMAIN_TERMS[0][1]
            for term in non_skripsi_terms:
                searchable = searchable.replace(term, " ")
        if any(term in searchable for term in terms):
            matched.append(canonical)

    if len(matched) == 1:
        return matched[0]

    if not matched and any(term in query_lower for term in _NON_SKRIPSI_TRACK_TERMS):
        return "tugas akhir non skripsi"

    return None


def _contains_domain(query: str) -> bool:
    query_lower = query.lower()
    return any(
        term in query_lower
        for _, terms in _DOMAIN_TERMS
        for term in terms
    ) or any(term in query_lower for term in _NON_SKRIPSI_TRACK_TERMS)
