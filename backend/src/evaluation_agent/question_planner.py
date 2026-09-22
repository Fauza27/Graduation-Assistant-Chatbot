"""Normalize question understanding into safe, soft document routes."""

from __future__ import annotations

import re
from collections.abc import Iterable

from src.evaluation_agent.evidence_search import domains_in_text, infer_domains
from src.evaluation_agent.models import EvaluationCase, InformationNeed, QuestionPlan


COMPARISON_MARKERS = (
    "sama juga",
    "sama kayak",
    "apakah sama",
    "beda",
    "dibanding",
    "mana yang",
    "yang mana",
    "keduanya",
)
LOW_CONFIDENCE_THRESHOLD = 0.65


def fallback_question_plan(
    case: EvaluationCase, available_domains: Iterable[str]
) -> QuestionPlan:
    """Create a conservative plan when semantic planning is unavailable."""

    allowed = set(available_domains)
    inferred = infer_domains(case)
    question_type = _question_type(case.question)
    if question_type == "comparison":
        inferred.update(_context_domains(case))
    targets = sorted(inferred or allowed)
    resolved = case.question.strip()
    needs = _fallback_needs(resolved, targets, question_type)
    return QuestionPlan(
        case_id=case.case_id,
        resolved_question=resolved,
        target_domains=targets,
        information_needs=needs,
        question_type=question_type,
        is_ambiguous=not bool(inferred),
        ambiguity_reason=(
            "Dokumen tujuan tidak dapat ditentukan secara pasti dari pertanyaan dan konteks."
            if not inferred
            else ""
        ),
        confidence=0.45 if not inferred else 0.75,
    )


def normalize_question_plan(
    plan: QuestionPlan,
    case: EvaluationCase,
    available_domains: Iterable[str],
) -> QuestionPlan:
    """Keep model routing inside the manifest and prevent hard false exclusions."""

    allowed = set(available_domains)
    explicit = domains_in_text(case.question).intersection(allowed)
    contextual = _context_domains(case).intersection(allowed)
    heuristic = infer_domains(case).intersection(allowed)
    targets = set(plan.target_domains).intersection(allowed)
    if explicit:
        targets = set(explicit)

    question_type = plan.question_type
    if _question_type(case.question) == "comparison":
        question_type = "comparison"
        targets.update(contextual)

    # Low-confidence routing is deliberately soft: searching an extra guide is
    # cheaper than incorrectly declaring that its evidence does not exist.
    unresolved_shared_term = not explicit and len(heuristic) > 1
    if unresolved_shared_term:
        targets.update(heuristic)
    is_ambiguous = (
        plan.is_ambiguous
        or plan.confidence < LOW_CONFIDENCE_THRESHOLD
        or unresolved_shared_term
    )
    if is_ambiguous:
        targets.update(contextual)
        targets.update(allowed)
    if not targets:
        targets.update(infer_domains(case).intersection(allowed) or allowed)

    needs = _normalize_needs(plan.information_needs, targets)
    needs_per_document = len(targets) > 1 and (
        question_type == "comparison" or len(explicit) > 1
    )
    if needs_per_document:
        represented_domains = {
            domain for need in needs for domain in need.domains
        }
        if represented_domains != targets or len(needs) < len(targets):
            needs = _fallback_needs(
                plan.resolved_question, sorted(targets), "comparison"
            )
    if not needs:
        needs = _fallback_needs(plan.resolved_question, sorted(targets), question_type)

    return plan.model_copy(
        update={
            "case_id": case.case_id,
            "resolved_question": plan.resolved_question.strip() or case.question.strip(),
            "target_domains": sorted(targets),
            "information_needs": needs,
            "question_type": question_type,
            "is_ambiguous": is_ambiguous,
        }
    )


def required_need_ids(plan: QuestionPlan) -> set[str]:
    return {need.need_id for need in plan.information_needs}


def _question_type(question: str) -> str:
    lowered = " ".join(question.lower().split())
    if any(marker in lowered for marker in COMPARISON_MARKERS):
        return "comparison"
    if any(marker in lowered for marker in ("ada nggak", "ada tidak", "tersedia")):
        return "availability"
    return "single_fact"


def _context_domains(case: EvaluationCase) -> set[str]:
    questions = [*case.prior_questions[-5:], case.question]
    domains: set[str] = set()
    for question in questions:
        domains.update(domains_in_text(question))
    return domains


def _normalize_needs(
    needs: list[InformationNeed], target_domains: set[str]
) -> list[InformationNeed]:
    normalized: list[InformationNeed] = []
    used_ids: set[str] = set()
    for index, need in enumerate(needs, start=1):
        description = " ".join(need.description.split())
        if not description:
            continue
        base_id = re.sub(r"[^a-z0-9_]+", "_", need.need_id.lower()).strip("_")
        base_id = base_id or f"need_{index}"
        need_id = base_id
        suffix = 2
        while need_id in used_ids:
            need_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(need_id)
        domains = sorted(set(need.domains).intersection(target_domains))
        normalized.append(
            need.model_copy(update={"need_id": need_id, "domains": domains})
        )
    return normalized


def _fallback_needs(
    resolved_question: str, target_domains: list[str], question_type: str
) -> list[InformationNeed]:
    if question_type == "comparison" and len(target_domains) > 1:
        return [
            InformationNeed(
                need_id=f"need_{index}",
                description=f"Informasi {domain} untuk menjawab: {resolved_question}",
                domains=[domain],
            )
            for index, domain in enumerate(target_domains, start=1)
        ]
    return [
        InformationNeed(
            need_id="need_1",
            description=resolved_question,
            domains=target_domains,
        )
    ]
