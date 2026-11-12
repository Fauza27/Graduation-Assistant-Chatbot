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
from src.retrieval.domains import DOMAIN_PATTERNS, explicit_domains


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
_CONTEXT_PREFIX = re.compile(
    r"^(?:dalam|pada|untuk|di|kalau|jika|bila|apabila|setelah|sebelum|saat|ketika)\b",
    re.IGNORECASE,
)
_COMPARISON = re.compile(
    r"\b(?:bandingkan|perbandingan|perbedaan|bedanya|beda|dibanding(?:kan)?|versus|vs)\b",
    re.IGNORECASE,
)
_COMPARISON_SEPARATOR = re.compile(
    r"\s+(?:(?:dibanding(?:kan)?\s+)?dengan|dibanding(?:kan)?|dan|versus|vs\.?)\s+",
    re.IGNORECASE,
)
_PAGE_COUNT = re.compile(r"\b(?:jumlah halaman|berapa halaman|panjang naskah)\b", re.IGNORECASE)
_TRANSCRIPT = re.compile(r"\btranskrip(?:nya)?\b", re.IGNORECASE)
_GRADE_POSTING = re.compile(
    r"\b(?:muncul|tampil|ditampilkan|masuk|keluar|tercantum|dicantumkan|pencantuman|tercatat)\b",
    re.IGNORECASE,
)
_GENERIC_EXAM = re.compile(
    r"\b(?:seminar(?:\s+(?:proposal|hasil))?|ujian(?:\s+pendadaran)?|pendadaran)(?:nya)?"
    r"(?=\s*[?.!,;]|$|\s+(?:saya|itu|ini|tersebut|yang|akan|harus|dilaksanakan|"
    r"berapa|kapan|sejak|setelah|sebelum)\b)",
    re.IGNORECASE,
)
_EXAM_PROCEDURE = re.compile(
    r"\b(?:syarat|persyaratan|berkas|daftar|mendaftar|pendaftaran|batas|tenggat|"
    r"paling\s+lambat|kapan|jadwal|berapa\s+(?:lama|hari|minggu))\b",
    re.IGNORECASE,
)
_EXAM_CLARIFICATION = (
    "Apakah yang Anda maksud PI, KKP, TA Skripsi, atau TA Non-Skripsi?"
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
    clarification: str | None = None

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

    clarified_query = _resume_after_clarification(normalized_query, memory)
    if clarified_query:
        resolved_query, rewrite_method = clarified_query, RewriteMethod.RULE
    elif needs_rewrite(normalized_query) and memory.has_prior_context:
        resolved_query, rewrite_method = rewrite(normalized_query, memory)

    search_queries = decompose_query(resolved_query)
    clarification = None
    if (
        not explicit_domains(resolved_query)
        and _GENERIC_EXAM.search(normalized_query)
        and _EXAM_PROCEDURE.search(normalized_query)
    ):
        clarification = _EXAM_CLARIFICATION

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
        clarification=clarification,
    )


def _resume_after_clarification(query: str, memory: ConversationMemory) -> str | None:
    """Restore the pending question when the user supplies just the guide."""
    if memory.get_last_answer() != _EXAM_CLARIFICATION:
        return None

    domains = explicit_domains(query)
    if len(domains) != 1:
        return None

    domain = domains[0]
    reply = query.strip(" ?.!")
    if not re.fullmatch(
        rf"(?:(?:yang|untuk|maksud saya|jalur|ujian|seminar)\s+)*"
        rf"(?:(?:ta|tugas akhir)\s+)?(?:{DOMAIN_PATTERNS[domain]})"
        r"(?:\s+(?:ya|saja|aja|dong))?",
        reply,
        re.IGNORECASE,
    ):
        return None

    pending = memory.get_last_question()
    return f"{pending.rstrip(' ?.')} terkait {domain}?" if pending else None


def decompose_query(query: str) -> tuple[str, ...]:
    """Pisahkan kebutuhan eksplisit tanpa memanggil LLM.

    Pemisahan hanya dilakukan ketika klausa berikutnya dimulai dengan kata
    tanya. Frasa seperti "dosen pembimbing dan penguji" tetap satu query.
    """
    raw_clauses = _CLAUSE_SEPARATOR.split(query)
    if (
        len(raw_clauses) > 1
        and _CONTEXT_PREFIX.match(raw_clauses[0])
        and not re.search(rf"\b{_CLAUSE_START}", raw_clauses[0], re.IGNORECASE)
    ):
        # A leading qualifier is part of the question, not a search on its own.
        raw_clauses[:2] = [f"{raw_clauses[0]}, {raw_clauses[1]}"]
    clauses = [clause.strip(" ,;?.") for clause in raw_clauses]
    clauses = [clause for clause in clauses if len(clause.split()) >= 2]

    if len(clauses) < 2:
        return _shared_comparison_queries(query) or _grade_posting_queries(query)

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


def _grade_posting_queries(query: str) -> tuple[str, ...]:
    """Focus retrieval on grade posting for a single guide and question."""
    if not (
        _TRANSCRIPT.search(query)
        and _GRADE_POSTING.search(query)
        and re.search(r"\bnilai(?:nya)?\b", query, re.IGNORECASE)
    ):
        return (query,)

    domains = explicit_domains(query)
    if len(domains) != 1:
        return (query,)

    # The full request remains the reranking and generation question.
    return (f"pencantuman nilai {domains[0]} pada transkrip",)


def _shared_comparison_queries(query: str) -> tuple[str, ...]:
    """Search both guides for a shared attribute such as a minimum page count."""
    domains = explicit_domains(query)
    if len(domains) != 2 or not _COMPARISON.search(query):
        return ()

    for separator in _COMPARISON_SEPARATOR.finditer(query):
        left = query[:separator.start()]
        right = query[separator.end():].rstrip(" ?.")
        left_domains = explicit_domains(left)
        right_domains = explicit_domains(right)
        if len(left_domains) != 1 or len(right_domains) != 1 or left_domains == right_domains:
            continue

        left_domain, right_domain = left_domains[0], right_domains[0]
        left_topic = _strip_trailing_domain(left, left_domain)
        right_topic = _strip_trailing_domain(right, right_domain)
        if left_topic == left or right_topic == right:
            continue
        if right_topic and not left_topic.casefold().endswith(right_topic.casefold()):
            continue

        topic = re.sub(r"^bandingkan(?:\s+ketentuan)?\s+", "", left_topic, flags=re.I)
        if not topic:
            continue
        # Proposal length is documented in the seminar-proposal procedure.
        # This expands the search topic without changing the user's question.
        if _PAGE_COUNT.search(topic) and re.search(r"\bproposal$", topic, re.I):
            topic = re.sub(r"(?<!seminar )\bproposal$", "untuk seminar proposal", topic, flags=re.I)

        return f"{topic} {left_domain}", f"{topic} {right_domain}"
    return ()


def _strip_trailing_domain(text: str, domain: str) -> str:
    return re.sub(
        rf"(?:\b(?:ta|tugas akhir)\s+)?(?:{DOMAIN_PATTERNS[domain]})$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


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
