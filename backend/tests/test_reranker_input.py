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
