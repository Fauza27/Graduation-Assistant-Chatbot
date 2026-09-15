from src.evaluation_agent.models import ChunkAudit, FailureStage
from src.evaluation_agent.trace_analyzer import analyze_trace


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
