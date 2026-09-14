"""Typed contracts shared by the RAG evaluation workflow."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    INCOMPLETE = "incomplete"
    UNCERTAIN = "uncertain"


EVALUATION_QUEUE_STATUSES = (
    ReviewStatus.UNREVIEWED.value,
    ReviewStatus.INCORRECT.value,
    ReviewStatus.INCOMPLETE.value,
    ReviewStatus.UNCERTAIN.value,
)


class FailureStage(str, Enum):
    INFORMATION_UNAVAILABLE = "information_unavailable"
    EXTRACTION = "extraction"
    CHUNKING = "chunking"
    QUERY_PROCESSING = "query_processing"
    RETRIEVAL = "retrieval"
    PARENT_ASSEMBLY = "parent_assembly"
    RERANKING = "reranking"
    CONTEXT_ASSEMBLY = "context_assembly"
    GENERATION = "generation"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class DocumentSpec(BaseModel):
    slug: str
    title: str
    domain: str
    version: str
    path: Path
    chunk_source: str


class RegisteredDocument(BaseModel):
    document_id: str
    version_id: str
    spec: DocumentSpec
    checksum_sha256: str
    page_count: int


class DocumentPage(BaseModel):
    page_number: int
    text: str
    extraction_warning: str | None = None


class PageWindow(BaseModel):
    document_slug: str
    document_title: str
    version_id: str
    page_start: int
    page_end: int
    text: str
    has_extraction_warning: bool = False


class EvaluationCase(BaseModel):
    case_id: str
    request_id: str | None = None
    question: str
    actual_answer: str | None = None
    review_status: ReviewStatus
    expected_answer: str | None = None
    expected_evidence: dict[str, Any] | None = None
    review_notes: str | None = None
    created_by: str | None = None


class EvidenceCandidateLLM(BaseModel):
    case_id: str
    is_relevant: bool
    page_start: int | None = None
    page_end: int | None = None
    evidence_text: str = ""
    explanation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class WindowScanOutput(BaseModel):
    candidates: list[EvidenceCandidateLLM]


class EvidenceCandidate(BaseModel):
    case_id: str
    version_id: str
    document_slug: str
    document_title: str
    page_start: int
    page_end: int
    evidence_text: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    is_verified: bool = False


class EvidenceVerification(BaseModel):
    answers_question: bool
    answer_available: bool
    page_start: int | None = None
    page_end: int | None = None
    corrected_evidence_text: str = ""
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class ChunkMatch(BaseModel):
    child_id: str
    parent_id: str
    title: str = ""
    pages: list[str] = Field(default_factory=list)
    coverage: float = Field(ge=0.0, le=1.0)


class ChunkAudit(BaseModel):
    status: str
    explanation: str
    affected_chunk_ids: list[str] = Field(default_factory=list)
    matched_parent_ids: list[str] = Field(default_factory=list)
    matches: list[ChunkMatch] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class Diagnosis(BaseModel):
    failed_stage: FailureStage
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class Recommendation(BaseModel):
    target: str
    action: str
    rationale: str
    risk: str = Field(pattern="^(low|medium|high)$")
    validation_plan: str


class DiagnosisReview(BaseModel):
    failed_stage: FailureStage
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommendations: list[Recommendation] = Field(default_factory=list)


class RegressionJudgement(BaseModel):
    answer_correct: bool
    citation_correct: bool
    explanation: str
