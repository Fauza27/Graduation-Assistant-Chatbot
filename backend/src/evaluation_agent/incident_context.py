"""Focus diagnostic review on observed transitions and score provenance."""

from __future__ import annotations

from src.evaluation_agent.models import ChunkAudit, Diagnosis


def build_incident_context(
    trace: dict, audit: ChunkAudit, diagnosis: Diagnosis
) -> dict:
    """Provide facts, not an oracle-based algorithm for future requests."""
    best_coverage = max((match.coverage for match in audit.matches), default=0)
    strongest = {
        match.parent_id for match in audit.matches if match.coverage == best_coverage
    }
    scored = trace.get("reranked_candidates", [])
    relevant = [row for row in scored if row.get("parent_id") in strongest]
    checks = diagnosis.diagnostics.get("rerank_gate_checks", [])
    return {
        "earliest_failed_stage": diagnosis.failed_stage.value,
        "observed_failure": diagnosis.root_cause,
        "strongest_evidence_parent_ids": sorted(strongest),
        "strongest_evidence_coverage": best_coverage,
        "strongest_evidence_rerank_results": relevant,
        "accepted_rerank_results": [row for row in scored if row.get("accepted")],
        "selection_counterfactuals": [
            check for check in checks if check["parent_id"] in strongest
        ],
        "missing_score_parent_ids": diagnosis.diagnostics.get(
            "parents_without_recorded_rerank_score", []
        ),
        "interpretation_rules": [
            "Evidence matches come from an offline audit; production cannot identify the correct parent using these IDs.",
            "A low rank/score despite full evidence suggests a scoring/input mismatch; a gate change alone does not repair ordering.",
            "Required gap and top-N are counterfactual bounds with unchanged scores, not recommended production values.",
            "A parent marked truncated=false cannot have lost its evidence to the recorded character limit; model tokenizer truncation is a separate unmeasured possibility.",
            "Full score coverage means no need to add score logging or increase rerank candidate count to score these same parents.",
            "RRF/search scores cannot be compared with cross-encoder thresholds.",
            "rerank_min_top_score applies to the highest candidate score, not to the score of every individual parent.",
            "Acceptance requires highest score >= minimum top score, parent score >= highest score - relative gap, and position within top-N among gap survivors; parent score > 0 alone is insufficient.",
        ],
    }
