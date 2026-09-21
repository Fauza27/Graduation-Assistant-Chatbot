"""Build lexical-search alternatives from terminology used in the guides.

The vector query remains unchanged. For PostgreSQL full-text search, every
expanded form keeps the complete user intent and is joined with ``OR``. This
matters because ``websearch_to_tsquery`` treats ordinary whitespace as ``AND``;
simply appending synonyms would make a query stricter instead of broader.
"""

from __future__ import annotations

import re

from loguru import logger

MAX_QUERY_VARIANTS = 8

# The expansions below are terms that appear in the four current guidebooks.
ACRONYM_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "PI": ("Penulisan Ilmiah",),
    "KKP": ("Kuliah Kerja Praktik", "Kuliah Kerja Praktek"),
    "TA": ("Tugas Akhir",),
    "SKS": ("Satuan Kredit Semester",),
    "IPK": ("Indeks Prestasi Kumulatif",),
    "KRS": ("Kartu Rencana Studi",),
    "BAAK": ("Biro Administrasi Akademik dan Kemahasiswaan",),
    "BAUK": ("Biro Administrasi Umum dan Keuangan",),
    "BKK": ("Bursa Kerja Khusus",),
    "EYD": ("Ejaan Yang Disempurnakan",),
    "LOA": ("Letter of Acceptance", "Lembar Persetujuan"),
    "BMC": ("Business Model Canvas",),
    "NIB": ("Nomor Induk Berusaha",),
    "NPWP": ("Nomor Pokok Wajib Pajak",),
    "ISSN": ("International Standard Serial Number",),
    "SWOT": ("Strength Weakness Opportunity Threat",),
}

# These abbreviations are safe to match regardless of letter case. PI and TA
# remain uppercase-only because their lowercase forms occur naturally in text.
CASE_INSENSITIVE_ACRONYMS = frozenset(
    acronym for acronym in ACRONYM_EXPANSIONS if acronym not in {"PI", "TA"}
)

_AMBIGUOUS_LONG_FORMS = {"lembar persetujuan"}

LONG_FORM_TO_ACRONYM: dict[str, tuple[str, ...]] = {
    long_form.lower(): (acronym,)
    for acronym, long_forms in ACRONYM_EXPANSIONS.items()
    for long_form in long_forms
    if long_form.lower() not in _AMBIGUOUS_LONG_FORMS
}

# Student wording -> wording present in the documents. Each replacement is a
# lexical alternative, never an assumed answer or numeric requirement.
PHRASE_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "sidang skripsi": ("ujian pendadaran skripsi",),
    "sidang tugas akhir": ("ujian pendadaran",),
    "sidang": ("pendadaran", "ujian"),
    "anti plagiarisme": ("anti-plagiarisme", "kemiripan Turnitin"),
    "anti-plagiarism": ("anti-plagiarisme", "kemiripan Turnitin"),
    "similarity": ("kemiripan", "anti-plagiarisme"),
    "surat diterima jurnal": ("Letter of Acceptance", "Lembar Persetujuan"),
    "model bisnis": ("Business Model Canvas",),
    "pembimbing": ("dosen pembimbing",),
    "penguji": ("dosen penguji",),
}


def _replace_token(
    text: str,
    token: str,
    replacement: str,
    *,
    case_sensitive: bool,
) -> str | None:
    """Replace one complete token and return a changed query variant."""

    flags = 0 if case_sensitive else re.IGNORECASE
    replaced, count = re.subn(
        rf"\b{re.escape(token)}\b",
        replacement,
        text,
        count=1,
        flags=flags,
    )
    return replaced if count else None


def _replace_phrase(
    text: str,
    phrase: str,
    replacement: str,
) -> str | None:
    """Replace one complete phrase case-insensitively."""

    replaced, count = re.subn(
        rf"(?<!\w){re.escape(phrase)}(?!\w)",
        replacement,
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return replaced if count else None


def _append_variant(
    variants: list[str],
    candidate: str | None,
) -> None:
    """Append one normalized, unique alternative within the safety cap."""

    if candidate is None or len(variants) >= MAX_QUERY_VARIANTS:
        return

    normalized = re.sub(r"\s+", " ", candidate).strip()
    existing = {variant.casefold() for variant in variants}
    if normalized and normalized.casefold() not in existing:
        variants.append(normalized)


def expand_query(question: str) -> str:
    """Return OR-ed lexical variants while preserving the complete question."""

    if not question:
        return question

    variants = [question.strip()]
    question_lower = question.lower()

    for acronym, long_forms in ACRONYM_EXPANSIONS.items():
        case_sensitive = acronym not in CASE_INSENSITIVE_ACRONYMS
        for long_form in long_forms:
            _append_variant(
                variants,
                _replace_token(
                    question,
                    acronym,
                    long_form,
                    case_sensitive=case_sensitive,
                ),
            )

    for long_form, acronyms in LONG_FORM_TO_ACRONYM.items():
        # Do not shorten the domain name "Tugas Akhir Non Skripsi" to TA.
        if (
            long_form == "tugas akhir"
            and "tugas akhir non skripsi" in question_lower
        ):
            continue

        for acronym in acronyms:
            _append_variant(
                variants,
                _replace_phrase(question, long_form, acronym),
            )

    # Prefer longer phrases so "sidang skripsi" is handled before "sidang".
    for phrase in sorted(PHRASE_EQUIVALENTS, key=len, reverse=True):
        for equivalent in PHRASE_EQUIVALENTS[phrase]:
            if equivalent.casefold() in question.casefold():
                continue
            _append_variant(
                variants,
                _replace_phrase(question, phrase, equivalent),
            )

    if len(variants) == 1:
        return question

    expanded = " OR ".join(variants)
    logger.debug(
        "Lexical query expansion created {} alternative(s): {}",
        len(variants) - 1,
        variants[1:],
    )
    return expanded


def expand_query_smart(question: str) -> str:
    """Backward-compatible wrapper used by ``HybridSearcher``."""

    return expand_query(question)
