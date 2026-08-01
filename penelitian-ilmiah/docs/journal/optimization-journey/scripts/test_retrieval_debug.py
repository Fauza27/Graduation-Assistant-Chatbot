"""
Test retrieval pipeline untuk debug pertanyaan yang gagal.
"""

from src.retrieval.self_query import extract_query_components
from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.parent_child import ParentChildFetcher
from src.retrieval.reranker import CrossEncoderReranker

def test_single_question(question: str):
    """Test retrieval untuk satu pertanyaan."""
    
    print("=" * 80)
    print(f"QUESTION: {question}")
    print("=" * 80)
    
    # ── TAHAP 1: Self-Query ─────────────────────────────────
    print("\n[1] SELF-QUERY EXTRACTION")
    print("-" * 80)
    
    parsed = extract_query_components(question)
    print(f"Original query : {parsed.original_query}")
    print(f"Semantic query : {parsed.semantic_query}")
    print(f"Filters        : {parsed.filters}")
    
    # ── TAHAP 2: Hybrid Search ──────────────────────────────
    print("\n[2] HYBRID SEARCH")
    print("-" * 80)
    
    searcher = HybridSearcher()
    search_results = searcher.search(
        query=parsed.semantic_query,
        filters=parsed.filters,
    )
    
    print(f"Total results: {len(search_results)}")
    print("\nTop 10 results:")
    for i, r in enumerate(search_results[:10], 1):
        title = r.document.metadata.get("title", "")[:60]
        print(f"  [{i:2d}] {r.child_id:8s} | hybrid={r.hybrid_score:.4f}")
        print(f"       {title}")
        # Print snippet dari content
        content_snippet = r.document.page_content[:150].replace('\n', ' ')
        print(f"       Content: {content_snippet}...")
        print()
    
    if not search_results:
        print("❌ NO RESULTS FOUND!")
        return
    
    # ── TAHAP 3: Parent-Child Fetching ──────────────────────
    print("\n[3] PARENT-CHILD FETCHING")
    print("-" * 80)
    
    fetcher = ParentChildFetcher()
    parent_results = fetcher.fetch_parents(search_results)
    
    print(f"Total parents: {len(parent_results)}")
    for i, p in enumerate(parent_results, 1):
        print(f"  [{i}] {p['parent_id']:15s} | {p['title'][:50]}")
        print(f"      Children: {p.get('matched_children', [])}")
    
    # ── TAHAP 4: Cross-Encoder Reranking ────────────────────
    print("\n[4] CROSS-ENCODER RERANKING")
    print("-" * 80)
    
    reranker = CrossEncoderReranker()
    reranked_parents = reranker.rerank(
        query=question,
        documents=parent_results,
    )
    
    print(f"Total reranked: {len(reranked_parents)}")
    for i, p in enumerate(reranked_parents, 1):
        ce_score = p.get("cross_encoder_score", 0)
        print(f"  [{i}] {p['parent_id']:15s} | CE={ce_score:.4f} | {p['title'][:50]}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    # Test pertanyaan yang gagal (context_recall = 0.0)
    test_questions = [
        "Apa saja berkas yang harus dilampirkan saat mendaftar ujian PI?",
        "Bagaimana pakaian yang harus dikenakan pria saat ujian PI?",
        "Berapa jumlah minimal halaman untuk laporan PI?",
    ]
    
    for q in test_questions:
        test_single_question(q)
        print("\n\n")
