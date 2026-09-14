"""
Unit tests for self_query.py (Temuan #15, #28) and errors.py AuthenticationError.
"""

import pytest

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

    def test_extract_query_components_end_to_end(self):
        parsed = extract_query_components("Bagaimana alur seminar PI?")
        assert parsed.detected_source == _SOURCE_PI
        assert parsed.filters.get("source") == _SOURCE_PI


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
