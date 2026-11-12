"""Pre-evaluation plumbing checks; mocked answers are not accuracy results."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from src.api import ai
from src.generation import chain
from src.generation.memory import ConversationMemory
from src.generation.token_utils import count_tokens
from src.middleware.request_context import RequestContextMiddleware
from src.monitoring.context import clear_current, get_current, new_collector
from src.monitoring.errors import (
    RetrievalError, RequestDeadlineExceeded, SessionAccessError, SupabaseServiceError,
)
from src.monitoring.pipeline_snapshot import capture_pipeline_snapshot
from src.services import ai_services
from src.retrieval.query_planner import QueryPlan
from src.generation.intent_classifier.reformulator import RewriteMethod


def test_http_id_matches_the_recorded_chat_id(monkeypatch):
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.include_router(ai.router, prefix='/api')
    monkeypatch.setattr(ai, 'verify_access_token', lambda _: {'role': 'mahasiswa', 'sub': 'test-user'})
    monkeypatch.setattr(ai, 'check_and_update_quota', lambda **_: True)
    recorded = []

    def fake_chat(**kwargs):
        recorded.append(get_current().request_id)
        return {'request_id': recorded[-1], 'answer': 'Jawaban contoh', 'num_docs': 0, 'sources': []}

    monkeypatch.setattr(ai, 'chat_service', fake_chat)
    client = TestClient(app)
    headers = {'Authorization': 'Bearer test', 'X-Request-ID': 'client-reused-id'}
    first = client.post('/api/ai/chat', json={'query': 'Apa syarat PI?', 'session_id': 'session-test'}, headers=headers)
    second = client.post('/api/ai/chat', json={'query': 'Apa syarat KKP?', 'session_id': 'session-test'}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.headers['X-Request-ID'] == first.json()['request_id'] == recorded[0]
    assert second.headers['X-Request-ID'] == second.json()['request_id'] == recorded[1]
    assert recorded[0] != recorded[1]


def test_pipeline_snapshot_records_reranker_and_memory_implementation(mock_settings):
    mock_settings.reranker_enabled = False
    snapshot = capture_pipeline_snapshot(mock_settings)
    assert snapshot['reranker_enabled'] is False
    for path in ['src/generation/memory.py', 'src/generation/token_utils.py', 'src/services/chat_model.py', 'src/services/ai_services.py']:
        assert len(snapshot['implementation_checksums'][path]) == 64
    assert 'open_api_key' not in snapshot
    assert 'supabase_service_key' not in snapshot


def test_context_budget_and_trace_only_include_documents_sent_to_model(monkeypatch):
    monkeypatch.setattr(chain.settings, 'MAX_CONTEXT_TOKENS', 100)
    documents = [
        {'parent_id': 'pi-first', 'domain': 'PI', 'content': '漢字🚀' * 300},
        {'parent_id': 'kkp-not-sent', 'domain': 'KKP', 'content': 'UNSENT_EVIDENCE'},
    ]
    llm = Mock()
    llm.invoke.return_value = AIMessage(content='Sumber: Buku Panduan PI. Jawaban contoh.', usage_metadata={'input_tokens': 120, 'output_tokens': 10, 'total_tokens': 130})
    monkeypatch.setattr(chain, 'get_llm', lambda: llm)
    collector = new_collector('test-context', 'test')
    try:
        result = chain.RAGGenerator().generate('Pertanyaan contoh', documents)
        context = collector.final_context
        assert count_tokens(context['text']) <= 100
        assert context['text'].endswith('</UNTRUSTED_DOCUMENT>\n<END_UNTRUSTED_CONTEXT>')
        assert 'UNSENT_EVIDENCE' not in context['text']
        assert context['document_ids'] == ['pi-first']
        assert [s['parent_id'] for s in result['sources']] == ['pi-first']
    finally:
        clear_current()


def test_retrieval_error_does_not_leave_unanswered_turn_in_cached_memory(monkeypatch):
    memory = ConversationMemory(summary='Ringkasan sebelumnya')
    memory.add_user_turn('Apa itu PI?')
    memory.add_assistant_turn('Jawaban sebelumnya')
    before = memory.to_dict()
    monkeypatch.setattr(ai_services, 'get_or_create_memory', lambda *args, **kwargs: memory)
    monkeypatch.setattr(ai_services, 'build_query_plan', lambda q, _: QueryPlan(q, q, q, (q,), q, RewriteMethod.NONE))

    def fail(**kwargs):
        raise RetrievalError('mocked failure')

    monkeypatch.setattr(ai_services, '_get_retrieval_documents', fail)
    with pytest.raises(RetrievalError):
        ai_services.chat('Bagaimana prosedurnya?', 'test-memory', 'test-user')
    assert memory.to_dict() == before


def test_compaction_keeps_old_exchanges_when_no_summary_can_fit():
    memory = ConversationMemory(max_history_tokens=40, min_recent_turns=1, summary_max_tokens=10, summary='Ringkasan lama')
    memory.add_user_turn('Pertanyaan lama')
    memory.add_assistant_turn('Jawaban lama')
    memory.add_user_turn('Pertanyaan terbaru ' * 100)
    memory.add_assistant_turn('Jawaban terbaru ' * 100)
    before = memory.to_dict()
    memory.apply_summary('Ringkasan gabungan', memory.get_turns_to_summarize())
    assert memory.to_dict() == before


def test_service_keeps_generator_decision_to_omit_sources(monkeypatch):
    memory = ConversationMemory()
    monkeypatch.setattr(ai_services, 'get_or_create_memory', lambda *args, **kwargs: memory)
    monkeypatch.setattr(ai_services, '_get_retrieval_documents', lambda **_: [{'parent_id': 'parent-pi-1', 'content': 'Panduan'}])
    generator = Mock()
    generator.generate.return_value = {'answer': 'Halo juga!', 'sources': []}
    monkeypatch.setattr(ai_services, 'get_rag_generator', lambda: generator)
    monkeypatch.setattr(ai_services, '_persist_conversation', lambda **_: None)
    result = ai_services.chat('Halo teman', 'test-greeting', 'test-user')
    assert result['sources'] == []


def test_late_answer_after_timeout_is_not_committed_to_conversation(monkeypatch):
    memory = ConversationMemory()
    monkeypatch.setattr(ai_services, 'get_or_create_memory', lambda *args, **kwargs: memory)
    monkeypatch.setattr(ai_services, '_get_retrieval_documents', lambda **_: [])
    collector = new_collector('test-late', 'test')

    def late_answer(**kwargs):
        collector._response_abandoned.set()
        return {'answer': 'Late answer', 'sources': []}

    generator = Mock()
    generator.generate.side_effect = late_answer
    monkeypatch.setattr(ai_services, 'get_rag_generator', lambda: generator)
    save = Mock()
    monkeypatch.setattr(ai_services, '_persist_conversation', save)
    try:
        with pytest.raises(RequestDeadlineExceeded):
            ai_services.chat('Apa itu KKP?', 'test-late', 'test-user')
        save.assert_not_called()
        assert memory.is_empty
        assert collector.status == 'error'
    finally:
        clear_current()


def test_failed_session_save_is_not_reported_as_a_successful_chat(monkeypatch):
    memory = ConversationMemory()
    monkeypatch.setattr(ai_services, 'get_or_create_memory', lambda *args, **kwargs: memory)
    monkeypatch.setattr(ai_services, 'build_query_plan', lambda q, _: QueryPlan(q, q, q, (q,), q, RewriteMethod.NONE))
    monkeypatch.setattr(ai_services, '_get_retrieval_documents', lambda **_: [])
    generator = Mock()
    generator.generate.return_value = {'answer': 'Jawaban contoh', 'sources': []}
    monkeypatch.setattr(ai_services, 'get_rag_generator', lambda: generator)
    store = Mock()
    store.save_memory.side_effect = RuntimeError('mock storage unavailable')
    monkeypatch.setattr(ai_services, 'get_session_store_strategy', lambda: store)
    collector = new_collector('test-save-error', 'test')
    try:
        with pytest.raises(SupabaseServiceError):
            ai_services.chat('Apa syarat PI?', 'test-save-error', 'test-user', channel='website')
        assert collector.status == 'error'
        assert collector.error_source == 'supabase'
        assert collector.http_status == 503
        assert memory.is_empty
        store.log_chat_interaction.assert_not_called()
    finally:
        clear_current()


def test_save_preserves_session_ownership_errors(monkeypatch):
    store = Mock()
    store.save_memory.side_effect = SessionAccessError('owner', 'other')
    monkeypatch.setattr(ai_services, 'get_session_store_strategy', lambda: store)
    with pytest.raises(SessionAccessError):
        ai_services._save_memory_if_needed('test-owner', ConversationMemory())


def test_endpoint_reports_session_storage_failure_as_503(monkeypatch):
    app = FastAPI()
    app.include_router(ai.router, prefix='/api')
    monkeypatch.setattr(ai, 'verify_access_token', lambda _: {'role': 'mahasiswa', 'sub': 'test-user'})
    monkeypatch.setattr(ai, 'check_and_update_quota', lambda **_: True)
    monkeypatch.setattr(ai, 'persist_metrics', lambda _: None)

    def fail_chat(**kwargs):
        raise SupabaseServiceError('mock storage unavailable')

    monkeypatch.setattr(ai, 'chat_service', fail_chat)
    response = TestClient(app).post(
        '/api/ai/chat',
        json={'query': 'Apa syarat PI?', 'session_id': 'test-session'},
        headers={'Authorization': 'Bearer test'},
    )
    assert response.status_code == 503
    assert response.headers['Retry-After'] == '5'
