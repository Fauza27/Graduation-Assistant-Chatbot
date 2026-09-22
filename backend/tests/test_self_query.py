"""
Unit tests for self_query.py (Temuan #15, #28) and errors.py AuthenticationError.
"""

from src.monitoring.errors import AuthenticationError, ChatError
from src.retrieval.self_query import (
    _detect_source,
    extract_query_components,
    get_available_sections,
    _SOURCE_PI,
    _SOURCE_KKP,
    _SOURCE_SKRIPSI,
    _SOURCE_NON_SKRIPSI,
)


class TestSelfQuerySourceDetection:
    """Tests for source detection including case-sensitive PI handling (Temuan #28)."""

    def test_pi_detection_unambiguous_phrase(self):
        # Case-insensitive full phrases
        assert _detect_source("apa syarat penulisan ilmiah?", raw_query="apa syarat penulisan ilmiah?") == _SOURCE_PI
        assert _detect_source("alur penulisan imliah", raw_query="alur penulisan imliah") == _SOURCE_PI

    def test_pi_detection_compound_phrases_lowercase(self):
        # Compound phrases with "pi" work even if lowercase
        assert _detect_source("kapan ujian pi?", raw_query="kapan ujian pi?") == _SOURCE_PI
        assert _detect_source("jadwal seminar pi", raw_query="jadwal seminar pi") == _SOURCE_PI
        assert _detect_source("format laporan pi", raw_query="format laporan pi") == _SOURCE_PI

    def test_pi_detection_standalone_uppercase(self):
        # Standalone "PI" works if uppercase
        assert _detect_source("apa syarat pi?", raw_query="apa syarat PI?") == _SOURCE_PI
        assert _detect_source("bagaimana alur pi?", raw_query="Bagaimana alur PI?") == _SOURCE_PI

    def test_pi_no_false_positives(self):
        # Common Indonesian words containing "pi" or lowercase "pi" must NOT match PI source
        assert _detect_source("tapi bagaimana syaratnya?", raw_query="tapi bagaimana syaratnya?") is None
        assert _detect_source("topi saya hilang di kampus", raw_query="topi saya hilang di kampus") is None
        assert _detect_source("tempat ini sangat sepi", raw_query="tempat ini sangat sepi") is None
        assert _detect_source("pilihan program studi apa saja?", raw_query="pilihan program studi apa saja?") is None

    def test_other_sources(self):
        assert _detect_source("syarat tempat kkp", raw_query="syarat tempat kkp") == _SOURCE_KKP
        assert _detect_source("format laporan non skripsi", raw_query="format laporan non skripsi") == _SOURCE_NON_SKRIPSI
        assert _detect_source("syarat pendadaran skripsi", raw_query="syarat pendadaran skripsi") == _SOURCE_SKRIPSI

    def test_shared_exam_terms_do_not_force_skripsi_source(self):
        assert _detect_source("syarat seminar hasil", raw_query="syarat seminar hasil") is None
        assert _detect_source("alur pendadaran", raw_query="alur pendadaran") is None

    def test_non_skripsi_guide_specific_terms(self):
        assert _detect_source("syarat jalur karya ilmiah", raw_query="syarat jalur karya ilmiah") == _SOURCE_NON_SKRIPSI
        assert _detect_source("ketentuan pekerja profesional", raw_query="ketentuan pekerja profesional") == _SOURCE_NON_SKRIPSI

    def test_generic_journal_term_does_not_force_non_skripsi(self):
        assert _detect_source("format referensi jurnal", raw_query="format referensi jurnal") is None

    def test_explicit_domain_wins_over_non_skripsi_track_vocabulary(self):
        assert _detect_source(
            "cara menulis karya ilmiah untuk skripsi",
            raw_query="cara menulis karya ilmiah untuk skripsi",
        ) == _SOURCE_SKRIPSI
        assert _detect_source(
            "format prosiding untuk penulisan ilmiah",
            raw_query="format prosiding untuk penulisan ilmiah",
        ) == _SOURCE_PI

    def test_extract_query_components_end_to_end(self):
        parsed = extract_query_components("Bagaimana alur seminar PI?")
        assert parsed.detected_source == _SOURCE_PI
        assert parsed.filters.get("source") == _SOURCE_PI

    def test_resolved_skripsi_requirement_routes_to_skripsi(self):
        parsed = extract_query_components(
            "Berapa minimal SKS dan IPK untuk mengambil Skripsi?"
        )

        assert parsed.detected_source == _SOURCE_SKRIPSI
        assert parsed.filters.get("source") == _SOURCE_SKRIPSI

    def test_professional_track_routes_to_non_skripsi(self):
        parsed = extract_query_components(
            "Apa syarat jalur pekerja profesional Non-Skripsi?"
        )

        assert parsed.detected_source == _SOURCE_NON_SKRIPSI
        assert parsed.filters.get("source") == _SOURCE_NON_SKRIPSI

    def test_cross_domain_comparison_keeps_search_unfiltered(self):
        parsed = extract_query_components(
            "Apakah minimal SKS dan IPK untuk PI sama dengan KKP?"
        )

        assert parsed.detected_source is None
        assert "source" not in parsed.filters

    def test_non_skripsi_chapter_filter_uses_normalized_database_section(self):
        parsed = extract_query_components(
            "syarat non skripsi dan berapa sks minimal"
        )

        assert parsed.detected_source == _SOURCE_NON_SKRIPSI
        assert parsed.detected_section == "BAB II"
        assert parsed.filters == {
            "source": _SOURCE_NON_SKRIPSI,
            "section": "BAB II KETENTUAN UMUM",
        }

    def test_chapter_filter_requires_a_compatible_source(self):
        generic = extract_query_components("berapa sks minimal dan ipk minimal")
        skripsi = extract_query_components("syarat skripsi dan sks minimal")

        assert generic.detected_section == "BAB II"
        assert "section" not in generic.filters
        assert skripsi.filters["section"] == "BAB II >"

    def test_chapter_filter_does_not_use_ambiguous_roman_prefix(self):
        pi = extract_query_components("syarat PI dan sks minimal")
        non_skripsi = extract_query_components(
            "sistematika jalur wirausaha non skripsi"
        )

        assert pi.filters["section"] == "BAB II >"
        assert non_skripsi.filters["section"] == (
            "BAB III BENTUK TUGAS AKHIR NON SKRIPSI"
        )

    def test_skripsi_front_matter_filter_is_suppressed_for_its_metadata(self):
        parsed = extract_query_components(
            "contoh kata pengantar dan daftar isi skripsi"
        )

        assert parsed.detected_section == "Front Matter"
        assert parsed.filters == {"source": _SOURCE_SKRIPSI}


class TestSelfQueryAvailableSections:
    """Tests for get_available_sections filtering (Temuan #15)."""

    def test_get_available_sections_all(self):
        sections_all = get_available_sections("all")
        assert "BAB I" in sections_all
        assert "BAB II" in sections_all
        assert "BAB III" in sections_all
        assert "Lampiran" in sections_all

    def test_get_available_sections_per_source(self):
        pi_sections = get_available_sections("PI")
        assert any("PI" in desc for desc in pi_sections["BAB II"])

        kkp_sections = get_available_sections("KKP")
        assert any("KKP" in desc for desc in kkp_sections["BAB II"])

        skripsi_sections = get_available_sections("SKRIPSI")
        assert any("Skripsi" in desc for desc in skripsi_sections["BAB II"])

        non_skripsi_sections = get_available_sections("NON_SKRIPSI")
        assert any("Non Skripsi" in desc or "Jalur Kelulusan" in desc for desc in non_skripsi_sections["BAB II"])


class TestAuthenticationError:
    """Tests for AuthenticationError class consistency."""

    def test_authentication_error_properties(self):
        err = AuthenticationError("Token expired")
        assert isinstance(err, ChatError)
        assert err.error_source == "authentication"
        assert str(err) == "Token expired"

    def test_authentication_error_default_message(self):
        err = AuthenticationError()
        assert err.message == "Autentikasi diperlukan."
        assert err.error_source == "authentication"
