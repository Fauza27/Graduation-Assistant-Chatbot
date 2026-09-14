from unittest.mock import Mock, patch

from langchain_core.documents import Document

from src.retrieval.hybrid_search import HybridSearchResult
from src.retrieval.pipeline import run_retrieval


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
