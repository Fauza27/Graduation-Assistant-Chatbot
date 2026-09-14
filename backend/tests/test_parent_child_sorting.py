"""
Unit tests for parent_child.py matched_pages sorting.
Validates that numeric sorting works and mixed numbers/strings do not raise TypeError.
"""

from src.retrieval.parent_child import ParentChildFetcher


class TestParentChildPageSorting:

    def test_numeric_page_sorting(self):
        """Urutan halaman numerik harus 1, 2, 10, 20 (bukan leksikografis 1, 10, 2, 20)."""
        pages = ["10", "2", "1", "20"]
        sorted_pages = sorted(
            set(pages),
            key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)),
        )
        assert sorted_pages == ["1", "2", "10", "20"]

    def test_mixed_digit_and_roman_pages_no_type_error(self):
        """Campuran halaman digit ('1', '2') dan non-digit ('iv', 'v', 'cover') tidak crash."""
        pages = ["2", "iv", "10", "1", "v", "cover"]
        sorted_pages = sorted(
            set(pages),
            key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)),
        )
        # Angka diurutkan numerik dulu, lalu non-angka secara alfabetis
        assert sorted_pages == ["1", "2", "10", "cover", "iv", "v"]

    def test_attach_metadata_sorts_pages(self):
        """Verifikasi _attach_metadata memasang matched_pages yang terurut dengan benar."""
        from src.retrieval.parent_child import ParentMatchInfo

        parents = [{"parent_id": "p1"}]
        parent_matches = {
            "p1": ParentMatchInfo(
                best_score=0.9,
                matched_children=["c1", "c2"],
                score_source="rrf",
            )
        }
        child_pages = {
            "p1": ["12", "3", "i", "4"]
        }

        ParentChildFetcher._attach_metadata(parents, parent_matches, child_pages)
        assert parents[0]["matched_pages"] == ["3", "4", "12", "i"]
