from src.evaluation_agent.evidence_search import OriginalDocumentIndex, infer_domains
from src.evaluation_agent.models import (
    ConversationTurn,
    EvaluationCase,
    PageWindow,
    ReviewStatus,
)


def _window(slug: str, domain: str, page: int, text: str) -> tuple[PageWindow, str]:
    return (
        PageWindow(
            document_slug=slug,
            document_title=f"Panduan {domain}",
            version_id=f"version-{slug}",
            page_start=page,
            page_end=page,
            text=f"--- HALAMAN FISIK {page} ---\n{text}",
        ),
        domain,
    )


def test_search_uses_student_context_and_limits_explicit_domain():
    index = OriginalDocumentIndex(
        [
            _window(
                "skripsi",
                "SKRIPSI",
                15,
                "Pendaftaran seminar proposal melalui laman web KPST.",
            ),
            _window(
                "kkp", "KKP", 17, "Pendaftaran seminar KKP melalui laman web KPST."
            ),
        ]
    )
    case = EvaluationCase(
        case_id="case-1",
        question="berkasnya upload lewat mana?",
        standalone_question="Pendaftaran seminar proposal Skripsi dilakukan melalui apa?",
        conversation_context=[ConversationTurn(question="daftar sempro skripsi")],
        review_status=ReviewStatus.UNREVIEWED,
    )

    results = index.search(case, limit=5)

    assert infer_domains(case) == {"SKRIPSI"}
    assert [result.window.document_slug for result in results] == ["skripsi"]
    assert "KPST" in results[0].snippet


def test_search_uses_previous_turn_for_short_follow_up():
    index = OriginalDocumentIndex(
        [
            _window(
                "skripsi",
                "SKRIPSI",
                15,
                "Naskah seminar proposal minimal 40 halaman di luar lampiran.",
            ),
            _window("kkp", "KKP", 8, "Laporan KKP memuat kegiatan pada instansi."),
        ]
    )
    case = EvaluationCase(
        case_id="case-2",
        question="minimal berapa halaman?",
        review_status=ReviewStatus.UNREVIEWED,
        conversation_context=[
            ConversationTurn(
                question="saya mau daftar sempro skripsi",
                resolved_question="Pendaftaran seminar proposal Skripsi",
            )
        ],
    )

    results = index.search(case, limit=5)

    assert infer_domains(case) == {"SKRIPSI"}
    assert results[0].window.page_start == 15
    assert "40 halaman" in results[0].snippet


def test_search_bridges_student_and_document_plagiarism_terms():
    index = OriginalDocumentIndex(
        [
            _window(
                "skripsi",
                "SKRIPSI",
                15,
                "Hasil cek anti plagiasi memiliki batas kemiripan maksimal 30 persen.",
            ),
            _window("skripsi", "SKRIPSI", 30, "Ketentuan ukuran margin naskah."),
        ]
    )
    case = EvaluationCase(
        case_id="case-3",
        question="maksimal similarity skripsi berapa?",
        review_status=ReviewStatus.UNREVIEWED,
    )

    results = index.search(case, limit=2)

    assert results[0].window.page_start == 15
    assert "30 persen" in results[0].snippet


def test_sempro_context_excludes_pi_and_kkp_guides():
    index = OriginalDocumentIndex(
        [
            _window(
                "skripsi", "SKRIPSI", 15, "Berkas seminar proposal diunggah ke KPST."
            ),
            _window(
                "non-skripsi",
                "NON_SKRIPSI",
                15,
                "Berkas seminar proposal diunggah ke KPST.",
            ),
            _window("pi", "PI", 47, "Berkas ujian PI diupload ke KPST."),
            _window("kkp", "KKP", 45, "Berkas seminar KKP diupload ke KPST."),
        ]
    )
    case = EvaluationCase(
        case_id="case-4",
        question="berkas yang harus saya upload apa aja?",
        review_status=ReviewStatus.UNREVIEWED,
        conversation_context=[
            ConversationTurn(question="habis ini daftar sempro lewat mana?")
        ],
    )

    results = index.search(case, limit=8)

    assert infer_domains(case) == {"SKRIPSI", "NON_SKRIPSI"}
    assert {result.window.document_slug for result in results} == {
        "skripsi",
        "non-skripsi",
    }


def test_immediate_context_removes_scope_drift_from_old_reformulation():
    index = OriginalDocumentIndex(
        [
            _window(
                "skripsi", "SKRIPSI", 16, "Seminar proposal berlangsung total 60 menit."
            ),
            _window(
                "skripsi", "SKRIPSI", 20, "Seminar hasil berlangsung total 60 menit."
            ),
        ]
    )
    case = EvaluationCase(
        case_id="case-5",
        question="terus total ujiannya berapa lama?",
        standalone_question="Durasi ujian seminar proposal dan seminar hasil",
        review_status=ReviewStatus.UNREVIEWED,
        conversation_context=[
            ConversationTurn(question="pas sempro presentasi berapa menit?")
        ],
    )

    results = index.search(case, limit=2)

    assert results[0].window.page_start == 16


def test_loa_question_is_not_routed_to_kkp_by_a_corrupted_rewrite():
    case = EvaluationCase(
        case_id="loa",
        question="kalau artikelnya baru dapat LoA tapi belum terbit, bisa dipakai nggak?",
        standalone_question="LoA bisa dipakai terkait KKP?",
        review_status="unreviewed",
        prior_questions=[
            "tugas akhir non skripsi jalur karya ilmiah itu syaratnya apa?",
            "emailnya harus email kampus?",
        ],
        conversation_context=[
            ConversationTurn(
                question="emailnya harus email kampus?",
                resolved_question="Email KKP",
                answer="Kegiatan KKP",
            )
        ],
    )
    assert infer_domains(case) == {"NON_SKRIPSI"}
    assert "KKP" not in case.context_text
    assert "KKP" not in case.evidence_question


def test_new_explicit_topic_overrides_previous_domain():
    case = EvaluationCase(
        case_id="switch",
        question="nah kalau skripsi berapa?",
        review_status="unreviewed",
        prior_questions=["PI berapa SKS?", "kalau KKP?"],
    )
    assert infer_domains(case) == {"SKRIPSI"}


def test_old_rewrite_alone_cannot_establish_a_domain():
    case = EvaluationCase(
        case_id="missing",
        question="nilai maksimalnya berapa?",
        standalone_question="nilai KKP maksimal berapa?",
        review_status="unreviewed",
    )
    assert infer_domains(case) == set()
