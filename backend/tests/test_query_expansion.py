"""Regression tests for guide-specific lexical query expansion."""

from src.retrieval.query_expansion import expand_query


def test_acronym_expansion_keeps_full_intent_in_every_alternative():
    expanded = expand_query("berapa SKS minimal untuk PI?")
    variants = expanded.split(" OR ")

    assert variants[0] == "berapa SKS minimal untuk PI?"
    assert any("Satuan Kredit Semester" in variant for variant in variants)
    assert any("Penulisan Ilmiah" in variant for variant in variants)
    assert all("minimal" in variant for variant in variants)


def test_non_skripsi_document_acronyms_are_expanded():
    expanded = expand_query("apakah BMC dan NIB wajib untuk wirausaha?")

    assert "Business Model Canvas" in expanded
    assert "Nomor Induk Berusaha" in expanded


def test_student_wording_gets_document_wording_as_an_alternative():
    expanded = expand_query("berapa batas similarity untuk skripsi?")

    assert "berapa batas kemiripan untuk skripsi?" in expanded
    assert "anti-plagiarisme" in expanded


def test_lowercase_pi_and_ta_are_not_treated_as_ambiguous_acronyms():
    assert expand_query("tapi bagaimana caranya") == "tapi bagaimana caranya"


def test_generic_approval_sheet_is_not_assumed_to_be_loa():
    expanded = expand_query("apa isi lembar persetujuan ujian?")

    assert "LOA" not in expanded


def test_existing_official_role_does_not_get_duplicated():
    expanded = expand_query("apa tugas dosen pembimbing?")

    assert "dosen dosen pembimbing" not in expanded
