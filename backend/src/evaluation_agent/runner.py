"""Orchestrate exhaustive original-document scans and RAG diagnosis."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from loguru import logger

from config.settings import get_settings
from src.evaluation_agent.chunk_auditor import audit_chunks
from src.evaluation_agent.document_reader import (
    PROJECT_ROOT,
    OriginalDocumentReader,
    load_document_manifest,
)
from src.evaluation_agent.model_client import (
    EvaluatorModel,
    OpenAIEvaluatorModel,
    get_evaluator_model,
)
from src.evaluation_agent.models import (
    ChunkAudit,
    EvaluationCase,
    EvidenceCandidate,
    PageWindow,
    RegisteredDocument,
)
from src.evaluation_agent.report import write_report
from src.evaluation_agent.repository import (
    EvaluationRepository,
    get_evaluation_repository,
)
from src.evaluation_agent.trace_analyzer import analyze_trace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _batches(items: list[EvaluationCase], size: int) -> Iterable[list[EvaluationCase]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


class EvaluationRunner:
    """Run evidence discovery once per document for all pending failure cases."""

    def __init__(
        self,
        repository: EvaluationRepository | None = None,
        model: EvaluatorModel | None = None,
        reader: OriginalDocumentReader | None = None,
    ) -> None:
        self.settings = get_settings()
        self.repository = repository or get_evaluation_repository()
        self._model = model
        self.reader = reader or OriginalDocumentReader()

    @property
    def model(self) -> EvaluatorModel:
        if self._model is None:
            self._model = get_evaluator_model()
        return self._model

    def register_documents(self) -> list[RegisteredDocument]:
        specs = load_document_manifest(self.settings.EVALUATION_DOCUMENT_MANIFEST)
        return [self.repository.register_document(spec) for spec in specs]

    def run(self, case_ids: set[str] | None = None) -> tuple[str, Path]:
        cases = self.repository.list_cases(["incorrect", "incomplete", "uncertain"])
        if case_ids is not None:
            cases = [case for case in cases if case.case_id in case_ids]
        if not cases:
            raise ValueError("Tidak ada evaluation case gagal yang dapat diproses")

        model_name = getattr(self.model, "model_name", type(self.model).__name__)
        run_id = self.repository.create_run(
            model=model_name,
            case_ids=[case.case_id for case in cases],
            config=self._run_config(),
        )
        return self._execute(run_id, cases)

    def run_existing(self, run_id: str) -> tuple[str, Path]:
        """Execute a pending database run created by the admin API."""
        run = self.repository.get_run(run_id)
        if self._model is None:
            self._model = OpenAIEvaluatorModel(str(run["evaluator_model"]))
        case_ids = self.repository.get_run_case_ids(run_id)
        cases = self.repository.get_cases(case_ids)
        if len(cases) != len(case_ids):
            raise ValueError("Sebagian evaluation case pada run tidak ditemukan")
        if not cases:
            raise ValueError("Evaluation run tidak memiliki case")
        return self._execute(run_id, cases)

    def _run_config(self, documents: list[RegisteredDocument] | None = None) -> dict:
        config = {
            "manifest": self.settings.EVALUATION_DOCUMENT_MANIFEST,
            "page_window": self.settings.EVALUATION_PAGE_WINDOW,
            "question_batch_size": self.settings.EVALUATION_QUESTION_BATCH_SIZE,
            "max_evidence_per_case": self.settings.EVALUATION_MAX_EVIDENCE_PER_CASE,
        }
        if documents is not None:
            config["document_checksums"] = {
                item.spec.slug: item.checksum_sha256 for item in documents
            }
        return config

    def _execute(self, run_id: str, cases: list[EvaluationCase]) -> tuple[str, Path]:
        if not self.repository.claim_run(run_id):
            raise RuntimeError(
                "Evaluation run sedang diproses atau sudah selesai; buat batch baru"
            )
        try:
            documents = self.register_documents()
            self.repository.update_run(
                run_id,
                configuration=self._run_config(documents),
                error_message=None,
                completed_at=None,
            )
            evidence_by_case = self._discover_evidence(cases, documents)
            results, failed_cases = self._diagnose_cases(
                run_id, cases, documents, evidence_by_case
            )
            report_path = write_report(run_id, results, PROJECT_ROOT)
            self.repository.update_run(
                run_id,
                status="completed" if failed_cases == 0 else "failed",
                processed_cases=len(results),
                error_message=(
                    None
                    if failed_cases == 0
                    else f"{failed_cases} case gagal diproses; laporan parsial tersedia"
                ),
                completed_at=_now(),
            )
            return run_id, report_path
        except Exception as exc:
            self.repository.update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                completed_at=_now(),
            )
            raise

    def _discover_evidence(
        self,
        cases: list[EvaluationCase],
        documents: list[RegisteredDocument],
    ) -> dict[str, list[EvidenceCandidate]]:
        found: dict[str, list[EvidenceCandidate]] = defaultdict(list)
        for document in documents:
            logger.info("Membaca seluruh dokumen asli: {}", document.spec.title)
            pages = self.reader.read_pages(document.spec.path)
            windows = self.reader.build_windows(
                pages,
                document_slug=document.spec.slug,
                document_title=document.spec.title,
                version_id=document.version_id,
                window_size=self.settings.EVALUATION_PAGE_WINDOW,
            )
            for window in windows:
                for case_batch in _batches(
                    cases, self.settings.EVALUATION_QUESTION_BATCH_SIZE
                ):
                    allowed_case_ids = {case.case_id for case in case_batch}
                    for candidate in self.model.scan_window(case_batch, window):
                        if (
                            candidate.case_id not in allowed_case_ids
                            or not candidate.is_relevant
                            or not candidate.evidence_text.strip()
                        ):
                            continue
                        page_start = min(
                            window.page_end,
                            max(
                                window.page_start,
                                candidate.page_start or window.page_start,
                            ),
                        )
                        page_end = min(
                            window.page_end,
                            max(page_start, candidate.page_end or window.page_end),
                        )
                        found[candidate.case_id].append(
                            EvidenceCandidate(
                                case_id=candidate.case_id,
                                version_id=document.version_id,
                                document_slug=document.spec.slug,
                                document_title=document.spec.title,
                                page_start=page_start,
                                page_end=max(page_start, page_end),
                                evidence_text=candidate.evidence_text.strip(),
                                explanation=candidate.explanation,
                                confidence=candidate.confidence,
                            )
                        )
        limit = self.settings.EVALUATION_MAX_EVIDENCE_PER_CASE
        unique: dict[str, list[EvidenceCandidate]] = {}
        for case_id, items in found.items():
            deduplicated: dict[tuple[str, str], EvidenceCandidate] = {}
            for item in items:
                key = (item.version_id, " ".join(item.evidence_text.lower().split()))
                previous = deduplicated.get(key)
                if previous is None or item.confidence > previous.confidence:
                    deduplicated[key] = item
            unique[case_id] = sorted(
                deduplicated.values(), key=lambda item: item.confidence, reverse=True
            )[:limit]
        return unique

    def _diagnose_cases(
        self,
        run_id: str,
        cases: list[EvaluationCase],
        documents: list[RegisteredDocument],
        evidence_by_case: dict[str, list[EvidenceCandidate]],
    ) -> tuple[list[dict], int]:
        document_by_version = {item.version_id: item for item in documents}
        results: list[dict] = []
        processed = 0
        failed = 0
        for case in cases:
            self.repository.clear_case_results(run_id, case.case_id)
            self.repository.update_run_case(
                run_id,
                case.case_id,
                status="processing",
                started_at=_now(),
                completed_at=None,
                error_message=None,
            )
            try:
                verified = self._verify_best_evidence(
                    case, evidence_by_case.get(case.case_id, []), document_by_version
                )
                answer_available = verified is not None
                audit = ChunkAudit(
                    status="not_applicable",
                    explanation="Tidak ada bukti terverifikasi untuk dibandingkan.",
                )
                if verified is not None:
                    document = document_by_version[verified.version_id]
                    audit = audit_chunks(
                        verified, self.repository.load_chunks(document)
                    )
                    self.repository.save_evidence(run_id, verified)

                trace = self.repository.load_trace(case.request_id)
                preliminary = analyze_trace(
                    answer_available=answer_available,
                    chunk_audit=audit,
                    trace=trace,
                )
                review = self.model.review_diagnosis(
                    case=case,
                    evidence_text=verified.evidence_text if verified else "",
                    chunk_audit=audit,
                    trace=trace,
                    preliminary=preliminary,
                )
                self.repository.save_finding(
                    run_id, case.case_id, answer_available, audit, review
                )
                result = {
                    "case_id": case.case_id,
                    "question": case.question,
                    "answer_available": answer_available,
                    "evidence": verified.model_dump(mode="json") if verified else None,
                    "chunk_audit": audit.model_dump(mode="json"),
                    "diagnosis": review.model_dump(mode="json"),
                }
                results.append(result)
                self.repository.update_run_case(
                    run_id, case.case_id, status="completed", completed_at=_now()
                )
                processed += 1
                self.repository.update_run(run_id, processed_cases=processed)
            except Exception as exc:
                failed += 1
                logger.exception("Evaluasi case {} gagal", case.case_id)
                self.repository.update_run_case(
                    run_id,
                    case.case_id,
                    status="failed",
                    error_message=str(exc),
                    completed_at=_now(),
                )
        return results, failed

    def _verify_best_evidence(
        self,
        case: EvaluationCase,
        candidates: list[EvidenceCandidate],
        documents: dict[str, RegisteredDocument],
    ) -> EvidenceCandidate | None:
        for candidate in candidates:
            document = documents[candidate.version_id]
            pages = self.reader.read_pages(document.spec.path)
            start = max(1, candidate.page_start - 2)
            end = min(len(pages), candidate.page_end + 2)
            context_pages = pages[start - 1 : end]
            window = PageWindow(
                document_slug=document.spec.slug,
                document_title=document.spec.title,
                version_id=document.version_id,
                page_start=start,
                page_end=end,
                text="\n\n".join(
                    f"--- HALAMAN FISIK {page.page_number} ---\n{page.text}"
                    for page in context_pages
                ),
                has_extraction_warning=any(
                    page.extraction_warning for page in context_pages
                ),
            )
            verification = self.model.verify_evidence(
                case, window, candidate.evidence_text
            )
            if verification.answers_question and verification.answer_available:
                verified_start = min(
                    end,
                    max(start, verification.page_start or candidate.page_start),
                )
                verified_end = min(
                    end,
                    max(
                        verified_start,
                        verification.page_end or candidate.page_end,
                    ),
                )
                return candidate.model_copy(
                    update={
                        "page_start": verified_start,
                        "page_end": verified_end,
                        "evidence_text": (
                            verification.corrected_evidence_text.strip()
                            or candidate.evidence_text
                        ),
                        "explanation": verification.explanation,
                        "confidence": verification.confidence,
                        "is_verified": True,
                    }
                )
        return None
