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


def test_auditor_detects_evidence_split_across_chunks():
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

    assert result.status == "context_split"
    assert result.affected_chunk_ids == ["a", "b"]


def test_auditor_reports_missing_extraction():
    result = audit_chunks(_evidence("minimal 100 SKS"), [])

    assert result.status == "extraction_missing"
