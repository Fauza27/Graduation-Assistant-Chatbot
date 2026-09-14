"""Offline regressions for retrieval freshness across independent workers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.services import retrieval_cache as cache_module
from src.services.retrieval_cache import RevisionedRetrievalCache, read_knowledge_revision


@pytest.fixture
def revision_reader():
    return Mock(return_value=1)


def test_reuses_results_and_monitoring_only_at_current_revision(revision_reader):
    cache = RevisionedRetrievalCache(revision_reader)
    revision, entry = cache.lookup("syarat skripsi", "Apa persyaratannya?")
    assert entry is None

    documents = [{"parent_id": "p1", "content": "Lulus 120 SKS"}]
    metrics = {"retrieved_parent_ids": ["p1"], "num_docs_after_rerank": 1}
    assert cache.store_if_current(
        revision, "syarat skripsi", "Apa persyaratannya?", documents, metrics
    )

    _, cached = cache.lookup("syarat skripsi", "Apa persyaratannya?")
    assert cached.documents == documents
    assert cached.metrics == metrics
    # One lookup before each cache read, plus validation after retrieval.
    assert revision_reader.call_count == 3


@pytest.mark.parametrize("updated_documents", [[], [{"parent_id": "p1", "content": "Baru"}]])
def test_edit_or_delete_invalidates_cache_in_every_worker(revision_reader, updated_documents):
    workers = [RevisionedRetrievalCache(revision_reader) for _ in range(2)]
    for worker in workers:
        assert worker.store_if_current(
            1, "skripsi", "skripsi", [{"parent_id": "p1", "content": "Lama"}], {}
        )

    # A committed mutation performed by any process bumps the shared DB value.
    revision_reader.return_value = 2
    for worker in workers:
        revision, entry = worker.lookup("skripsi", "skripsi")
        assert revision == 2
        assert entry is None
        assert worker.store_if_current(
            revision, "skripsi", "skripsi", updated_documents, {}
        )
        _, entry = worker.lookup("skripsi", "skripsi")
        assert entry.documents == updated_documents


def test_change_during_retrieval_prevents_caching(revision_reader):
    cache = RevisionedRetrievalCache(revision_reader)
    revision, _ = cache.lookup("skripsi", "skripsi")
    revision_reader.return_value = 2

    assert not cache.store_if_current(
        revision, "skripsi", "skripsi", [{"content": "Possibly stale"}], {}
    )
    assert cache.lookup("skripsi", "skripsi") == (2, None)


def test_revision_failure_bypasses_even_an_existing_entry(revision_reader):
    cache = RevisionedRetrievalCache(revision_reader)
    assert cache.store_if_current(1, "skripsi", "skripsi", [{"content": "Old"}], {})
    revision_reader.side_effect = RuntimeError("Database unavailable")

    revision, entry = cache.lookup("skripsi", "skripsi")
    assert revision is None
    assert entry is None
    assert not cache.store_if_current(revision, "skripsi", "skripsi", [], {})


def test_revision_failure_after_retrieval_prevents_caching(revision_reader):
    cache = RevisionedRetrievalCache(revision_reader)
    revision, _ = cache.lookup("skripsi", "skripsi")
    revision_reader.side_effect = RuntimeError("Database unavailable")
    assert not cache.store_if_current(revision, "skripsi", "skripsi", [], {})

    revision_reader.side_effect = None
    assert cache.lookup("skripsi", "skripsi") == (1, None)


@pytest.mark.parametrize(
    ("resolved_query", "original_question"),
    [("syarat skripsi", "Berapa SKS?"), ("syarat KKP", "Apa persyaratannya?")],
)
def test_key_includes_both_retrieval_and_reranking_inputs(
    revision_reader, resolved_query, original_question
):
    cache = RevisionedRetrievalCache(revision_reader)
    assert cache.store_if_current(
        1, "syarat skripsi", "Apa persyaratannya?", [{"parent_id": "p1"}], {}
    )
    assert cache.lookup(resolved_query, original_question) == (1, None)


def test_mutating_generation_or_monitoring_data_does_not_poison_cache(revision_reader):
    cache = RevisionedRetrievalCache(revision_reader)
    documents = [{"parent_id": "p1", "pages": ["1"]}]
    metrics = {"retrieved_parent_ids": ["p1"]}
    cache.store_if_current(1, "skripsi", "skripsi", documents, metrics)
    documents[0]["pages"].append("2")
    metrics["retrieved_parent_ids"].append("p2")

    _, first_read = cache.lookup("skripsi", "skripsi")
    assert first_read.documents[0]["pages"] == ["1"]
    assert first_read.metrics["retrieved_parent_ids"] == ["p1"]
    first_read.documents.clear()
    first_read.metrics["retrieved_parent_ids"].clear()

    _, second_read = cache.lookup("skripsi", "skripsi")
    assert second_read.documents == [{"parent_id": "p1", "pages": ["1"]}]
    assert second_read.metrics == {"retrieved_parent_ids": ["p1"]}


def test_reads_singleton_revision_without_caching_database_value(monkeypatch):
    client = Mock()
    query = client.table.return_value.select.return_value.eq.return_value
    query.execute.side_effect = [
        SimpleNamespace(data=[{"revision": 12}]),
        SimpleNamespace(data=[{"revision": 13}]),
    ]
    monkeypatch.setattr(cache_module, "_get_supabase_client", lambda: client)

    assert read_knowledge_revision() == 12
    assert read_knowledge_revision() == 13
    client.table.assert_called_with("knowledge_base_revision")
    client.table.return_value.select.assert_called_with("revision")
    client.table.return_value.select.return_value.eq.assert_called_with("id", 1)


@pytest.mark.parametrize(
    "rows",
    [None, [], [{}], [{"revision": None}], [{"revision": -1}], [{"revision": True}],
     [{"revision": "1"}], [{"revision": 1}, {"revision": 2}]],
)
def test_missing_or_invalid_database_revision_is_rejected(monkeypatch, rows):
    client = Mock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=rows)
    )
    monkeypatch.setattr(cache_module, "_get_supabase_client", lambda: client)

    with pytest.raises(ValueError):
        read_knowledge_revision()
