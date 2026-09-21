from src.retrieval.reranker import CrossEncoderReranker


def test_pairs_include_distinct_headings_and_preserve_document_content():
    reranker = object.__new__(CrossEncoderReranker)
    reranker.max_content_chars = 50
    document = {
        "title": "Ketentuan Profesional",
        "section": "Persyaratan",
        "content": "Tiga syarat",
    }
    pairs, truncated = reranker._build_pairs("Syarat?", [document], "content")
    assert pairs == [["Syarat?", "Ketentuan Profesional\n\nPersyaratan\n\nTiga syarat"]]
    assert document["content"] == "Tiga syarat"
    assert truncated == 0


def test_metadata_input_stays_within_limit_and_handles_missing_headings():
    reranker = object.__new__(CrossEncoderReranker)
    reranker.max_content_chars = 20
    pairs, truncated = reranker._build_pairs(
        "Q",
        [
            {"title": "Judul", "section": "Judul", "content": "x" * 50},
            {"title": None, "section": "", "content": "isi"},
        ],
        "content",
    )
    assert pairs[0][1] == "Judul\n\n" + "x" * 13
    assert pairs[1][1] == "isi"
    assert truncated == 1


def test_pairs_prioritize_matched_child_instead_of_parent_start():
    reranker = object.__new__(CrossEncoderReranker)
    reranker.max_content_chars = 200
    document = {
        "title": "Prosedur Proposal",
        "section": "BAB II",
        "content": "bagian awal yang tidak relevan " * 100,
        "matched_child_documents": [
            {
                "id": "child-late",
                "title": "Alur Pelaksanaan Proposal",
                "section": "BAB II > 2.6.1",
                "content": "Mahasiswa mendaftar setelah proposal disetujui.",
            }
        ],
    }

    pairs, truncated = reranker._build_pairs("Bagaimana alurnya?", [document], "content")

    rerank_text = pairs[0][1]
    assert "Mahasiswa mendaftar setelah proposal disetujui." in rerank_text
    assert "bagian awal yang tidak relevan" not in rerank_text
    assert document["rerank_evidence_source"] == "matched_children"
    assert truncated == 0


def test_long_child_uses_query_relevant_window():
    reranker = object.__new__(CrossEncoderReranker)
    reranker.max_content_chars = 300
    late_fact = "Sumber kecocokan wajib dicantumkan dalam bukti anti-plagiarisme."
    document = {
        "title": "Syarat Ujian",
        "section": "BAB II",
        "content": "unused parent",
        "matched_child_documents": [
            {
                "title": "Berkas Ujian",
                "content": ("informasi umum " * 100) + late_fact,
            }
        ],
    }

    pairs, truncated = reranker._build_pairs(
        "Apa yang dicantumkan sebagai sumber kecocokan?",
        [document],
        "content",
    )

    assert late_fact in pairs[0][1]
    assert len(pairs[0][1]) <= 300
    assert document["rerank_window_start"] > 0
    assert truncated == 1
