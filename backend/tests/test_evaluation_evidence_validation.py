"""Regression checks for erroneous decisions observed in the September 21 run."""

import pytest

from src.evaluation_agent.evidence_validation import validate_quote, grounded_numbers
from src.evaluation_agent.models import DocumentPage, EvidenceVerification


def verification(quote, **changes):
    fields = dict(
        answers_question=True,
        answer_available=True,
        page_start=15,
        page_end=15,
        corrected_evidence_text=quote,
        explanation="Bukti menjawab pertanyaan.",
        confidence=0.9,
        verdict="supported",
        reference_answer="Sesuai kutipan.",
    )
    return EvidenceVerification(**(fields | changes))


@pytest.mark.parametrize(
    "quote",
    [
        "jumlah SKS minimal 100 SKS dengan IP Kumulatif minimal 2,00.",
        "Bukti pemeriksaan anti-plagiarisme dengan tingkat kemiripan maksimal 30%",
        "Proposal dibuat minimal 40 halaman (tidak termasuk cover, daftar isi, daftar pustaka).",
        "Seminar proposal dilaksanakan paling lama 60 menit, terdiri dari 10 menit untuk presentasi",
        "Identitas Email Mahasiswa berdomain wicida.ac.id (*@wicida.ac.id)",
        "mahasiswa menyerahkan form tersebut ke BAAK untuk mendapatkan surat pengantar",
    ],
)
def test_source_quotes_survive_pdf_whitespace_normalization(quote):
    page = DocumentPage(page_number=15, text=quote.replace(" ", "  \n"))
    assert validate_quote(verification(quote), [page]) is None


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"page_start": 999, "page_end": 999}, "page_outside_checked_window"),
        ({"page_start": 16, "page_end": 15}, "missing_or_reversed_page_range"),
        ({"corrected_evidence_text": "maksimal 40%"}, "quote_not_in_cited_pages"),
        (
            {"corrected_evidence_text": "Bukti menjelaskan syarat plagiasi."},
            "quote_not_in_cited_pages",
        ),
        ({"answer_available": False}, "contradictory_verdict"),
        ({"is_related_scope": True}, "contradictory_scope"),
        ({"reference_answer": ""}, "missing_reference_answer"),
    ],
)
def test_invalid_evidence_cannot_be_certified(changes, reason):
    page = DocumentPage(page_number=15, text="maksimal 30%")
    assert validate_quote(verification("maksimal 30%", **changes), [page]) == reason


def test_numeric_guard_accepts_decimal_formatting_but_rejects_invented_limits():
    assert grounded_numbers("IPK 2.0", "IP Kumulatif minimal 2,00")
    assert not grounded_numbers("maksimal 40%", "maksimal 30%")


def test_quote_on_a_different_page_is_rejected():
    pages = [
        DocumentPage(page_number=15, text="halaman lain"),
        DocumentPage(page_number=16, text="maksimal 30%"),
    ]
    assert (
        validate_quote(verification("maksimal 30%"), pages)
        == "quote_not_in_cited_pages"
    )
