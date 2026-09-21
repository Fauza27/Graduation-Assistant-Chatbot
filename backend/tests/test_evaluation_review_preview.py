from types import SimpleNamespace

import pytest

from src.api import admin_evaluations


@pytest.mark.parametrize("stored_answer", [None, ""])
def test_review_preview_reads_answer_before_case_exists(monkeypatch, stored_answer):
    repository = SimpleNamespace(
        get_case_by_request=lambda request_id: (
            {"actual_answer": stored_answer} if stored_answer is not None else None
        ),
        load_trace=lambda request_id: {
            "answer": "Jawaban chatbot yang hendak dinilai",
            "final_context": {"documents": ["Konteks internal"]},
        },
    )
    monkeypatch.setattr(
        admin_evaluations, "get_evaluation_repository", lambda: repository
    )

    response = admin_evaluations.get_evaluation_case_by_request(
        "request-1", admin={"username": "admin"}
    )

    assert response["answer"] == "Jawaban chatbot yang hendak dinilai"
    assert set(response) == {"data", "answer"}


def test_review_preview_uses_existing_answer_without_loading_trace(monkeypatch):
    def unexpected_trace(request_id):
        pytest.fail("Trace tidak perlu dibaca jika case sudah mempunyai jawaban")

    repository = SimpleNamespace(
        get_case_by_request=lambda request_id: {"actual_answer": "Jawaban tersimpan"},
        load_trace=unexpected_trace,
    )
    monkeypatch.setattr(
        admin_evaluations, "get_evaluation_repository", lambda: repository
    )

    response = admin_evaluations.get_evaluation_case_by_request(
        "request-1", admin={"username": "admin"}
    )

    assert response["answer"] == "Jawaban tersimpan"


def test_review_preview_handles_missing_historical_answer(monkeypatch):
    repository = SimpleNamespace(
        get_case_by_request=lambda request_id: None,
        load_trace=lambda request_id: {},
    )
    monkeypatch.setattr(
        admin_evaluations, "get_evaluation_repository", lambda: repository
    )

    assert admin_evaluations.get_evaluation_case_by_request(
        "request-1", admin={"username": "admin"}
    ) == {"data": None, "answer": None}
