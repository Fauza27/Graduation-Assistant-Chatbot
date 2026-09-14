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


def audit_chunks(
    evidence: EvidenceCandidate,
    chunks: list[dict],
) -> ChunkAudit:
    """Find missing, fragmented, or adequately represented evidence."""
    if not chunks:
        return ChunkAudit(
            status="extraction_missing",
            explanation="Tidak ada child chunk yang terhubung dengan dokumen asli.",
            diagnostics={"chunk_count": 0},
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

    if best_coverage < 0.2:
        status = "extraction_missing"
        explanation = (
            "Bukti pada dokumen asli hampir tidak terwakili dalam child chunks."
        )
    elif (
        combined_coverage >= 0.85
        and best_coverage < 0.85
        and combined_coverage - best_coverage >= 0.1
        and len(matches) > 1
    ):
        status = "context_split"
        explanation = (
            "Bukti tersebar pada beberapa child chunk dan satu chunk saja tidak "
            "membawa konteks yang cukup."
        )
    elif best_coverage < 0.6:
        status = "extraction_corrupted"
        explanation = (
            "Sebagian bukti ditemukan, tetapi representasi chunk tidak lengkap."
        )
    else:
        status = "chunking_valid"
        explanation = "Bukti dokumen asli terwakili dengan baik dalam chunk."

    if status == "extraction_missing":
        relevant_matches = []
    elif status == "context_split":
        relevant_matches = matches[:3]
    else:
        relevant_matches = [
            match
            for match in matches
            if match.coverage >= max(0.2, best_coverage * 0.75)
        ]

    return ChunkAudit(
        status=status,
        explanation=explanation,
        affected_chunk_ids=[match.child_id for match in relevant_matches],
        matched_parent_ids=list(
            dict.fromkeys(
                match.parent_id for match in relevant_matches if match.parent_id
            )
        ),
        matches=matches,
        diagnostics={
            "best_coverage": round(best_coverage, 4),
            "combined_top_3_coverage": round(combined_coverage, 4),
            "source_chunk_count": len(chunks),
        },
    )
