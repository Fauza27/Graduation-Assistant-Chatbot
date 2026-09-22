from src.evaluation_agent.chunk_auditor import audit_chunks
from src.evaluation_agent.models import EvidenceCandidate


def _evidence(text: str) -> EvidenceCandidate:
    return EvidenceCandidate(
        case_id="case-1",
        version_id="version-1",
        document_slug="kkp",
        document_title="Panduan KKP",
        page_start=10,
        page_end=11,
        evidence_text=text,
        explanation="",
        confidence=0.9,
        is_verified=True,
    )


def test_child_fragmentation_does_not_prove_a_chunking_failure():
    evidence = _evidence(
        "Mahasiswa dapat mengikuti KKP setelah menyelesaikan minimal 100 SKS dan tidak memiliki nilai E"
    )
    chunks = [
        {
            "id": "a",
            "parent_id": "p",
            "content": "Mahasiswa dapat mengikuti KKP setelah menyelesaikan minimal 100 SKS",
        },
        {
            "id": "b",
            "parent_id": "p",
            "content": "Persyaratan berikutnya adalah tidak memiliki nilai E",
        },
    ]

    result = audit_chunks(evidence, chunks)

    assert result.status == "inconclusive"
    assert result.affected_chunk_ids == []
    parent = {"parent_id": "p", "content": evidence.evidence_text}
    with_parent = audit_chunks(evidence, chunks, [parent])
    assert with_parent.status == "chunking_valid"
    assert with_parent.matched_parent_ids == ["p"]


def test_parent_evidence_does_not_require_a_pages_column():
    evidence = _evidence("minimal 100 SKS")
    result = audit_chunks(
        evidence,
        [{"id": "child", "parent_id": "parent", "content": "fragment"}],
        [{"parent_id": "parent", "content": "minimal 100 SKS", "title": "Syarat"}],
    )
    assert result.status == "chunking_valid"
    assert result.matched_parent_ids == ["parent"]


def test_auditor_reports_missing_extraction():
    result = audit_chunks(_evidence("minimal 100 SKS"), [])

    assert result.status == "extraction_missing"
