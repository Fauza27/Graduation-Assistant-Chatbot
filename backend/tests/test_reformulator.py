"""Regression coverage for lost referents and contaminated conversation domains."""
from unittest.mock import Mock

import pytest
from langchain_core.messages import SystemMessage

from src.generation.intent_classifier.reformulator import (
    QueryReformulator, RewriteMethod, _extract_last_topic, needs_rewrite, normalize_query,
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


def test_failure_does_not_invent_a_referent():
    memory = ConversationMemory()
    memory.add_user_turn("Ujian PI")
    memory.add_assistant_turn("Baik")
    llm = Mock()
    llm.invoke.side_effect = RuntimeError("unavailable")
    assert QueryReformulator(llm).reformulate("minimal berapa kali?", memory) == (
        "minimal berapa kali?", RewriteMethod.NONE,
    )


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
    assert explicit_domains("non-skripsi") == ("Tugas Akhir Non Skripsi",)
    assert explicit_domains("PI dan KKP") == ("Penulisan Ilmiah", "KKP")
    assert explicit_domains("startup") == ()
