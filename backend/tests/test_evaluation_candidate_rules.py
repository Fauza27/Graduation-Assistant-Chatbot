from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.evaluation_agent.candidate_rules import detect_auto_candidate
from src.monitoring.context import RequestMetricsCollector
from src.monitoring.writer import persist_auto_evaluation_candidate


def _collector(**updates) -> RequestMetricsCollector:
    collector = RequestMetricsCollector(
        question="Apa syarat KKP?",
        status="success",
    )
    for field, value in updates.items():
        setattr(collector, field, value)
    return collector


def test_no_relevant_document_becomes_automatic_candidate():
    decision = detect_auto_candidate(_collector(is_no_relevant_doc=True))

    assert decision is not None
    assert decision.reason_code == "no_relevant_document"


def test_reranker_rejection_has_specific_reason():
    decision = detect_auto_candidate(
        _collector(
            is_no_relevant_doc=True,
            num_docs_retrieved=5,
            num_docs_after_rerank=0,
        )
    )

    assert decision is not None
    assert decision.reason_code == "all_candidates_rejected"


def test_retrieval_error_becomes_automatic_candidate():
    decision = detect_auto_candidate(
        _collector(status="error", error_source="retrieval")
    )

    assert decision is not None
    assert decision.reason_code == "retrieval_error"


def test_successful_retrieval_and_non_rag_errors_are_ignored():
    assert detect_auto_candidate(_collector()) is None
    assert (
        detect_auto_candidate(_collector(status="error", error_source="authentication"))
        is None
    )


def test_automatic_candidate_insert_does_not_overwrite_admin_review():
    collector = _collector(is_no_relevant_doc=True, answer="Tidak ditemukan.")
    client = Mock()
    table = Mock()
    client.table.return_value = table
    table.upsert.return_value.execute.return_value = Mock(data=[])

    with (
        patch(
            "src.monitoring.writer.get_settings",
            return_value=SimpleNamespace(EVALUATION_AGENT_ENABLED=True),
        ),
        patch("src.monitoring.writer._get_supabase_client", return_value=client),
    ):
        persist_auto_evaluation_candidate(collector)

    payload = table.upsert.call_args.args[0]
    assert payload["review_status"] == "unreviewed"
    assert payload["created_by"] == "system:auto:no_relevant_document"
    assert table.upsert.call_args.kwargs == {
        "on_conflict": "request_id",
        "ignore_duplicates": True,
    }
