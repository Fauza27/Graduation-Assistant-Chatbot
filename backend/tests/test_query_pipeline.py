from unittest.mock import Mock, patch
from types import SimpleNamespace

from langchain_core.documents import Document

from src.retrieval.hybrid_search import HybridSearchResult
from src.retrieval.pipeline import (
    _deduplicate_equivalent_child_content,
    _select_reranked_documents,
    run_retrieval,
)


def _child(child_id: str, parent_id: str, score: float) -> HybridSearchResult:
    return HybridSearchResult(
        document=Document(
            page_content=f"Isi {child_id}",
            metadata={"child_id": child_id, "parent_id": parent_id},
        ),
        hybrid_score=score,
        child_id=child_id,
        parent_id=parent_id,
    )


@patch("src.services.ai_services._get_parent_child_fetcher")
@patch("src.services.ai_services._get_hybrid_searcher")
def test_multi_query_results_are_merged_before_parent_fetch(
    get_searcher: Mock,
    get_fetcher: Mock,
):
    searcher = get_searcher.return_value
    searcher.search.side_effect = [
        [_child("c1", "p1", 0.8), _child("c2", "p2", 0.7)],
        [_child("c1", "p1", 0.9), _child("c3", "p2", 0.6)],
    ]

    fetcher = get_fetcher.return_value
    fetcher.fetch_parents.return_value = [
        {"parent_id": "p1", "content": "Syarat", "best_child_score": 0.9},
        {"parent_id": "p2", "content": "Prosedur", "best_child_score": 0.7},
    ]

    result = run_retrieval(
        query="syarat skripsi dan prosedur pendadaran",
        rerank_query="Apa syarat skripsi dan bagaimana pendadarannya?",
        search_queries=("syarat skripsi", "prosedur pendadaran"),
    )

    assert searcher.search.call_count == 2
    merged_children = fetcher.fetch_parents.call_args.args[0]
    assert [child.child_id for child in merged_children] == ["c1", "c2", "c3"]
    assert merged_children[0].hybrid_score > merged_children[1].hybrid_score
    assert merged_children[0].score_source == "multi_query_rrf"
    assert result.num_docs == 2


def test_identical_rules_in_different_guides_keep_both_sources():
    first = _child("pi-format", "pi-parent", 0.9)
    second = _child("kkp-format", "kkp-parent", 0.8)
    distinct = _child("distinct", "other-parent", 0.7)
    first.document.page_content = "Margin kiri empat sentimeter"
    second.document.page_content = "  MARGIN kiri   empat SENTIMETER "

    result = _deduplicate_equivalent_child_content([first, second, distinct])

    assert [child.child_id for child in result] == ["pi-format", "kkp-format", "distinct"]


def test_negative_rerank_score_does_not_prove_missing_information():
    settings = SimpleNamespace(
        rerank_min_top_score=None, rerank_relative_gap=2.5, rerank_top_n=5,
    )
    evidence = {"parent_id": "requirements", "cross_encoder_score": -3.82}
    other = {"parent_id": "unrelated", "cross_encoder_score": -8.0}
    selected, _, _ = _select_reranked_documents([evidence, other], settings)
    assert selected == [evidence]
    assert other["selection_reason"] == "relative_gap"

    settings.rerank_min_top_score = 0.0
    selected, _, _ = _select_reranked_documents([evidence, other], settings)
    assert selected == []


def test_repeated_content_within_one_parent_is_deduplicated():
    first = _child("c1", "p1", 0.9)
    second = _child("c2", "p1", 0.8)
    second.document.page_content = first.document.page_content
    assert _deduplicate_equivalent_child_content([first, second]) == [first]
