from src.evaluation_agent.models import EvaluationCase, ReviewStatus
from src.evaluation_agent.repository import attach_case_context, _all_rows


def test_attach_case_context_uses_only_prior_turns_and_resolved_query():
    case = EvaluationCase(
        case_id="case-2",
        request_id="request-2",
        question="berkasnya apa aja?",
        review_status=ReviewStatus.UNREVIEWED,
    )
    metrics = [
        {
            "request_id": "request-1",
            "session_id": "session-1",
            "created_at": "2026-09-21T01:00:00Z",
            "question": "saya mau daftar sempro skripsi",
        },
        {
            "request_id": "request-2",
            "session_id": "session-1",
            "created_at": "2026-09-21T01:01:00Z",
            "question": "berkasnya apa aja?",
        },
        {
            "request_id": "request-3",
            "session_id": "session-1",
            "created_at": "2026-09-21T01:02:00Z",
            "question": "pertanyaan masa depan",
        },
    ]
    traces = [
        {
            "request_id": "request-1",
            "query_plan": {"resolved_query": "Pendaftaran seminar proposal Skripsi"},
            "answer": "Silakan mendaftar melalui KPST.",
        },
        {
            "request_id": "request-2",
            "query_plan": {
                "resolved_query": "Berkas pendaftaran seminar proposal Skripsi"
            },
            "answer": "Jawaban saat ini.",
        },
    ]

    enriched = attach_case_context([case], metrics, traces, max_turns=3)[0]

    assert enriched.evidence_question == "berkasnya apa aja?"
    assert enriched.session_id == "session-1"
    assert enriched.standalone_question == "Berkas pendaftaran seminar proposal Skripsi"
    assert enriched.prior_questions == ["saya mau daftar sempro skripsi"]
    assert "Pendaftaran seminar proposal Skripsi" not in enriched.context_text
    assert [turn.question for turn in enriched.conversation_context] == [
        "saya mau daftar sempro skripsi"
    ]
    assert "pertanyaan masa depan" not in enriched.context_text


def test_pagination_keeps_evidence_beyond_first_response():
    from types import SimpleNamespace

    class Query:
        def range(self, start, end):
            self.start, self.end = start, end
            return self

        def execute(self):
            return SimpleNamespace(
                data=[{"id": n} for n in range(7)][self.start : self.end + 1]
            )

    assert _all_rows(Query(), page_size=3) == [{"id": n} for n in range(7)]
