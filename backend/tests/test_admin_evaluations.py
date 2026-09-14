from types import SimpleNamespace

from src.api import admin_evaluations
from src.evaluation_agent.models import EvaluationCase, ReviewStatus


class QueueRepository:
    def __init__(self) -> None:
        self.created = None

    def list_cases(self, statuses):
        assert statuses == ["unreviewed", "incorrect", "incomplete", "uncertain"]
        return [
            EvaluationCase(
                case_id="case-1",
                question="Pertanyaan satu?",
                review_status=ReviewStatus.INCORRECT,
            ),
            EvaluationCase(
                case_id="case-2",
                question="Pertanyaan dua?",
                review_status=ReviewStatus.INCOMPLETE,
            ),
        ]

    def create_run(self, model, case_ids, config):
        self.created = {"model": model, "case_ids": case_ids, "config": config}
        return "run-123"


def test_start_run_queues_selected_cases(monkeypatch):
    repository = QueueRepository()
    settings = SimpleNamespace(
        EVALUATION_AGENT_ENABLED=True,
        EVALUATION_MODEL="evaluator-model",
        llm_model="chat-model",
        EVALUATION_DOCUMENT_MANIFEST="manifest.yaml",
        EVALUATION_PAGE_WINDOW=3,
        EVALUATION_QUESTION_BATCH_SIZE=10,
        EVALUATION_MAX_EVIDENCE_PER_CASE=5,
    )
    monkeypatch.setattr(
        admin_evaluations, "get_evaluation_repository", lambda: repository
    )
    monkeypatch.setattr(admin_evaluations, "get_settings", lambda: settings)

    response = admin_evaluations.start_evaluation_run(
        admin_evaluations.StartEvaluationRequest(case_ids=["case-2"]),
        admin={"username": "admin"},
    )

    assert response["run_id"] == "run-123"
    assert "--run-id run-123" in response["next_command"]
    assert repository.created["case_ids"] == ["case-2"]
    assert repository.created["model"] == "evaluator-model"
