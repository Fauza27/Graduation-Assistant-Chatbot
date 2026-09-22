"""Keep diagnostic claims and recommendation targets within observed evidence."""

from __future__ import annotations

import re

from src.evaluation_agent.models import Diagnosis, DiagnosisReview, FailureStage


def constrain_review(
    review: DiagnosisReview, preliminary: Diagnosis, system_context: dict
) -> DiagnosisReview:
    """LLM explains a trace finding; it cannot invent a different failure stage."""
    if preliminary.failed_stage in {FailureStage.AMBIGUOUS, FailureStage.UNKNOWN}:
        return DiagnosisReview(
            failed_stage=preliminary.failed_stage,
            root_cause=preliminary.root_cause,
            confidence=preliminary.confidence,
            recommendations=[],
        )
    allowed_files = {
        source["path"]
        for source in system_context.get("current_source_excerpts", [])
        if source.get("excerpts")
    }
    allowed_files.add("config/settings.py")
    allowed_settings = {
        name.lower() for name in system_context.get("current_configuration", {})
    }
    recommendations = []
    for item in review.recommendations:
        files = set(re.findall(r"[\w/]+\.py", item.target))
        setting = item.target.strip().lower()
        if (files and files.issubset(allowed_files)) or setting in allowed_settings:
            recommendations.append(item)
    # If the reviewer contradicts the deterministic finding, do not preserve its
    # unsupported explanation or actions while silently relabeling the stage.
    agrees = review.failed_stage == preliminary.failed_stage
    return DiagnosisReview(
        failed_stage=preliminary.failed_stage,
        root_cause=review.root_cause if agrees else preliminary.root_cause,
        confidence=min(review.confidence, preliminary.confidence),
        recommendations=recommendations[:2] if agrees else [],
    )
