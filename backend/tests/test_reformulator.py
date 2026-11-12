"""Regression coverage for lost referents and contaminated conversation domains."""
from unittest.mock import Mock

import pytest
from langchain_core.messages import SystemMessage

from src.generation.intent_classifier.reformulator import (
    QueryReformulator, RewriteMethod, _extract_last_topic, _extract_last_track,
    needs_rewrite, normalize_query,
)
from src.generation.memory import ConversationMemory
from src.retrieval.domains import explicit_domains


@pytest.mark.parametrize("question", [
    "minimal sks sama ipknya berapa?",
    "berkas yang harus saya upload apa aja?",
    "minimal berapa kali?",
    "nah kalau skripsi berapa?",
    "surat itu diterbitkan sama siapa?",
    "bagian hasil dan pembahasan ada di bab berapa?",
])
def test_student_followups_require_context(question):
    assert needs_rewrite(question)


def test_assistant_wrong_domain_cannot_establish_user_topic():
    memory = ConversationMemory()
    memory.add_user_turn("Saya mau ambil skripsi")
    memory.add_assistant_turn("Untuk KKP syaratnya 100 SKS.")
    assert _extract_last_topic(memory) == "Skripsi"


def test_stage_is_resolved_by_context_not_replaced_with_domain():
    memory = ConversationMemory()
    memory.add_user_turn("Pas pendadaran skripsi pakai apa?")
    memory.add_assistant_turn("Pakaian tercantum dalam panduan.")
    llm = Mock()
    llm.invoke.return_value.content = '"Berapa lama ujian pendadaran skripsi?"'
    question, method = QueryReformulator(llm).reformulate("ujiannya berapa lama?", memory)
    assert question == "Berapa lama ujian pendadaran skripsi?"
    assert method == RewriteMethod.LLM
    messages = llm.invoke.call_args.args[0]
    assert isinstance(messages[0], SystemMessage)
    assert "Pas pendadaran skripsi" in messages[1].content


def test_explicit_domain_switch_cannot_be_replaced_by_old_domain():
    memory = ConversationMemory()
    memory.add_user_turn("Berapa SKS PI?")
    memory.add_assistant_turn("100 SKS")
    llm = Mock()
    llm.invoke.return_value.content = "Berapa SKS Penulisan Ilmiah?"
    question, method = QueryReformulator(llm).reformulate("kalau KKP sama juga?", memory)
    assert question == "kalau KKP sama juga?"
    assert method == RewriteMethod.NONE


def test_summary_only_memory_can_resolve_followup():
    memory = ConversationMemory(summary="Pengguna membahas seminar proposal skripsi.")
    llm = Mock()
    llm.invoke.return_value.content = "Apa berkas pendaftaran seminar proposal skripsi?"
    question, method = QueryReformulator(llm).reformulate("berkasnya apa aja?", memory)
    assert "seminar proposal" in question
    assert method == RewriteMethod.LLM


def test_professional_track_is_available_for_followup_rewriting():
    memory = ConversationMemory()
    memory.add_user_turn("Saya web developer, bisa ambil jalur profesional?")
    memory.add_assistant_turn("Syaratnya tersedia dalam panduan.")
    memory.add_user_turn("Kalau kerjanya freelance gimana?")
    memory.add_assistant_turn("Periksa syarat jalurnya.")
    llm = Mock()
    llm.invoke.return_value.content = (
        "Apakah panduan jalur profesional menyebut pekerjaan freelance diperbolehkan?"
    )

    question, method = QueryReformulator(llm).reformulate(
        "Panduannya memang menyebut freelance boleh atau nggak?", memory,
    )

    assert "jalur profesional" in question
    assert method == RewriteMethod.LLM
    assert "Jalur terakhir yang disebut pengguna (bukan fakta kelayakan): jalur profesional" in (
        llm.invoke.call_args.args[0][1].content
    )


def test_explicit_domain_switch_clears_previous_track():
    memory = ConversationMemory()
    memory.add_user_turn("Bagaimana jalur profesional?")
    memory.add_assistant_turn("Syaratnya tersedia dalam panduan.")
    memory.add_user_turn("Kalau KKP berapa SKS?")

    assert _extract_last_track(memory) is None


def test_track_followup_keeps_user_named_track_when_llm_omits_it():
    memory = ConversationMemory()
    memory.add_user_turn("Saya web developer, bisa ambil jalur profesional?")
    memory.add_assistant_turn("Syaratnya ada di panduan.")
    llm = Mock()
    llm.invoke.return_value.content = (
        "Apakah panduan Tugas Akhir Non Skripsi menyebut freelance diperbolehkan?"
    )

    question, method = QueryReformulator(llm).reformulate(
        "Panduannya memang menyebut freelance boleh atau nggak?", memory,
    )

    assert "jalur profesional" in question
    assert method == RewriteMethod.LLM


def test_followup_keeps_user_named_domain_when_llm_drops_it():
    memory = ConversationMemory()
    memory.add_user_turn("Proposal skripsi dibawa saat bimbingan")
    memory.add_assistant_turn("Sesuai panduan skripsi.")
    llm = Mock()
    llm.invoke.return_value.content = "Kalau topik tidak bisa dilanjutkan, apa yang harus dilakukan?"

    question, method = QueryReformulator(llm).reformulate(
        "kalau topiknya tidak bisa dilanjutkan gimana?", memory,
    )

    assert "Skripsi" in question
    assert method == RewriteMethod.LLM


def test_which_one_followup_keeps_all_recent_user_domains():
    memory = ConversationMemory()
    for domain in ("PI", "KKP", "skripsi"):
        memory.add_user_turn(f"Bagaimana syarat {domain}?")
        memory.add_assistant_turn("Syarat tersedia dalam panduan.")
    llm = Mock()
    llm.invoke.return_value.content = "Apakah skripsi bisa tanpa instansi?"

    question, method = QueryReformulator(llm).reformulate(
        "yang bisa tanpa instansi itu yang mana tadi?", memory,
    )

    assert set(explicit_domains(question)) == {
        "Penulisan Ilmiah", "KKP", "Skripsi",
    }
    assert method == RewriteMethod.LLM


def test_which_is_required_followup_stays_a_comparison():
    memory = ConversationMemory()
    for domain in ("PI", "KKP", "skripsi"):
        memory.add_user_turn(f"Bagaimana syarat {domain}?")
        memory.add_assistant_turn("Syarat tersedia dalam panduan.")
    llm = Mock()
    llm.invoke.return_value.content = "Apakah skripsi wajib punya pembimbing lapangan?"

    question, _ = QueryReformulator(llm).reformulate(
        "kalau yang wajib punya pembimbing lapangan?", memory,
    )

    assert set(explicit_domains(question)) == {
        "Penulisan Ilmiah", "KKP", "Skripsi",
    }


def test_failure_carries_only_the_domain_named_by_the_user():
    memory = ConversationMemory()
    memory.add_user_turn("Ujian PI")
    memory.add_assistant_turn("Baik")
    llm = Mock()
    llm.invoke.side_effect = RuntimeError("unavailable")
    question, method = QueryReformulator(llm).reformulate("minimal berapa kali?", memory)
    assert question == "minimal berapa kali terkait Penulisan Ilmiah?"
    assert method == RewriteMethod.RULE


def test_declarative_model_answer_is_not_used_as_a_search_query():
    memory = ConversationMemory()
    memory.add_user_turn("Bimbingan ujian KKP")
    memory.add_assistant_turn("Lembar persetujuan disiapkan.")
    llm = Mock()
    llm.invoke.return_value.content = (
        "Lembar persetujuan ujian KKP harus ditandatangani oleh Ketua Program Studi."
    )

    question, method = QueryReformulator(llm).reformulate(
        "lembar persetujuannya ditandatangani siapa?", memory,
    )

    assert question == "lembar persetujuannya ditandatangani siapa terkait KKP?"
    assert method == RewriteMethod.RULE


def test_followup_keeps_user_named_seminar_stage_without_guessing_domain():
    memory = ConversationMemory()
    memory.add_user_turn("Kalau saya lulus sempro, proposalnya berlaku sampai kapan?")
    memory.add_assistant_turn("Proposal berlaku satu tahun menurut panduan.")
    llm = Mock()
    llm.invoke.return_value.content = "Siapa yang menerbitkan surat pengantar penelitian?"

    question, method = QueryReformulator(llm).reformulate(
        "surat itu diterbitkan sama siapa?", memory,
    )

    assert "seminar proposal" in question.lower()
    assert "Penulisan Ilmiah" not in question
    assert method == RewriteMethod.LLM


def test_followup_preserves_both_user_compared_tracks():
    memory = ConversationMemory()
    memory.add_user_turn("Laporan jalur profesional sama wirausaha strukturnya sama nggak?")
    memory.add_assistant_turn("Keduanya punya empat bab.")
    llm = Mock()
    llm.invoke.return_value.content = "Apakah proposal jalur profesional sampai BAB II?"

    question, method = QueryReformulator(llm).reformulate(
        "proposalnya cuma sampai bab 2 ya?", memory,
    )

    assert "jalur profesional" in question.lower()
    assert "jalur wirausaha" in question.lower()
    assert method == RewriteMethod.LLM


def test_followup_keeps_single_wirausaha_track():
    memory = ConversationMemory()
    memory.add_user_turn("Kalau jalur wirausaha, company profile-nya apa?")
    memory.add_assistant_turn("Panduan memberi beberapa contoh.")
    llm = Mock()
    llm.invoke.return_value.content = "Apakah company profile boleh pakai akun media sosial saja?"

    question, method = QueryReformulator(llm).reformulate(
        "company profile-nya boleh pakai akun media sosial aja?", memory,
    )

    assert "jalur wirausaha" in question.lower()
    assert method == RewriteMethod.LLM


def test_answer_like_rewrite_with_generic_question_is_rejected():
    memory = ConversationMemory()
    memory.add_user_turn("Saya mau ambil PI")
    memory.add_assistant_turn("Sumbernya dari buku dan jurnal.")
    llm = Mock()
    llm.invoke.return_value.content = (
        "Sumber untuk PI harus berasal dari buku dan jurnal. "
        "Apakah ada pertanyaan lain yang ingin Anda ajukan?"
    )

    question, method = QueryReformulator(llm).reformulate(
        "sumbernya harus dari buku atau jurnal?", memory,
    )

    assert "apakah ada pertanyaan lain" not in question.lower()
    assert method == RewriteMethod.RULE


def test_rewriter_discards_answer_sentence_before_question():
    memory = ConversationMemory()
    memory.add_user_turn("Perlu surat pengantar setelah sempro?")
    memory.add_assistant_turn("Surat itu diterbitkan BAAK.")
    llm = Mock()
    llm.invoke.return_value.content = (
        "Surat pengantar ditandatangani Wakil Ketua I. "
        "Apakah ada tanda tangan lain?"
    )

    question, method = QueryReformulator(llm).reformulate(
        "perlu tanda tangan siapa aja?", memory,
    )

    assert "ditandatangani Wakil Ketua I" not in question
    assert "seminar proposal" in question.lower()
    assert method == RewriteMethod.RULE


def test_standalone_question_and_empty_history_skip_model():
    llm = Mock()
    r = QueryReformulator(llm)
    memory = ConversationMemory()
    r.reformulate("apa syarat KKP?", memory)
    memory.add_user_turn("PI")
    memory.add_assistant_turn("Baik")
    r.reformulate("Berapa minimal SKS KKP?", memory)
    llm.invoke.assert_not_called()


def test_normalization_and_domain_boundaries():
    assert normalize_query("bagaimana praktik anti plagiarisme?") == "bagaimana praktik anti plagiarisme?"
    assert "KKP" in normalize_query("apa syarat praktik kerja lapangan?")
    assert "menghadiri seminar" in normalize_query("harus nonton seminar?")
    assert explicit_domains("non-skripsi") == ("Tugas Akhir Non Skripsi",)
    assert explicit_domains("PI dan KKP") == ("Penulisan Ilmiah", "KKP")
    assert explicit_domains("startup") == ()
    assert normalize_query("Penulisan Ilmiah (PI)") == "Penulisan Ilmiah"


def test_rewrite_cannot_copy_an_answer_number_into_the_question():
    memory = ConversationMemory()
    memory.add_user_turn("Berapa lama tahapan seminar hasil skripsi?")
    memory.add_assistant_turn("Batasnya 527 hari.")
    llm = Mock()
    llm.invoke.return_value.content = "Apakah batas 527 hari seminar hasil skripsi bisa diperpanjang?"
    question, method = QueryReformulator(llm).reformulate("Bisa diperpanjang?", memory)
    assert "527" not in question
    assert method == RewriteMethod.RULE


def test_scope_preservation_does_not_invent_after_a_stage():
    memory = ConversationMemory()
    memory.add_user_turn("Saya membahas seminar hasil skripsi")
    memory.add_assistant_turn("Baik.")
    llm = Mock()
    llm.invoke.return_value.content = "Berapa durasi ujiannya?"
    question, _ = QueryReformulator(llm).reformulate("Durasi ujiannya?", memory)
    assert "seminar hasil" in question
    assert "setelah" not in question


def test_unnamed_domain_cannot_be_guessed_from_a_stage():
    memory = ConversationMemory()
    memory.add_user_turn("Seminar proposal dilaksanakan kapan?")
    memory.add_assistant_turn("Untuk PI biasanya ada jadwal.")
    llm = Mock()
    llm.invoke.return_value.content = "Apa berkas seminar Penulisan Ilmiah?"
    question, method = QueryReformulator(llm).reformulate("Berkasnya apa?", memory)
    assert "Penulisan Ilmiah" not in question
    assert "seminar proposal" in question
    assert method == RewriteMethod.RULE
