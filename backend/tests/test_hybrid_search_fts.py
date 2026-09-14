"""
Unit tests for hybrid_search.py FTS fallback when embedding is None.
"""

from unittest.mock import Mock, patch
from src.retrieval.hybrid_search import HybridSearcher


class TestHybridSearchFTSFallback:

    @patch.object(HybridSearcher, "_create_embedding")
    @patch.object(HybridSearcher, "_fts_fallback")
    def test_search_falls_back_to_fts_when_embedding_fails(
        self,
        mock_fts_fallback,
        mock_create_embedding,
    ):
        """Saat embedding gagal (None), search memanggil _fts_fallback alih-alih mengembalikan list kosong."""
        mock_create_embedding.return_value = None
        mock_fts_fallback.return_value = [
            {
                "id": "child_1",
                "parent_id": "parent_1",
                "title": "Bab 1",
                "content": "Isi dokumen panduan",
                "section": "BAB I",
                "pages": ["1", "2"],
                "source": "panduan_skripsi.pdf",
                "metadata": {},
                "fts_rank": 0.85,
                "rrf_score": 0.85,
            }
        ]

        searcher = HybridSearcher(supabase_client=Mock())
        results = searcher.search(query="syarat skripsi")

        mock_create_embedding.assert_called_once()
        mock_fts_fallback.assert_called_once()
        assert len(results) == 1
        assert results[0].child_id == "child_1"
        assert results[0].score_source == "fts_only_fallback"

    def test_fts_fallback_normalizes_fts_rank(self):
        """_fts_fallback mengonversi kolom fts_rank menjadi rrf_score untuk kompatibilitas downstream."""
        mock_sb = Mock()
        mock_rpc = Mock()
        mock_rpc.execute.return_value = Mock(
            data=[
                {
                    "id": "c1",
                    "parent_id": "p1",
                    "title": "Judul",
                    "content": "Konten",
                    "section": "BAB I",
                    "pages": ["1"],
                    "source": "s.pdf",
                    "metadata": {},
                    "fts_rank": 0.42,
                }
            ]
        )
        mock_sb.rpc.return_value = mock_rpc

        searcher = HybridSearcher(supabase_client=mock_sb)
        rows = searcher._fts_fallback(
            expanded_query="query text",
            filters={"section": "BAB I"},
            match_count=5,
        )

        assert len(rows) == 1
        assert rows[0]["rrf_score"] == 0.42
        mock_sb.rpc.assert_called_once_with(
            "search_fts_child_documents",
            {
                "query_text": "query text",
                "match_count": 5,
                "filter_section": "BAB I",
                "filter_source": None,
            },
        )
