from scripts.database.rebuild_lossless_pi_kkp_chunks import (
    KKP_SPEC,
    PI_SPEC,
    _load_json,
    rebuild,
)


def test_lossless_chunk_rebuild_is_reproducible_and_parent_child_consistent():
    for spec in (PI_SPEC, KKP_SPEC):
        parents, children, _ = rebuild(spec)

        assert parents == _load_json(spec.parent_path)
        assert children == _load_json(spec.child_path)

        children_by_id = {child["id"]: child for child in children}
        for parent in parents:
            expected = "\n\n".join(
                children_by_id[child_id]["content"]
                for child_id in parent["child_ids"]
            )
            assert parent["content"] == expected


def test_rebuilt_chunks_retain_previously_missing_source_facts():
    pi_text = "\n".join(
        child["content"] for child in _load_json(PI_SPEC.child_path)
    ).casefold()
    kkp_text = "\n".join(
        child["content"] for child in _load_json(KKP_SPEC.child_path)
    ).casefold()

    for text in (pi_text, kkp_text):
        assert "sumber kecocokan yang terdeteksi" in text
        assert "header tabel harus tetap ditampilkan" in text

    assert "keselarasan antara pekerjaan" in kkp_text
    assert "dampak langsung dari tugas" in kkp_text
    assert "baik dari sisi teknis, proses kerja, maupun pengalaman pribadi" in kkp_text
