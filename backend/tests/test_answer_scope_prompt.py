"""Check generation plumbing; mocked outputs do not measure model accuracy."""

from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from src.generation import chain


def test_postprocessing_preserves_claims_and_only_normalizes_whitespace():
    text = "  Sumber: Panduan contoh\n\n\nBiasanya diperlukan izin.\n\nSyaratnya berbeda.  "
    assert chain.postprocess_answer(text) == (
        "Sumber: Panduan contoh\n\nBiasanya diperlukan izin.\n\nSyaratnya berbeda."
    )


@pytest.mark.parametrize("limit", [23, 71])
def test_generator_uses_current_document_and_calls_llm(monkeypatch, limit):
    context = f"[Sumber: Panduan contoh]\nDokumen contoh memerlukan {limit} lampiran."
    answer = f"Sumber: Panduan contoh\n\nDiperlukan {limit} lampiran."
    llm = Mock()
    llm.invoke.return_value = AIMessage(
        content=answer,
        usage_metadata={"input_tokens": 70, "output_tokens": 20, "total_tokens": 90},
    )
    monkeypatch.setattr(chain, "get_llm", lambda: llm)

    result = chain.RAGGenerator().generate(
        "Berapa lampiran yang diperlukan?", context, [],
    )

    llm.invoke.assert_called_once()
    messages = llm.invoke.call_args.args[0]
    assert context in messages[-1].content
    assert str(limit) not in messages[0].content
    assert result["answer"] == answer
    assert result["usage"]["output_tokens"] == 20


def test_previously_guarded_question_is_still_sent_to_generator(monkeypatch):
    llm = Mock()
    answer = "Sumber: Panduan revisi\n\nIkuti ketentuan pada dokumen revisi ini."
    llm.invoke.return_value = AIMessage(
        content=answer,
        usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
    )
    monkeypatch.setattr(chain, "get_llm", lambda: llm)
    context = (
        "[Sumber: Buku Panduan PI]\nJumlah referensi minimal 15 dan 80% "
        "merupakan ketentuan yang telah dicabut oleh dokumen revisi."
    )
    result = chain.RAGGenerator().generate(
        "Sumber PI harus dari buku atau jurnal?", context, [],
    )
    llm.invoke.assert_called_once()
    assert result["answer"] == answer


def test_empty_context_does_not_return_a_campus_answer_template(monkeypatch):
    llm = Mock()
    llm.invoke.return_value = AIMessage(
        content="Bukti belum ditemukan dalam konteks yang diberikan.",
        usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
    )
    monkeypatch.setattr(chain, "get_llm", lambda: llm)
    result = chain.RAGGenerator().generate("Berapa lama proposal berlaku?", [], [])
    llm.invoke.assert_called_once()
    assert result["answer"] == llm.invoke.return_value.content
