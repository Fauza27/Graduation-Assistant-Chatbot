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
