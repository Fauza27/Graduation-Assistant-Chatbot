"""Validate source provenance independently of the LLM's semantic judgement."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from src.evaluation_agent.models import DocumentPage, EvidenceVerification


def normalize_quote(text: str) -> str:
    # Preserve punctuation, digits and negations; only normalize PDF whitespace.
    return " ".join(unicodedata.normalize("NFKC", text).split())


def validate_quote(
    result: EvidenceVerification, pages: list[DocumentPage]
) -> str | None:
    """Return a rejection reason, or None for an exact, correctly located quote."""
    start, end = result.page_start, result.page_end
    if start is None or end is None or start > end:
        return "missing_or_reversed_page_range"
    available = {page.page_number: page for page in pages}
    if any(number not in available for number in range(start, end + 1)):
        return "page_outside_checked_window"
    quote = normalize_quote(result.corrected_evidence_text)
    if not quote:
        return "empty_quote"
    source = normalize_quote(
        "\n".join(available[n].text for n in range(start, end + 1))
    )
    if quote not in source:
        return "quote_not_in_cited_pages"
    if result.answers_question != result.answer_available:
        return "contradictory_verdict"
    if result.answers_question and result.is_related_scope:
        return "contradictory_scope"
    if result.answers_question and not result.reference_answer.strip():
        return "missing_reference_answer"
    return None


def grounded_numbers(answer: str, quote: str) -> bool:
    """Reject invented numbers in a reference answer (not a semantic proof)."""

    def numbers(text: str) -> set[Decimal]:
        return {
            Decimal(value.replace(",", "."))
            for value in re.findall(r"\d+(?:[.,]\d+)?", text)
        }

    return numbers(answer).issubset(numbers(quote))


def validate_semantic_fit(result: EvidenceVerification) -> str | None:
    """Reject a supported verdict when its own semantic checks disagree."""

    if not result.answers_question and result.verdict != "partial":
        return None
    checks = {
        "subject": result.subject_matches,
        "attribute": result.attribute_matches,
        "scope": result.scope_matches,
        "unit": result.unit_matches,
    }
    mismatch = next((name for name, matches in checks.items() if not matches), None)
    return f"semantic_{mismatch}_mismatch" if mismatch else None
