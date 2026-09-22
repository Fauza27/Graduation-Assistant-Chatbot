import json

import pytest

from src.evaluation_agent.model_client import OpenAIEvaluatorModel
from src.evaluation_agent.models import (
    EvaluationCase,
    EvidenceDecision,
    PageWindow,
    QuestionPlanBatch,
)


@pytest.mark.parametrize(
    "verdict", ["supported", "partial", "related_scope", "not_found"]
)
def test_one_verdict_drives_consistent_evidence_flags(verdict):
    captured = {}

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is EvidenceDecision
            return self

        def invoke(self, messages):
            captured.update(json.loads(messages[1].content.split("DATA:\n", 1)[1]))
            return dict(
                explanation="Sesuai sumber.",
                quote="minimal 100 SKS",
                page_start=15,
                page_end=15,
                reference_answer="100 SKS",
                verdict=verdict,
                scope_note="",
                covered_need_ids=["need_1"] if verdict == "supported" else [],
                subject_matches=True,
                attribute_matches=True,
                scope_matches=True,
                unit_matches=True,
                confidence=0.9,
            )

    model = object.__new__(OpenAIEvaluatorModel)
    model._llm = FakeLLM()
    case = EvaluationCase(
        case_id="pi",
        question="minimal SKS PI berapa?",
        standalone_question="syarat KKP",
        review_status="unreviewed",
    )
    window = PageWindow(
        document_slug="pi",
        document_title="Panduan PI",
        version_id="v",
        page_start=15,
        page_end=15,
        text="minimal 100 SKS",
    )
    result = model.verify_evidence(case, window, "candidate hint")
    assert (
        result.answers_question == result.answer_available == (verdict == "supported")
    )
    assert result.is_related_scope == (verdict in {"partial", "related_scope"})
    assert "KKP" not in json.dumps(captured)
    assert captured["academic_domains"] == ["PI"]


def test_question_planner_can_route_one_question_to_multiple_documents():
    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is QuestionPlanBatch
            return self

        def invoke(self, messages):
            return {
                "plans": [
                    {
                        "case_id": "compare",
                        "resolved_question": "Apakah persyaratan PI dan KKP sama?",
                        "target_domains": ["PI", "KKP"],
                        "information_needs": [
                            {
                                "need_id": "pi_requirement",
                                "description": "Persyaratan PI",
                                "domains": ["PI"],
                            },
                            {
                                "need_id": "kkp_requirement",
                                "description": "Persyaratan KKP",
                                "domains": ["KKP"],
                            },
                        ],
                        "question_type": "comparison",
                        "is_ambiguous": False,
                        "ambiguity_reason": "",
                        "confidence": 0.95,
                    }
                ]
            }

    model = object.__new__(OpenAIEvaluatorModel)
    model._llm = FakeLLM()
    case = EvaluationCase(
        case_id="compare",
        question="kalau KKP sama juga?",
        review_status="unreviewed",
        prior_questions=["PI minimal SKS dan IPK berapa?"],
    )

    plans = model.plan_questions([case], ["PI", "KKP"])

    assert plans[0].target_domains == ["PI", "KKP"]
    assert len(plans[0].information_needs) == 2
