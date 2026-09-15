import json
from types import SimpleNamespace

from langchain_core.documents import Document

from src.evaluation_agent.model_client import OpenAIEvaluatorModel
from src.evaluation_agent.incident_context import (
    build_incident_context,
    describe_reranking_failure,
    reranking_success_criteria,
)
from src.evaluation_agent.models import (
    ChunkAudit,
    Diagnosis,
    EvaluationCase,
)
from src.evaluation_agent.report import write_report, recommendation_summary
from src.evaluation_agent.system_context import build_system_context
from src.monitoring.pipeline_snapshot import capture_pipeline_snapshot
from src.retrieval import pipeline


def test_context_uses_safe_settings_and_distinguishes_historical_config(mock_settings):
    snapshot = capture_pipeline_snapshot(mock_settings)
    context = build_system_context(
        "reranking",
        {"pipeline_snapshot": {"rerank_top_n": 5, "open_api_key": "SECRET_SENTINEL"}},
        mock_settings,
    )

    encoded = json.dumps(context)
    assert "SECRET_SENTINEL" not in encoded
    assert mock_settings.open_api_key not in json.dumps(snapshot)
    assert context["request_configuration"]["rerank_top_n"] == 5
    assert context["current_configuration"]["rerank_top_n"] == 3
    assert context["source_matches_request"]["src/retrieval/pipeline.py"] is None
    sources = {source["path"]: source for source in context["current_source_excerpts"]}
    assert (
        "_select_reranked_documents"
        in sources["src/retrieval/pipeline.py"]["excerpts"][0]["code"]
    )
    assert context["setting_constraints"]["rerank_top_n"]["ge"] == 3
    assert context["current_configuration"]["rerank_max_content_chars"] == 2000


def test_incident_focuses_on_full_evidence_not_partial_matches():
    audit = ChunkAudit(
        status="chunking_valid",
        explanation="valid",
        matches=[
            {"child_id": "full", "parent_id": "full-parent", "coverage": 1.0},
            {"child_id": "partial", "parent_id": "partial-parent", "coverage": 0.8},
        ],
    )
    context = build_incident_context(
        {
            "reranked_candidates": [
                {
                    "parent_id": "full-parent",
                    "rerank_score": -1.5,
                    "rank": 7,
                    "accepted": False,
                },
                {
                    "parent_id": "partial-parent",
                    "rerank_score": 1.2,
                    "rank": 5,
                    "accepted": False,
                },
            ]
        },
        audit,
        Diagnosis(failed_stage="reranking", root_cause="Ditolak", confidence=0.9),
    )
    assert context["strongest_evidence_parent_ids"] == ["full-parent"]
    assert context["strongest_evidence_rerank_results"][0]["rank"] == 7


def test_review_receives_configuration_and_implementation(mock_settings):
    captured = {}

    class FakeLLM:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **kwargs):
            captured["prompt"] = messages[1].content
            return {
                "failed_stage": "reranking",
                "root_cause": "Bukti ditolak",
                "confidence": 0.9,
                "recommendations": [
                    {
                        "target": "reranker.py",
                        "action": "Tambahkan heading ke input",
                        "rationale": "Parent ranked low",
                        "validation_plan": "WRONG_CRITERION: score > 0 is sufficient",
                        "risk": "medium",
                    }
                ],
            }

    model = object.__new__(OpenAIEvaluatorModel)
    model._llm = FakeLLM()
    context = build_system_context("reranking", {}, mock_settings)
    review = model.review_diagnosis(
        case=EvaluationCase(
            case_id="case", question="Syarat?", review_status="incorrect"
        ),
        evidence_text="Bukti",
        chunk_audit=ChunkAudit(status="chunking_valid", explanation="valid"),
        trace={},
        preliminary=Diagnosis(
            failed_stage="reranking", root_cause="Ditolak", confidence=0.9
        ),
        system_context=context,
    )

    payload = json.loads(captured["prompt"].split("DATA:\n", 1)[1])
    assert payload["system_context"]["current_configuration"]["rerank_top_n"] == 3
    assert payload["system_context"]["current_source_excerpts"]
    assert "WRONG_CRITERION" not in review.recommendations[0].validation_plan
    assert (
        "skor parent >= skor tertinggi - rerank_relative_gap"
        in review.recommendations[0].validation_plan
    )


def test_failure_reason_uses_recorded_rejection_and_does_not_guess_missing_scores():
    row = {"parent_id": "parent", "title": "Ketentuan Profesional", "accepted": False}
    gate = {
        "parent_id": "parent",
        "rerank_rank": 7,
        "rerank_score": -1.5,
        "acceptance_threshold_at_request": 2.53,
        "top_score_passes_minimum_gate": True,
    }
    facts = {
        "strongest_evidence_rerank_results": [row],
        "selection_counterfactuals": [gate],
    }
    reason = describe_reranking_failure(facts)
    assert "Ketentuan Profesional" in reason
    assert "peringkat 7" in reason
    assert "(-1.50)" in reason and "(2.53)" in reason
    assert describe_reranking_failure({}) is None
    row["accepted"] = True
    assert describe_reranking_failure(facts) is None


def test_rerank_validation_uses_actual_gate_contract_and_expected_answer():
    case = EvaluationCase(
        case_id="case",
        question="Syarat?",
        review_status="incorrect",
        expected_answer="Tiga syarat",
    )
    criteria = reranking_success_criteria(
        case,
        {
            "current_configuration": {
                "rerank_min_top_score": 0,
                "rerank_relative_gap": 2.5,
                "rerank_top_n": 5,
            }
        },
        {"strongest_evidence_parent_ids": ["parent-027"]},
    )
    text = "\n".join(criteria)
    assert "rerank_relative_gap=2.5" in text
    assert "rerank_top_n=5" in text
    assert "skor parent >= skor tertinggi - rerank_relative_gap" in text
    assert "parent-027" in text
    assert "expected_answer: Tiga syarat" in text
    assert "kasus tanpa jawaban" in text


def test_report_shows_cause_and_action_and_retains_debug_details_in_json(tmp_path):
    path = write_report(
        "run",
        [
            {
                "question": "Syarat?",
                "answer_available": True,
                "diagnosis": {
                    "failed_stage": "reranking",
                    "confidence": 0.9,
                    "root_cause": "Ditolak",
                    "recommendations": [
                        {
                            "target": "pipeline.py",
                            "action": "Replay skor",
                            "rationale": "Parent ditemukan rank 3",
                            "risk": "low",
                            "validation_plan": "Bukti harus masuk context",
                        }
                    ],
                },
            }
        ],
        tmp_path,
    )
    text = path.read_text(encoding="utf-8")
    assert "Alasan gagal:** Ditolak" in text
    assert "Replay skor" in text
    assert "Parent ditemukan rank 3" not in text
    assert "Bukti harus masuk context" not in text
    saved = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert (
        saved["results"][0]["diagnosis"]["recommendations"][0]["validation_plan"]
        == "Bukti harus masuk context"
    )


def test_pipeline_records_all_scores_without_changing_final_selection(monkeypatch):
    from src.retrieval.reranker import CrossEncoderReranker
    from src.retrieval.self_query import ParsedQuery
    from src.services import ai_services

    settings = SimpleNamespace(
        max_parent_for_rerank=6,
        min_parent_for_rerank=1,
        rerank_top_n=3,
        rerank_min_top_score=0,
        rerank_relative_gap=2.5,
    )
    children = [
        SimpleNamespace(
            child_id=f"child-{i}",
            parent_id=f"parent-{i}",
            hybrid_score=6 - i,
            score_source="rrf",
            document=Document(page_content="isi", metadata={}),
        )
        for i in range(6)
    ]
    parents = [
        {"parent_id": f"parent-{i}", "content": "isi", "best_child_score": 6 - i}
        for i in range(6)
    ]
    captured = {}

    def score_all(self, query, documents, top_n):
        assert top_n == 6
        return [
            {**doc, "cross_encoder_score": 5 - i} for i, doc in enumerate(documents)
        ]

    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)
    monkeypatch.setattr(pipeline, "set_field", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(
        ai_services,
        "_get_hybrid_searcher",
        lambda: SimpleNamespace(search=lambda **kw: children),
    )
    monkeypatch.setattr(
        ai_services,
        "_get_parent_child_fetcher",
        lambda: SimpleNamespace(fetch_parents=lambda rows: parents),
    )
    monkeypatch.setattr(
        "src.retrieval.self_query.extract_query_components",
        lambda q: ParsedQuery(semantic_query=q),
    )
    monkeypatch.setattr(CrossEncoderReranker, "rerank", score_all)

    result = pipeline.run_retrieval("Syarat?")

    assert [doc["parent_id"] for doc in result.parent_documents] == [
        "parent-0",
        "parent-1",
        "parent-2",
    ]
    assert len(captured["reranked_candidates"]) == 6
    assert captured["reranked_candidates"][-1]["selection_reason"] == "relative_gap"
    assert captured["reranked_candidates"][-1]["accepted"] is False


def test_empty_acceptance_set_does_not_mark_rejected_parents_accepted():
    rows = pipeline._serialize_parent_candidates(
        [{"parent_id": "parent"}], accepted_ids=set()
    )
    assert rows[0]["accepted"] is False


def test_report_supports_recommendations_from_older_verbose_runs():
    action = "Saat ini: content\n\nUsulan: Tambahkan title dan section.\n\nLangkah implementasi:\n1. Update fungsi\n\nRollback: reset"
    assert recommendation_summary(action) == "Tambahkan title dan section."
