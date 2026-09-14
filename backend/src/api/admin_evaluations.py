"""Admin-only API for manual RAG review and evaluator reports."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.admin.auth import get_current_admin
from src.evaluation_agent.repository import get_evaluation_repository
from src.evaluation_agent.models import EVALUATION_QUEUE_STATUSES


router = APIRouter(prefix="/admin/evaluations", tags=["Admin Evaluations"])

ReviewStatusValue = Literal[
    "unreviewed", "correct", "incorrect", "incomplete", "uncertain"
]


class CreateEvaluationCaseRequest(BaseModel):
    request_id: str
    review_status: ReviewStatusValue
    expected_answer: str | None = Field(default=None, max_length=20_000)
    expected_evidence: dict[str, Any] | None = None
    review_notes: str | None = Field(default=None, max_length=10_000)


class UpdateEvaluationCaseRequest(BaseModel):
    review_status: ReviewStatusValue | None = None
    expected_answer: str | None = Field(default=None, max_length=20_000)
    expected_evidence: dict[str, Any] | None = None
    review_notes: str | None = Field(default=None, max_length=10_000)


class StartEvaluationRequest(BaseModel):
    case_ids: list[str] | None = None


class ReviewRecommendationRequest(BaseModel):
    status: Literal["approved", "rejected"]


def _admin_identity(admin: dict) -> str:
    return str(admin.get("username") or admin.get("sub") or "admin")


@router.get("/cases")
def list_evaluation_cases(
    status: list[ReviewStatusValue] = Query(default=list(EVALUATION_QUEUE_STATUSES)),
    admin: dict = Depends(get_current_admin),
):
    del admin
    cases = get_evaluation_repository().list_cases(list(status))
    return {"data": [case.model_dump(mode="json") for case in cases]}


@router.post("/cases", status_code=201)
def create_evaluation_case(
    body: CreateEvaluationCaseRequest,
    admin: dict = Depends(get_current_admin),
):
    try:
        row = get_evaluation_repository().create_case_from_request(
            body.request_id,
            review_status=body.review_status,
            expected_answer=body.expected_answer,
            expected_evidence=body.expected_evidence,
            review_notes=body.review_notes,
            created_by=_admin_identity(admin),
        )
        return {"data": row}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/by-request/{request_id}")
def get_evaluation_case_by_request(
    request_id: str,
    admin: dict = Depends(get_current_admin),
):
    del admin
    return {"data": get_evaluation_repository().get_case_by_request(request_id)}


@router.patch("/cases/{case_id}")
def update_evaluation_case(
    case_id: str,
    body: UpdateEvaluationCaseRequest,
    admin: dict = Depends(get_current_admin),
):
    del admin
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan")
    try:
        return {"data": get_evaluation_repository().update_case(case_id, fields)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs")
def list_evaluation_runs(
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(get_current_admin),
):
    del admin
    return {"data": get_evaluation_repository().list_runs(limit)}


@router.get("/runs/{run_id}")
def get_evaluation_run(
    run_id: str,
    admin: dict = Depends(get_current_admin),
):
    del admin
    try:
        return {"data": get_evaluation_repository().get_run_report(run_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs", status_code=202)
def start_evaluation_run(
    body: StartEvaluationRequest,
    admin: dict = Depends(get_current_admin),
):
    del admin
    if not get_settings().EVALUATION_AGENT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Evaluation agent belum diaktifkan pada konfigurasi backend",
        )
    repository = get_evaluation_repository()
    cases = repository.list_cases(list(EVALUATION_QUEUE_STATUSES))
    if body.case_ids is not None:
        requested = set(body.case_ids)
        cases = [case for case in cases if case.case_id in requested]
    if not cases:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada evaluation case gagal yang dapat dijadwalkan",
        )
    settings = get_settings()
    run_id = repository.create_run(
        model=settings.EVALUATION_MODEL or settings.llm_model,
        case_ids=[case.case_id for case in cases],
        config={
            "manifest": settings.EVALUATION_DOCUMENT_MANIFEST,
            "page_window": settings.EVALUATION_PAGE_WINDOW,
            "question_batch_size": settings.EVALUATION_QUESTION_BATCH_SIZE,
            "max_evidence_per_case": settings.EVALUATION_MAX_EVIDENCE_PER_CASE,
        },
    )
    return {
        "message": "Batch evaluasi masuk antrean",
        "run_id": run_id,
        "next_command": f"python scripts/run_failure_evaluation.py --run-id {run_id}",
    }


@router.patch("/recommendations/{recommendation_id}")
def review_recommendation(
    recommendation_id: str,
    body: ReviewRecommendationRequest,
    admin: dict = Depends(get_current_admin),
):
    try:
        row = get_evaluation_repository().review_recommendation(
            recommendation_id,
            body.status,
            _admin_identity(admin),
        )
        return {"data": row}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
