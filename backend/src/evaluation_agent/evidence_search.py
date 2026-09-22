"""High-recall lexical search over pages extracted from original documents.

The evaluator must first locate plausible source pages before an LLM judges the
evidence. Keeping this stage deterministic makes misses observable, inexpensive,
and reproducible.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from src.evaluation_agent.models import EvaluationCase, PageWindow


TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

# Question words and conversational filler add no value to page retrieval.
STOP_WORDS = {
    "ada",
    "aja",
    "apa",
    "apakah",
    "atau",
    "bagaimana",
    "berapa",
    "buat",
    "dalam",
    "dan",
    "dari",
    "dengan",
    "di",
    "gimana",
    "itu",
    "jadi",
    "juga",
    "kah",
    "kalau",
    "ke",
    "kok",
    "lagi",
    "mau",
    "nah",
    "nggak",
    "nya",
    "oleh",
    "pada",
    "pas",
    "saja",
    "sama",
    "saya",
    "sebagai",
    "setelah",
    "sih",
    "terus",
    "tidak",
    "untuk",
    "waktu",
    "yang",
    "ya",
}

# Canonical forms bridge common student language and formal guide wording.
TOKEN_ALIASES = {
    "acc": "setuju",
    "approval": "setuju",
    "diajukan": "aju",
    "dilaksanakan": "laksana",
    "disetujui": "setuju",
    "kemiripan": "plagiat",
    "kemiripannya": "plagiat",
    "mengajukan": "aju",
    "pengajuan": "aju",
    "pelaksanaan": "laksana",
    "plagiarism": "plagiat",
    "plagiarisme": "plagiat",
    "plagiasi": "plagiat",
    "registrasi": "daftar",
    "similarity": "plagiat",
    "unggah": "upload",
}

PHRASE_ALIASES = {
    "anti plagiasi": "plagiat",
    "anti plagiarism": "plagiat",
    "cek plagiasi": "plagiat",
    "kuliah kerja praktek": "kkp",
    "kuliah kerja praktik": "kkp",
    "non skripsi": "nonskripsi",
    "penulisan ilmiah": "pi",
    "seminar hasil": "semhas",
    "seminar proposal": "sempro",
    "tugas akhir non skripsi": "nonskripsi",
}

EXPANSION_GROUPS = (
    frozenset({"aju", "daftar", "pendaftaran", "upload", "kpst", "laman", "web"}),
    frozenset({"berkas", "dokumen", "lampiran", "persyaratan", "syarat"}),
    frozenset({"bimbingan", "konsultasi", "pembimbing", "lembar"}),
    frozenset({"durasi", "lama", "menit", "jam"}),
    frozenset({"halaman", "lembar", "naskah"}),
    frozenset({"ipk", "indeks", "prestasi", "kumulatif"}),
    frozenset({"nilai", "bobot", "penilaian", "lulus"}),
    frozenset({"pakaian", "almamater", "jas", "dasi", "seragam"}),
    frozenset({"plagiat", "turnitin", "persentase", "batas"}),
    frozenset({"sks", "kredit", "semester"}),
    frozenset({"video", "rekaman", "presentasi"}),
)

DOMAIN_TERMS = {
    "NON_SKRIPSI": (
        "nonskripsi",
        "prosiding",
        "sinta",
        "scopus",
        "wirausaha",
        "profesional",
    ),
    "KKP": ("kkp",),
    "PI": ("pi",),
    "SKRIPSI": ("skripsi",),
}

SCOPE_TERMS = frozenset(
    {
        "kkp",
        "nonskripsi",
        "pendadaran",
        "pi",
        "semhas",
        "sempro",
        "skripsi",
    }
)
SKRIPSI_PROCEDURE_TERMS = frozenset({"pendadaran", "semhas", "sempro"})


def normalize_text(text: str) -> str:
    """Normalize punctuation and frequent multi-word academic aliases."""

    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[-_/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for phrase, replacement in PHRASE_ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(phrase)}\b", replacement, normalized)
    return normalized


def tokenize(text: str, *, remove_stop_words: bool = True) -> list[str]:
    tokens = [
        TOKEN_ALIASES.get(token, token)
        for token in TOKEN_PATTERN.findall(normalize_text(text))
    ]
    if remove_stop_words:
        tokens = [token for token in tokens if token not in STOP_WORDS]
    return tokens


def infer_domains(case: EvaluationCase) -> set[str]:
    """Use explicit student domains, newest first; never trust a rewrite or answer."""
    if case.question_plan is not None:
        return set(case.question_plan.target_domains)
    primary = set(tokenize(case.question))
    domains = domains_in_text(case.question)
    if domains:
        return domains
    history = case.prior_questions or [
        turn.question for turn in case.conversation_context
    ]
    for question in reversed(history):
        domains = domains_in_text(question)
        if domains:
            return domains
    context_tokens = set(tokenize(" ".join(history)))
    if (primary | context_tokens).intersection(SKRIPSI_PROCEDURE_TERMS):
        return {"SKRIPSI", "NON_SKRIPSI"}
    return set()


def domains_in_text(text: str) -> set[str]:
    tokens = set(tokenize(text))
    return {
        domain for domain, terms in DOMAIN_TERMS.items() if tokens.intersection(terms)
    }


@dataclass(frozen=True)
class SearchWindow:
    window: PageWindow
    domain: str
    normalized_text: str
    token_counts: Counter[str]
    length: int


@dataclass(frozen=True)
class RankedWindow:
    window: PageWindow
    score: float
    matched_terms: tuple[str, ...]
    snippet: str


class OriginalDocumentIndex:
    """Small in-memory BM25 index built from every original-document window."""

    def __init__(self, windows: list[tuple[PageWindow, str]]) -> None:
        if not windows:
            raise ValueError("Indeks bukti memerlukan minimal satu page window")
        self._entries = [
            self._build_entry(window, domain) for window, domain in windows
        ]
        self._average_length = sum(entry.length for entry in self._entries) / len(
            self._entries
        )
        document_frequency: Counter[str] = Counter()
        for entry in self._entries:
            document_frequency.update(entry.token_counts.keys())
        count = len(self._entries)
        self._idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    @staticmethod
    def _build_entry(window: PageWindow, domain: str) -> SearchWindow:
        normalized = normalize_text(f"{window.document_title} {window.text}")
        counts = Counter(tokenize(normalized, remove_stop_words=False))
        return SearchWindow(
            window=window,
            domain=domain,
            normalized_text=normalized,
            token_counts=counts,
            length=max(1, sum(counts.values())),
        )

    def search(
        self,
        case: EvaluationCase,
        *,
        limit: int,
        allowed_domains: set[str] | None = None,
    ) -> list[RankedWindow]:
        domains = allowed_domains if allowed_domains is not None else infer_domains(case)
        query_weights = self._query_weights(case, domains)
        entries = [
            entry for entry in self._entries if not domains or entry.domain in domains
        ]
        ranked: list[RankedWindow] = []
        scoring_question = (
            case.question_plan.resolved_question
            if case.question_plan is not None
            else case.evidence_question
        )
        for entry in entries:
            score, matched = self._score(entry, query_weights, scoring_question)
            if score <= 0:
                continue
            ranked.append(
                RankedWindow(
                    window=entry.window,
                    score=score,
                    matched_terms=tuple(sorted(matched)),
                    snippet=_extract_snippet(entry.window.text, matched),
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return _diversify_documents(ranked, limit)

    def _query_weights(
        self, case: EvaluationCase, domains: set[str] | None = None
    ) -> Counter[str]:
        weights: Counter[str] = Counter()
        plan = case.question_plan
        primary_text = plan.resolved_question if plan is not None else case.evidence_question
        primary_tokens = tokenize(primary_text)
        grounded_scope = set(tokenize(case.question))
        for turn in case.conversation_context[-3:]:
            grounded_scope.update(tokenize(turn.question))
        grounded_scope.intersection_update(SCOPE_TERMS)
        if grounded_scope:
            primary_tokens = [
                token
                for token in primary_tokens
                if token not in SCOPE_TERMS or token in grounded_scope
            ]

        for token in primary_tokens:
            weights[token] += 2.0
        if plan is not None:
            for need in plan.information_needs:
                if domains and need.domains and set(need.domains).isdisjoint(domains):
                    continue
                for token in tokenize(need.description):
                    weights[token] += 1.25
        if case.question.strip().lower() != case.evidence_question.lower():
            for token in tokenize(case.question):
                weights[token] += 0.75
        recency_weights = (0.25, 0.5, 1.0)
        recent_turns = case.conversation_context[-3:]
        weights_by_turn = recency_weights[-len(recent_turns) :]
        for turn, context_weight in zip(recent_turns, weights_by_turn):
            for token in tokenize(turn.question):
                weights[token] += context_weight

        original_terms = set(weights)
        for group in EXPANSION_GROUPS:
            if original_terms.intersection(group):
                for token in group:
                    if token not in original_terms:
                        weights[token] += 0.3
        return weights

    def _score(
        self,
        entry: SearchWindow,
        query_weights: Counter[str],
        question: str,
    ) -> tuple[float, set[str]]:
        score = 0.0
        matched: set[str] = set()
        k1 = 1.5
        length_normalizer = 1 - 0.75 + 0.75 * entry.length / self._average_length
        for term, weight in query_weights.items():
            frequency = entry.token_counts.get(term, 0)
            if not frequency:
                continue
            matched.add(term)
            term_score = self._idf.get(term, 0.0) * (
                frequency * (k1 + 1) / (frequency + k1 * length_normalizer)
            )
            score += weight * term_score

        significant = tokenize(question)
        for size, bonus in ((3, 2.0), (2, 1.0)):
            for index in range(len(significant) - size + 1):
                phrase = " ".join(significant[index : index + size])
                if phrase in entry.normalized_text:
                    score += bonus
        for number in re.findall(r"\b\d+(?:[.,]\d+)?\b", question):
            if re.search(rf"\b{re.escape(number)}\b", entry.normalized_text):
                score += 3.0
        return score, matched


def _diversify_documents(items: list[RankedWindow], limit: int) -> list[RankedWindow]:
    """Keep global relevance while giving each plausible document one candidate."""

    if len(items) <= limit:
        return items
    selected: list[RankedWindow] = []
    seen_documents: set[str] = set()
    for item in items:
        slug = item.window.document_slug
        if slug not in seen_documents:
            selected.append(item)
            seen_documents.add(slug)
            if len(selected) == limit:
                return selected
    selected_keys = {
        (item.window.document_slug, item.window.page_start) for item in selected
    }
    for item in items:
        key = (item.window.document_slug, item.window.page_start)
        if key in selected_keys:
            continue
        selected.append(item)
        if len(selected) == limit:
            break
    return sorted(selected, key=lambda item: item.score, reverse=True)


def _extract_snippet(text: str, matched_terms: set[str], radius: int = 1) -> str:
    """Return nearby lines as the candidate quote while preserving page labels."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected: set[int] = set()
    for index, line in enumerate(lines):
        line_terms = set(tokenize(line, remove_stop_words=False))
        if line_terms.intersection(matched_terms):
            selected.update(
                range(max(0, index - radius), min(len(lines), index + radius + 1))
            )
    if not selected:
        return "\n".join(lines[:8])
    return "\n".join(lines[index] for index in sorted(selected))[:4000]
