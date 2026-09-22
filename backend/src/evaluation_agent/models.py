"""Typed contracts shared by the RAG evaluation workflow."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

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


class ConversationTurn(BaseModel):
    """Prior interaction used to resolve short follow-up questions."""

    question: str
    answer: str | None = None
    resolved_question: str | None = None


AcademicDomain = Literal["PI", "KKP", "SKRIPSI", "NON_SKRIPSI"]


class InformationNeed(BaseModel):
    """One fact that must be supported before a question is considered answered."""

    need_id: str = Field(pattern=r"^[a-z0-9_]+$")
    description: str = Field(min_length=3, max_length=300)
    domains: list[AcademicDomain] = Field(default_factory=list)


class QuestionPlan(BaseModel):
    """Document routing and evidence requirements for one evaluation case."""

    case_id: str
    resolved_question: str = Field(min_length=3, max_length=1000)
    target_domains: list[AcademicDomain] = Field(default_factory=list)
    information_needs: list[InformationNeed] = Field(default_factory=list)
    question_type: Literal[
        "single_fact", "multi_fact", "comparison", "availability", "ambiguous"
    ] = "single_fact"
    is_ambiguous: bool = False
    ambiguity_reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class QuestionPlanBatch(BaseModel):
    plans: list[QuestionPlan]


class EvaluationCase(BaseModel):
    case_id: str
    request_id: str | None = None
    question: str
    actual_answer: str | None = None
    review_status: ReviewStatus
    queue_reason: str = "manual_admin"
    expected_answer: str | None = None
    expected_evidence: dict[str, Any] | None = None
    review_notes: str | None = None
    created_by: str | None = None
    session_id: str | None = None
    standalone_question: str | None = None
    prior_questions: list[str] = Field(default_factory=list)
    conversation_context: list[ConversationTurn] = Field(default_factory=list)
    question_plan: QuestionPlan | None = None

    @property
    def evidence_question(self) -> str:
        """Use the student's words; historical rewrites are diagnostic data only."""

        return self.question.strip()

    @property
    def context_text(self) -> str:
        """Compact, human-readable context for evaluator prompts."""

        questions = self.prior_questions[-20:] or [
            turn.question for turn in self.conversation_context
        ]
        if not questions:
            return "-"
        return "\n".join(f"Mahasiswa: {question}" for question in questions)


class EvidenceDecision(BaseModel):
    """One semantic verdict, with a source quote and answer before the decision."""

    explanation: str = Field(
        description="Alasan singkat hubungan bukti dengan pertanyaan."
    )
    quote: str = Field(
        description="Satu kutipan persis dari halaman sumber; kosong jika tidak ada."
    )
    page_start: int | None
    page_end: int | None
    reference_answer: str = Field(
        description="Jawaban singkat berdasarkan kutipan; kosong jika tidak menjawab."
    )
    verdict: Literal["supported", "partial", "related_scope", "not_found"]
    scope_note: str = Field(
        description="Perbedaan cakupan konkret jika ada; jangan mengulang penolakan umum."
    )
    covered_need_ids: list[str] = Field(
        description="ID kebutuhan informasi yang didukung langsung oleh kutipan.",
    )
    subject_matches: bool = Field(
        description="Subjek kutipan sama dengan subjek pertanyaan."
    )
    attribute_matches: bool = Field(
        description="Atribut yang dijelaskan kutipan sama dengan yang ditanyakan.",
    )
    scope_matches: bool = Field(
        description="Jalur dan tahap akademik sesuai pertanyaan."
    )
    unit_matches: bool = Field(
        description="Satuan atau jenis ukuran sesuai pertanyaan."
    )
    confidence: float = Field(ge=0.0, le=1.0)


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
    covered_need_ids: list[str] = Field(default_factory=list)
    reference_answer: str = ""


class EvidenceVerification(BaseModel):
    answers_question: bool
    answer_available: bool
    is_related_scope: bool = False
    scope_note: str = ""
    page_start: int | None = None
    page_end: int | None = None
    corrected_evidence_text: str = ""
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    reference_answer: str = ""
    verdict: str = ""
    covered_need_ids: list[str] = Field(default_factory=list)
    subject_matches: bool = True
    attribute_matches: bool = True
    scope_matches: bool = True
    unit_matches: bool = True


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
    target: str = Field(description="File/fungsi atau parameter sistem yang dituju.")
    action: str = Field(
        description="1-3 kalimat: perubahan konkret yang diusulkan dan tujuannya."
    )
    rationale: str = Field(
        description="Satu kalimat bukti pendukung untuk catatan internal."
    )
    risk: str = Field(pattern="^(low|medium|high)$")
    validation_plan: str = Field(
        description="Satu kalimat cara menguji perbaikan untuk catatan internal."
    )


class DiagnosisReview(BaseModel):
    failed_stage: FailureStage
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommendations: list[Recommendation] = Field(default_factory=list)


class RegressionJudgement(BaseModel):
    answer_correct: bool
    citation_correct: bool
    explanation: str


class AnswerAssessment(BaseModel):
    explanation: str
    verdict: Literal["correct", "incorrect", "incomplete", "uncertain"]
