from unittest.mock import Mock

from src.generation.intent_classifier.reformulator import RewriteMethod
from src.generation.memory import ConversationMemory
from src.retrieval.query_planner import QueryComplexity, build_query_plan


def test_simple_query_uses_normalized_query_without_rewriter():
    memory = ConversationMemory()
    rewrite = Mock()

    plan = build_query_plan("  berapa SKS untuk PI?  ", memory, rewrite)

    assert plan.original_query == "berapa SKS untuk PI?"
    assert plan.normalized_query == "berapa SKS untuk Penulisan Ilmiah?"
    assert plan.resolved_query == plan.normalized_query
    assert plan.search_queries == (plan.resolved_query,)
    assert plan.rerank_query == plan.resolved_query
    assert plan.rewrite_method is RewriteMethod.NONE
    rewrite.assert_not_called()


def test_contextual_query_is_rewritten_using_prior_memory():
    memory = ConversationMemory()
    memory.add_user_turn("Apa syarat seminar PI?")
    memory.add_assistant_turn("Syaratnya tercantum dalam panduan.")
    rewrite = Mock(
        return_value=(
            "tahapan setelah seminar Penulisan Ilmiah",
            RewriteMethod.LLM,
        )
    )

    plan = build_query_plan("kalau sudah selesai, lanjut apa?", memory, rewrite)

    assert plan.resolved_query == "tahapan setelah seminar Penulisan Ilmiah"
    assert plan.rewrite_method is RewriteMethod.LLM
    assert plan.cache_key == plan.resolved_query
    rewrite.assert_called_once_with(plan.normalized_query, memory)


def test_explicit_multi_part_query_is_decomposed_without_llm():
    plan = build_query_plan(
        "Apa syarat skripsi, berapa SKS minimalnya, dan bagaimana proses pendadaran?",
        ConversationMemory(),
    )

    assert plan.complexity is QueryComplexity.COMPLEX
    assert plan.is_decomposed is True
    assert plan.search_queries == (
        "Apa syarat skripsi",
        "berapa SKS minimalnya terkait skripsi",
        "bagaimana proses pendadaran terkait skripsi",
    )


def test_conjunction_inside_one_subject_is_not_decomposed():
    plan = build_query_plan(
        "Apa ketentuan dosen pembimbing dan penguji skripsi?",
        ConversationMemory(),
    )

    assert plan.complexity is QueryComplexity.SIMPLE
    assert plan.search_queries == (plan.resolved_query,)


def test_leading_domain_qualifier_is_not_searched_on_its_own():
    plan = build_query_plan(
        "Pada tahap pelaksanaan KKP, berapa lama kegiatan berlangsung, dan bagaimana pelaporannya?",
        ConversationMemory(),
    )

    assert plan.search_queries == (
        "Pada tahap pelaksanaan KKP, berapa lama kegiatan berlangsung",
        "bagaimana pelaporannya terkait KKP",
    )


def test_conditional_preface_is_kept_with_the_question():
    plan = build_query_plan(
        "Kalau menyiapkan laporan PI, berapa margin kiri dan kanan yang harus saya atur?",
        ConversationMemory(),
    )

    assert plan.search_queries == (plan.normalized_query,)


def test_comparison_searches_for_the_shared_proposal_stage_in_each_guide():
    plan = build_query_plan(
        "Bandingkan ketentuan jumlah halaman minimum proposal TA Skripsi dengan proposal TA Non-Skripsi.",
        ConversationMemory(),
    )

    assert plan.search_queries == (
        "jumlah halaman minimum untuk seminar proposal Skripsi",
        "jumlah halaman minimum untuk seminar proposal Tugas Akhir Non Skripsi",
    )
    assert "seminar" not in plan.resolved_query.lower()
    assert "TA Tugas Akhir" not in plan.normalized_query


def test_grade_posting_search_keeps_the_original_request_and_its_guide():
    plan = build_query_plan(
        "Nilai KKP belum tercatat di transkrip. Dokumen apa yang perlu saya serahkan?",
        ConversationMemory(),
    )

    assert plan.search_queries == ("pencantuman nilai KKP pada transkrip",)
    assert plan.resolved_query == plan.normalized_query
    assert plan.rerank_query == plan.normalized_query
    assert build_query_plan(
        "Berapa IPK minimal pada transkrip untuk mendaftar ujian PI?",
        ConversationMemory(),
    ).is_decomposed is False


def test_clarification_preserves_a_resolved_guide_and_leaves_outside_exams_alone():
    memory = ConversationMemory()
    memory.add_user_turn("Saya sedang menyiapkan KKP.")
    memory.add_assistant_turn("Silakan ajukan pertanyaan.")
    rewrite = Mock(return_value=("Kapan batas seminar KKP?", RewriteMethod.LLM))
    question = "Kapan batas seminar?"

    assert build_query_plan(question, memory, rewrite).clarification is None
    assert build_query_plan(question, ConversationMemory()).clarification
    assert build_query_plan(
        "Berapa hari batas pelaksanaan seminar sejak disetujui pembimbing?",
        ConversationMemory(),
    ).clarification
    assert build_query_plan("Kapan jadwal ujian SIM?", ConversationMemory()).clarification is None


def test_non_skripsi_domain_is_carried_to_following_clause():
    plan = build_query_plan(
        "Apa syarat non skripsi dan bagaimana proses pengajuannya?",
        ConversationMemory(),
    )

    assert plan.search_queries == (
        "Apa syarat Tugas Akhir Non Skripsi",
        "bagaimana proses pengajuannya terkait tugas akhir non skripsi",
    )


def test_more_than_three_clauses_are_capped_without_dropping_content():
    plan = build_query_plan(
        "Apa syarat skripsi, berapa SKS minimal, bagaimana prosesnya, dan kapan ujiannya?",
        ConversationMemory(),
    )

    assert len(plan.search_queries) == 3
    assert "bagaimana prosesnya" in plan.search_queries[-1]
    assert "kapan ujiannya" in plan.search_queries[-1]


def test_shared_exam_terms_do_not_invent_a_skripsi_domain():
    plan = build_query_plan(
        "Apa syarat seminar hasil dan bagaimana proses pendadaran?",
        ConversationMemory(),
    )

    assert plan.search_queries == (
        "Apa syarat seminar hasil",
        "bagaimana proses pendadaran",
    )


def test_non_skripsi_track_is_carried_to_following_clause():
    plan = build_query_plan(
        "Apa syarat jalur karya ilmiah dan bagaimana penilaiannya?",
        ConversationMemory(),
    )

    assert plan.search_queries[-1].endswith("terkait tugas akhir non skripsi")


def test_explicit_skripsi_domain_wins_over_generic_track_term():
    plan = build_query_plan(
        "Apa format karya ilmiah untuk skripsi dan bagaimana penilaiannya?",
        ConversationMemory(),
    )

    assert plan.search_queries[-1].endswith("terkait skripsi")


def test_query_plan_does_not_inject_known_answer_or_section_locations():
    for question in (
        "Berapa halaman proposal skripsi?",
        "Apa ketentuan NPWP jalur wirausaha?",
        "Berkas ujian PI apa saja?",
    ):
        plan = build_query_plan(question, ConversationMemory())
        assert plan.search_queries == (plan.normalized_query,)
