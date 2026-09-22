from src.evaluation_agent.models import EvaluationCase, InformationNeed, QuestionPlan
from src.evaluation_agent.question_planner import normalize_question_plan


DOMAINS = ["PI", "KKP", "SKRIPSI", "NON_SKRIPSI"]


def test_comparison_keeps_every_referenced_document_and_need():
    case = EvaluationCase(
        case_id="compare",
        question="kalau KKP sama juga?",
        review_status="unreviewed",
        prior_questions=["kalau PI minimal SKS dan IPK berapa?"],
    )
    raw = QuestionPlan(
        case_id=case.case_id,
        resolved_question="Apakah syarat KKP sama dengan PI?",
        target_domains=["KKP"],
        information_needs=[
            InformationNeed(
                need_id="need_1",
                description="Syarat KKP",
                domains=["KKP"],
            )
        ],
        question_type="comparison",
        confidence=0.95,
    )

    plan = normalize_question_plan(raw, case, DOMAINS)

    assert plan.target_domains == ["KKP", "PI"]
    assert {domain for need in plan.information_needs for domain in need.domains} == {
        "PI",
        "KKP",
    }


def test_low_confidence_route_searches_all_guides_as_fallback():
    case = EvaluationCase(
        case_id="ambiguous",
        question="yang bisa tanpa instansi yang mana tadi?",
        review_status="unreviewed",
    )
    raw = QuestionPlan(
        case_id=case.case_id,
        resolved_question=case.question,
        target_domains=["SKRIPSI"],
        information_needs=[],
        is_ambiguous=True,
        ambiguity_reason="Rujukan tidak jelas.",
        confidence=0.4,
    )

    plan = normalize_question_plan(raw, case, DOMAINS)

    assert set(plan.target_domains) == set(DOMAINS)


def test_explicit_domain_cannot_be_removed_by_model_route():
    case = EvaluationCase(
        case_id="explicit",
        question="minimal SKS PI berapa?",
        review_status="unreviewed",
    )
    raw = QuestionPlan(
        case_id=case.case_id,
        resolved_question=case.question,
        target_domains=["KKP"],
        information_needs=[],
        confidence=0.9,
    )

    plan = normalize_question_plan(raw, case, DOMAINS)

    assert "PI" in plan.target_domains
