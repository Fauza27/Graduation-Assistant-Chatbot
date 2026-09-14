from src.evaluation_agent.models import (
    EvaluationCase,
    RegressionJudgement,
    ReviewStatus,
)
from src.evaluation_agent.regression import RegressionRunner


class RegressionRepository:
    def __init__(self) -> None:
        self.saved = []

    def load_regression_inputs(self, run_id):
        assert run_id == "run-1"
        return [
            {
                "case": EvaluationCase(
                    case_id="case-1",
                    request_id="baseline-request",
                    question="Apa syaratnya?",
                    review_status=ReviewStatus.INCORRECT,
                ),
                "evidence_text": "Syarat yang benar.",
                "affected_chunk_ids": ["child-1"],
            }
        ]

    def load_trace(self, request_id):
        assert request_id == "replay-request"
        return {
            "search_candidates": [
                {"child_id": "child-1", "parent_id": "parent-1", "rank": 2}
            ],
            "reranked_candidates": [{"parent_id": "parent-1", "accepted": True}],
            "final_context": {"document_ids": ["parent-1"]},
        }

    def save_regression_result(self, row):
        self.saved.append(row)


class RegressionModel:
    def judge_regression(self, case, answer, evidence_text):
        assert answer == "Jawaban baru"
        assert evidence_text == "Syarat yang benar."
        return RegressionJudgement(
            answer_correct=True,
            citation_correct=True,
            explanation="Jawaban sesuai bukti.",
        )


def test_regression_tracks_evidence_through_pipeline():
    repository = RegressionRepository()

    runner = RegressionRunner(
        repository=repository,
        model=RegressionModel(),
        chat_callable=lambda **kwargs: {
            "request_id": "replay-request",
            "answer": "Jawaban baru",
        },
    )
    results = runner.run("run-1")

    assert results[0]["evidence_found"] is True
    assert results[0]["evidence_rank"] == 2
    assert results[0]["survived_reranker"] is True
    assert results[0]["included_in_context"] is True
    assert results[0]["answer_correct"] is True
    assert repository.saved == results
