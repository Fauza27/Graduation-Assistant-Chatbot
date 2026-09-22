"""Compare verified original-document evidence with production child chunks."""

from __future__ import annotations

import re

from src.evaluation_agent.models import ChunkAudit, ChunkMatch, EvidenceCandidate


WORD_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _terms(text: str) -> set[str]:
    return {match.group(0).lower() for match in WORD_PATTERN.finditer(text)}


def _coverage(evidence_terms: set[str], content: str) -> float:
    if not evidence_terms:
        return 0.0
    return len(evidence_terms & _terms(content)) / len(evidence_terms)


def _quote_tokens(text: str) -> str:
    """Ignore formatting while retaining word order, numbers and negations."""
    return " " + " ".join(WORD_PATTERN.findall(text.lower())) + " "


def audit_chunks(
    evidence: EvidenceCandidate,
    chunks: list[dict],
    parents: list[dict] | None = None,
) -> ChunkAudit:
    """Find missing, fragmented, or adequately represented evidence."""
    if not chunks:
        return ChunkAudit(
            status="extraction_missing",
            explanation="Tidak ada child chunk yang terhubung dengan dokumen asli.",
            diagnostics={"chunk_count": 0},
        )

    quote = _quote_tokens(evidence.evidence_text)
    exact_children = [
        row
        for row in chunks
        if quote.strip() and quote in _quote_tokens(str(row.get("content", "")))
    ]
    exact_parents = [
        row
        for row in parents or []
        if quote.strip() and quote in _quote_tokens(str(row.get("content", "")))
    ]
    if exact_children or exact_parents:
        parent_ids = {
            str(row["parent_id"])
            for row in [*exact_children, *exact_parents]
            if row.get("parent_id")
        }
        return ChunkAudit(
            status="chunking_valid",
            explanation="Kutipan asli ditemukan utuh pada child atau parent chunk.",
            affected_chunk_ids=[str(row["id"]) for row in exact_children],
            matched_parent_ids=sorted(parent_ids),
            matches=[
                ChunkMatch(
                    child_id=str(row["id"]),
                    parent_id=str(row.get("parent_id", "")),
                    coverage=1.0,
                )
                for row in exact_children
            ]
            + [
                ChunkMatch(child_id="", parent_id=str(row["parent_id"]), coverage=1.0)
                for row in exact_parents
            ],
            diagnostics={
                "match_method": "exact_quote",
                "exact_parent_ids": [str(row["parent_id"]) for row in exact_parents],
            },
        )

    evidence_terms = _terms(evidence.evidence_text)
    ranked = sorted(
        (
            (
                _coverage(evidence_terms, str(chunk.get("content", ""))),
                chunk,
            )
            for chunk in chunks
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    matches = [
        ChunkMatch(
            child_id=str(chunk.get("id", "")),
            parent_id=str(chunk.get("parent_id", "")),
            title=str(chunk.get("title", "")),
            pages=[str(page) for page in chunk.get("pages", [])],
            coverage=round(score, 4),
        )
        for score, chunk in ranked[:5]
        if score > 0
    ]
    best_coverage = matches[0].coverage if matches else 0.0
    combined_terms: set[str] = set()
    for _, chunk in ranked[:3]:
        combined_terms.update(_terms(str(chunk.get("content", ""))))
    combined_coverage = (
        len(evidence_terms & combined_terms) / len(evidence_terms)
        if evidence_terms
        else 0.0
    )

    # Lexical overlap is a search hint, not proof that extraction lost a fact.
    # Even complete token coverage can combine unrelated sentences or numbers.
    status = "inconclusive"
    explanation = (
        "Belum ditemukan kutipan utuh pada child/parent. Kemiripan kata saja "
        "tidak membuktikan kehilangan informasi atau kebutuhan rechunking."
    )
    return ChunkAudit(
        status=status,
        explanation=explanation,
        matches=matches,
        diagnostics={
            "best_coverage": round(best_coverage, 4),
            "combined_top_3_coverage": round(combined_coverage, 4),
            "source_chunk_count": len(chunks),
        },
    )
