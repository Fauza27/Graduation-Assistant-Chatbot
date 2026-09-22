from src.evaluation_agent.models import ChunkAudit, FailureStage
from src.evaluation_agent.trace_analyzer import analyze_trace, analyze_query_scope
from src.evaluation_agent.models import EvaluationCase


def _valid_audit() -> ChunkAudit:
    return ChunkAudit(
        status="chunking_valid",
        explanation="valid",
        affected_chunk_ids=["child-1"],
        matched_parent_ids=["parent-1"],
    )


def test_trace_analyzer_identifies_reranker_failure():
    trace = {
        "search_candidates": [{"child_id": "child-1", "parent_id": "parent-1"}],
        "parent_candidates": [{"parent_id": "parent-1"}],
        "reranked_candidates": [{"parent_id": "parent-1", "accepted": False}],
        "final_context": {"document_ids": []},
    }

    result = analyze_trace(
        answer_available=True, chunk_audit=_valid_audit(), trace=trace
    )

    assert result.failed_stage is FailureStage.RERANKING


def test_trace_analyzer_identifies_generation_failure():
    trace = {
        "search_candidates": [{"child_id": "child-1", "parent_id": "parent-1"}],
        "parent_candidates": [{"parent_id": "parent-1"}],
        "reranked_candidates": [{"parent_id": "parent-1", "accepted": True}],
        "final_context": {"document_ids": ["parent-1"]},
    }

    result = analyze_trace(
        answer_available=True, chunk_audit=_valid_audit(), trace=trace
    )

    assert result.failed_stage is FailureStage.GENERATION


def test_trace_analyzer_stops_at_chunking_before_retrieval():
    audit = ChunkAudit(status="context_split", explanation="Bukti terpisah")

    result = analyze_trace(answer_available=True, chunk_audit=audit, trace={})

    assert result.failed_stage is FailureStage.CHUNKING


def test_trace_analyzer_marks_related_scope_abstention_as_ambiguous():
    result = analyze_trace(
        answer_available=False,
        chunk_audit=ChunkAudit(status="not_applicable", explanation="Tidak langsung"),
        trace={},
        queue_reason="answer_abstention",
        has_related_scope_evidence=True,
    )

    assert result.failed_stage is FailureStage.AMBIGUOUS
    assert result.diagnostics["queue_reason"] == "answer_abstention"


def test_trace_analyzer_does_not_treat_inconclusive_search_as_missing_information():
    result = analyze_trace(
        answer_available=False,
        chunk_audit=ChunkAudit(status="not_applicable", explanation="Belum ada bukti"),
        trace={},
        evidence_discovery_status="inconclusive",
    )

    assert result.failed_stage is FailureStage.AMBIGUOUS
    assert result.confidence < 0.5
    assert "belum membuktikan" in result.root_cause


def test_rerank_diagnostics_distinguish_gap_and_top_n_from_rrf_scores():
    trace = {
        "search_candidates": [
            {"child_id": "child-1", "parent_id": "parent-1", "score": 0.011}
        ],
        "parent_candidates": [{"parent_id": "parent-1"}],
        "reranked_candidates": [
            {
                "parent_id": "other",
                "rank": 1,
                "rerank_score": 5.0,
                "score_source": "cross_encoder",
                "accepted": True,
            },
            {
                "parent_id": "parent-1",
                "rank": 7,
                "rerank_score": -1.5,
                "score_source": "cross_encoder",
                "accepted": False,
            },
        ],
        "pipeline_snapshot": {"rerank_relative_gap": 2.5, "rerank_top_n": 5},
        "final_context": {"document_ids": ["other"]},
    }
    result = analyze_trace(
        answer_available=True, chunk_audit=_valid_audit(), trace=trace
    )
    checks = result.diagnostics["rerank_gate_checks"][0]
    assert checks["required_gap_if_scores_unchanged"] == 6.5
    assert checks["required_top_n_if_order_unchanged"] == 7
    assert checks["request_relative_gap"] == 2.5
    assert checks["acceptance_threshold_at_request"] == 2.5


def test_sibling_child_can_retrieve_a_parent_containing_the_evidence():
    trace = {
        "search_candidates": [{"child_id": "sibling", "parent_id": "parent-1"}],
        "parent_candidates": [{"parent_id": "parent-1"}],
        "reranked_candidates": [{"parent_id": "parent-1", "accepted": False}],
        "final_context": {"document_ids": []},
    }
    result = analyze_trace(
        answer_available=True, chunk_audit=_valid_audit(), trace=trace
    )
    assert result.failed_stage is FailureStage.RERANKING


def test_filter_presence_is_not_proof_of_a_query_processing_bug():
    result = analyze_trace(
        answer_available=True,
        chunk_audit=_valid_audit(),
        trace={
            "self_query_results": [{"filters": {"source": "Panduan PI"}}],
            "search_candidates": [],
            "parent_candidates": [],
        },
    )
    assert result.failed_stage is FailureStage.RETRIEVAL


def test_missing_trace_fields_are_not_treated_as_empty_successful_stages():
    result = analyze_trace(
        answer_available=True,
        chunk_audit=_valid_audit(),
        trace={"query_plan": {"resolved_query": "PI"}},
    )
    assert result.failed_stage is FailureStage.UNKNOWN


def test_wrong_kkp_rewrite_is_detected_from_original_publication_context():
    case = EvaluationCase(
        case_id="loa",
        question="kalau baru LoA boleh?",
        review_status="unreviewed",
        prior_questions=["non skripsi jalur karya ilmiah syaratnya apa?"],
    )
    finding = analyze_query_scope(
        case, {"query_plan": {"resolved_query": "LoA terkait KKP"}}
    )
    assert finding.failed_stage is FailureStage.QUERY_PROCESSING
    assert finding.diagnostics["intended_domains"] == ["NON_SKRIPSI"]


def test_matching_domain_does_not_prove_query_processing_failure():
    case = EvaluationCase(
        case_id="sks", question="berapa SKS PI?", review_status="unreviewed"
    )
    assert (
        analyze_query_scope(
            case, {"query_plan": {"resolved_query": "minimal SKS Penulisan Ilmiah"}}
        )
        is None
    )
