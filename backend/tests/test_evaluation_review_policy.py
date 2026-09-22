from src.evaluation_agent.models import Diagnosis, DiagnosisReview, Recommendation
from src.evaluation_agent.review_policy import constrain_review


def recommendation(target):
    return Recommendation(
        target=target,
        action="Uji input pencarian.",
        rationale="Bukti belum ditemukan.",
        risk="low",
        validation_plan="Uji kasus kontrol.",
    )


def test_unverified_evidence_cannot_generate_document_edits():
    diagnosis = Diagnosis(
        failed_stage="ambiguous", root_cause="Bukti belum cukup.", confidence=0.35
    )
    proposed = DiagnosisReview(
        failed_stage="information_unavailable",
        root_cause="Tambahkan layanan penitipan hewan.",
        confidence=0.9,
        recommendations=[recommendation("Buku Panduan KKP")],
    )
    result = constrain_review(proposed, diagnosis, {})
    assert result.failed_stage.value == "ambiguous"
    assert result.recommendations == []
    assert result.confidence == 0.35


def test_only_inspected_code_targets_are_retained():
    diagnosis = Diagnosis(
        failed_stage="retrieval",
        root_cause="Retrieval kehilangan bukti.",
        confidence=0.7,
    )
    proposed = DiagnosisReview(
        failed_stage="retrieval",
        root_cause="Bukti tidak terambil.",
        confidence=0.95,
        recommendations=[
            recommendation("Buku Panduan"),
            recommendation("src/retrieval/hybrid_search.py"),
            recommendation("src/invented.py"),
        ],
    )
    context = {
        "current_source_excerpts": [
            {
                "path": "src/retrieval/hybrid_search.py",
                "excerpts": [{"symbol": "search"}],
            }
        ]
    }
    result = constrain_review(proposed, diagnosis, context)
    assert [r.target for r in result.recommendations] == [
        "src/retrieval/hybrid_search.py"
    ]
    assert result.confidence == 0.7


def test_reviewer_cannot_move_failure_to_an_unsupported_stage():
    diagnosis = Diagnosis(
        failed_stage="retrieval", root_cause="Bukti tidak terambil.", confidence=0.7
    )
    proposed = DiagnosisReview(
        failed_stage="reranking",
        root_cause="Skor rendah.",
        confidence=0.9,
        recommendations=[recommendation("src/retrieval/reranker.py")],
    )
    result = constrain_review(proposed, diagnosis, {})
    assert result.root_cause == diagnosis.root_cause
    assert result.recommendations == []
