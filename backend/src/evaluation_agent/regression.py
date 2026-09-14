"""Replay evaluated questions and compare new pipeline behavior with evidence."""

from __future__ import annotations

import uuid
from typing import Callable

from src.evaluation_agent.model_client import EvaluatorModel, get_evaluator_model
from src.evaluation_agent.repository import (
    EvaluationRepository,
    get_evaluation_repository,
)
from src.services.ai_services import chat


ChatCallable = Callable[..., dict]


class RegressionRunner:
    def __init__(
        self,
        repository: EvaluationRepository | None = None,
        model: EvaluatorModel | None = None,
        chat_callable: ChatCallable = chat,
    ) -> None:
        self.repository = repository or get_evaluation_repository()
        self.model = model or get_evaluator_model()
        self.chat_callable = chat_callable

    def run(self, evaluation_run_id: str) -> list[dict]:
        results: list[dict] = []
        for item in self.repository.load_regression_inputs(evaluation_run_id):
            case = item["case"]
            response = self.chat_callable(
                query=case.question,
                session_id=f"evaluation-{uuid.uuid4()}",
                username="RAG Evaluator",
                channel="website",
                mahasiswa_id=None,
            )
            request_id = response.get("request_id")
            trace = self.repository.load_trace(request_id)
            judgement = self.model.judge_regression(
                case, response.get("answer", ""), item["evidence_text"]
            )
            child_ids = set(item["affected_chunk_ids"])
            search_rows = trace.get("search_candidates", [])
            evidence_ranks = [
                int(row["rank"])
                for row in search_rows
                if row.get("child_id") in child_ids and row.get("rank") is not None
            ]
            relevant_parents = {
                row.get("parent_id")
                for row in search_rows
                if row.get("child_id") in child_ids
            }
            accepted = {
                row.get("parent_id")
                for row in trace.get("reranked_candidates", [])
                if row.get("accepted")
            }
            context_ids = set(trace.get("final_context", {}).get("document_ids", []))
            row = {
                "run_id": evaluation_run_id,
                "case_id": case.case_id,
                "baseline_request_id": case.request_id,
                "replay_request_id": request_id,
                "evidence_found": bool(evidence_ranks),
                "evidence_rank": min(evidence_ranks) if evidence_ranks else None,
                "survived_reranker": bool(relevant_parents & accepted),
                "included_in_context": bool(relevant_parents & context_ids),
                "answer_correct": judgement.answer_correct,
                "citation_correct": judgement.citation_correct,
                "notes": judgement.explanation,
            }
            self.repository.save_regression_result(row)
            results.append(row)
        return results
