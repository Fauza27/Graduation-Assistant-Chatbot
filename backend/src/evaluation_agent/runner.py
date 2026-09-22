"""Orchestrate exhaustive original-document scans and RAG diagnosis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from config.settings import get_settings
from src.evaluation_agent.incident_context import build_incident_context
from src.evaluation_agent.chunk_auditor import audit_chunks
from src.evaluation_agent.document_reader import (
    PROJECT_ROOT,
    OriginalDocumentReader,
    load_document_manifest,
)
from src.evaluation_agent.evidence_search import (
    OriginalDocumentIndex,
)
from src.evaluation_agent.evidence_validation import (
    grounded_numbers,
    validate_quote,
    validate_semantic_fit,
)
from src.evaluation_agent.model_client import (
    EvaluatorModel,
    OpenAIEvaluatorModel,
    get_evaluator_model,
)
from src.evaluation_agent.models import (
    ChunkAudit,
    DiagnosisReview,
    EVALUATION_QUEUE_STATUSES,
    EvaluationCase,
    EvidenceCandidate,
    FailureStage,
    PageWindow,
    QuestionPlan,
    RegisteredDocument,
)
from src.evaluation_agent.question_planner import (
    fallback_question_plan,
    normalize_question_plan,
    required_need_ids,
)
from src.evaluation_agent.report import write_report
from src.evaluation_agent.review_policy import constrain_review
from src.evaluation_agent.repository import (
    EvaluationRepository,
    get_evaluation_repository,
)
from src.evaluation_agent.trace_analyzer import analyze_trace, analyze_query_scope
from src.evaluation_agent.system_context import build_system_context


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EvidenceAssessment:
    """Separate direct evidence from evidence with a different scope."""

    direct: EvidenceCandidate | None = None
    supporting: tuple[EvidenceCandidate, ...] = ()
    related_scope: EvidenceCandidate | None = None
    candidates_checked: int = 0
    attempts: tuple[dict, ...] = ()
    reference_answer: str = ""
    covered_need_ids: tuple[str, ...] = ()
    required_need_ids: tuple[str, ...] = ()

    @property
    def discovery_status(self) -> str:
        if self.direct is not None:
            return "verified"
        if self.supporting:
            return "partial_evidence"
        if self.related_scope is not None:
            return "related_scope_only"
        return "inconclusive"

    @property
    def verified_evidence(self) -> tuple[EvidenceCandidate, ...]:
        if self.supporting:
            return self.supporting
        return (self.direct,) if self.direct is not None else ()


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

    def register_documents(
        self, domains: set[str] | None = None
    ) -> list[RegisteredDocument]:
        specs = load_document_manifest(self.settings.EVALUATION_DOCUMENT_MANIFEST)
        if domains:
            specs = [spec for spec in specs if spec.domain in domains]
        return [
            self.repository.register_document(
                spec, page_count=len(self.reader.read_pages(spec.path))
            )
            for spec in specs
        ]

    def run(self, case_ids: set[str] | None = None) -> tuple[str, Path]:
        cases = self.repository.list_cases(list(EVALUATION_QUEUE_STATUSES))
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
            "evaluation_protocol_version": "2026-09-23-document-routed",
            "context_source": "original_student_questions",
            "manifest": self.settings.EVALUATION_DOCUMENT_MANIFEST,
            "page_window": self.settings.EVALUATION_PAGE_WINDOW,
            "candidate_windows_per_case": (
                self.settings.EVALUATION_CANDIDATE_WINDOWS_PER_CASE
            ),
            "context_turns": self.settings.EVALUATION_CONTEXT_TURNS,
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
            cases = self.repository.enrich_cases_with_context(
                cases,
                max_turns=self.settings.EVALUATION_CONTEXT_TURNS,
            )
            specs = load_document_manifest(self.settings.EVALUATION_DOCUMENT_MANIFEST)
            available_domains = sorted({spec.domain for spec in specs})
            cases = self._plan_cases(cases, available_domains)
            routed_domains = {
                domain
                for case in cases
                for domain in case.question_plan.target_domains
                if case.question_plan is not None
            }
            documents = [
                self.repository.register_document(
                    spec, page_count=len(self.reader.read_pages(spec.path))
                )
                for spec in specs
                if spec.domain in routed_domains
            ]
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

    def _plan_cases(
        self, cases: list[EvaluationCase], available_domains: list[str]
    ) -> list[EvaluationCase]:
        """Plan questions per conversation before any source document is scanned."""

        groups: dict[str, list[EvaluationCase]] = defaultdict(list)
        for case in cases:
            groups[case.session_id or f"case:{case.case_id}"].append(case)

        planned: dict[str, QuestionPlan] = {}
        planner = getattr(self.model, "plan_questions", None)
        for group in groups.values():
            raw_plans: list[QuestionPlan] = []
            if callable(planner):
                try:
                    raw_plans = planner(group, available_domains)
                except Exception:
                    logger.exception(
                        "Question planner gagal; menggunakan routing konservatif untuk {} case",
                        len(group),
                    )
            raw_by_case = {plan.case_id: plan for plan in raw_plans}
            for case in group:
                raw = raw_by_case.get(case.case_id) or fallback_question_plan(
                    case, available_domains
                )
                planned[case.case_id] = normalize_question_plan(
                    raw, case, available_domains
                )

        return [
            case.model_copy(update={"question_plan": planned[case.case_id]})
            for case in cases
        ]

    def _discover_evidence(
        self,
        cases: list[EvaluationCase],
        documents: list[RegisteredDocument],
    ) -> dict[str, list[EvidenceCandidate]]:
        available_domains = {document.spec.domain for document in documents}
        search_cases = [
            case
            if case.question_plan is not None
            else case.model_copy(
                update={
                    "question_plan": fallback_question_plan(case, available_domains)
                }
            )
            for case in cases
        ]
        found: dict[str, list[EvidenceCandidate]] = {
            case.case_id: [] for case in cases
        }
        limit = self.settings.EVALUATION_CANDIDATE_WINDOWS_PER_CASE
        for document in documents:
            relevant_cases = [
                case
                for case in search_cases
                if case.question_plan is not None
                and document.spec.domain in case.question_plan.target_domains
            ]
            if not relevant_cases:
                continue
            logger.info(
                "Memindai dokumen asli {} untuk {} pertanyaan relevan",
                document.spec.title,
                len(relevant_cases),
            )
            pages = self.reader.read_pages(document.spec.path)
            windows = self.reader.build_windows(
                pages,
                document_slug=document.spec.slug,
                document_title=document.spec.title,
                version_id=document.version_id,
                window_size=self.settings.EVALUATION_PAGE_WINDOW,
            )
            index = OriginalDocumentIndex(
                [(window, document.spec.domain) for window in windows]
            )
            for case in relevant_cases:
                route_count = max(1, len(case.question_plan.target_domains))
                per_document_limit = max(2, (limit + route_count - 1) // route_count)
                ranked = index.search(
                    case,
                    limit=per_document_limit,
                    allowed_domains={document.spec.domain},
                )
                found[case.case_id].extend(
                    EvidenceCandidate(
                        case_id=case.case_id,
                        version_id=item.window.version_id,
                        document_slug=item.window.document_slug,
                        document_title=item.window.document_title,
                        page_start=item.window.page_start,
                        page_end=item.window.page_end,
                        evidence_text=item.snippet,
                        explanation=(
                            "Kandidat dari indeks halaman asli; istilah cocok: "
                            + ", ".join(item.matched_terms)
                        ),
                        confidence=min(0.99, item.score / (item.score + 5.0)),
                    )
                    for item in ranked
                )
                logger.debug(
                    "Evidence search case={} domain={} candidates={}",
                    case.case_id,
                    document.spec.domain,
                    len(ranked),
                )
        return found

    def _diagnose_cases(
        self,
        run_id: str,
        cases: list[EvaluationCase],
        documents: list[RegisteredDocument],
        evidence_by_case: dict[str, list[EvidenceCandidate]],
    ) -> tuple[list[dict], int]:
        document_by_version = {item.version_id: item for item in documents}
        chunk_cache: dict[str, tuple[list[dict], list[dict]]] = {}
        evidence_cache: dict[tuple, EvidenceAssessment] = {}
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
                evidence_key = (
                    case.question,
                    case.context_text,
                    case.question_plan.model_dump_json()
                    if case.question_plan is not None
                    else "",
                )
                if evidence_key not in evidence_cache:
                    evidence_cache[evidence_key] = self._assess_evidence(
                        case,
                        evidence_by_case.get(case.case_id, []),
                        document_by_version,
                    )
                cached = evidence_cache[evidence_key]
                assessment = replace(
                    cached,
                    direct=cached.direct.model_copy(update={"case_id": case.case_id})
                    if cached.direct
                    else None,
                    supporting=tuple(
                        evidence.model_copy(update={"case_id": case.case_id})
                        for evidence in cached.supporting
                    ),
                    related_scope=cached.related_scope.model_copy(
                        update={"case_id": case.case_id}
                    )
                    if cached.related_scope
                    else None,
                )
                candidate_summaries = [
                    {
                        "document_slug": candidate.document_slug,
                        "pages": [candidate.page_start, candidate.page_end],
                        "confidence": candidate.confidence,
                        "explanation": candidate.explanation,
                    }
                    for candidate in evidence_by_case.get(case.case_id, [])
                ]
                verified = assessment.direct
                verified_evidence = assessment.verified_evidence
                related_scope = assessment.related_scope
                answer_available = verified is not None
                audit = ChunkAudit(
                    status="not_applicable",
                    explanation="Tidak ada bukti terverifikasi untuk dibandingkan.",
                )
                audits: list[ChunkAudit] = []
                for evidence in verified_evidence:
                    document = document_by_version[evidence.version_id]
                    if evidence.version_id not in chunk_cache:
                        children = self.repository.load_chunks(document)
                        chunk_cache[evidence.version_id] = (
                            children,
                            self.repository.load_parents(children),
                        )
                    audits.append(
                        audit_chunks(evidence, *chunk_cache[evidence.version_id])
                    )
                    self.repository.save_evidence(run_id, evidence)
                if audits:
                    audit = _merge_chunk_audits(audits)
                if related_scope is not None:
                    self.repository.save_evidence(run_id, related_scope)

                trace = self.repository.load_trace(case.request_id)
                preliminary = analyze_trace(
                    answer_available=answer_available,
                    chunk_audit=audit,
                    trace=trace,
                    queue_reason=case.queue_reason,
                    has_related_scope_evidence=related_scope is not None,
                    evidence_discovery_status=assessment.discovery_status,
                )
                if verified is not None:
                    preliminary = analyze_query_scope(case, trace) or preliminary
                answer_assessment = None
                evidence_text = _format_evidence(verified_evidence)
                if verified is not None and case.actual_answer:
                    answer_assessment = self.model.assess_answer(
                        case, evidence_text
                    )
                if (
                    verified is not None
                    and not case.actual_answer
                    and not trace.get("error_stage")
                ):
                    preliminary = preliminary.model_copy(
                        update={
                            "failed_stage": FailureStage.UNKNOWN,
                            "root_cause": "Jawaban chatbot tidak tersimpan; kualitas jawabannya belum dapat dinilai.",
                            "confidence": 0.3,
                        }
                    )
                system_context = build_system_context(
                    preliminary.failed_stage.value, trace, self.settings
                )
                incident_facts = build_incident_context(trace, audit, preliminary)
                if answer_assessment and answer_assessment.verdict in {
                    "correct",
                    "uncertain",
                }:
                    review = DiagnosisReview(
                        failed_stage=FailureStage.UNKNOWN
                        if answer_assessment.verdict == "correct"
                        else FailureStage.AMBIGUOUS,
                        root_cause=answer_assessment.explanation,
                        confidence=0.6
                        if answer_assessment.verdict == "correct"
                        else 0.35,
                        recommendations=[],
                    )
                elif verified is None or preliminary.failed_stage in {
                    FailureStage.AMBIGUOUS,
                    FailureStage.UNKNOWN,
                }:
                    review = DiagnosisReview(
                        failed_stage=preliminary.failed_stage,
                        root_cause=preliminary.root_cause,
                        confidence=preliminary.confidence,
                        recommendations=[],
                    )
                else:
                    review = self.model.review_diagnosis(
                        case=case,
                        evidence_text=evidence_text,
                        chunk_audit=audit,
                        trace=trace,
                        preliminary=preliminary,
                        system_context=system_context,
                    )
                    review = constrain_review(review, preliminary, system_context)
                self.repository.save_finding(
                    run_id,
                    case.case_id,
                    answer_available,
                    audit,
                    review,
                    diagnostics={
                        "chunk_audit": audit.diagnostics,
                        "trace_analysis": preliminary.model_dump(mode="json"),
                        "system_context": system_context,
                        "incident_facts": incident_facts,
                        "queue_reason": case.queue_reason,
                        "has_related_scope_evidence": related_scope is not None,
                        "evidence_discovery_status": assessment.discovery_status,
                        "evidence_candidates_checked": assessment.candidates_checked,
                        "standalone_question": case.evidence_question,
                        "conversation_context": case.context_text,
                        "recorded_resolved_query": case.standalone_question,
                        "evidence_candidates": candidate_summaries,
                        "verification_attempts": list(assessment.attempts),
                        "reference_answer": assessment.reference_answer,
                        "question_plan": case.question_plan.model_dump(mode="json")
                        if case.question_plan is not None
                        else None,
                        "covered_need_ids": list(assessment.covered_need_ids),
                        "required_need_ids": list(assessment.required_need_ids),
                        "answer_assessment": answer_assessment.model_dump(mode="json")
                        if answer_assessment
                        else None,
                    },
                )
                result = {
                    "case_id": case.case_id,
                    "question": case.question,
                    "standalone_question": case.evidence_question,
                    "conversation_context": case.context_text,
                    "recorded_resolved_query": case.standalone_question,
                    "question_plan": case.question_plan.model_dump(mode="json")
                    if case.question_plan is not None
                    else None,
                    "answer_available": answer_available,
                    "evidence": verified.model_dump(mode="json") if verified else None,
                    "supporting_evidence": [
                        evidence.model_dump(mode="json")
                        for evidence in verified_evidence
                    ],
                    "related_scope_evidence": (
                        related_scope.model_dump(mode="json")
                        if related_scope is not None
                        else None
                    ),
                    "chunk_audit": audit.model_dump(mode="json"),
                    "diagnosis": review.model_dump(mode="json"),
                    "answer_assessment": answer_assessment.model_dump(mode="json")
                    if answer_assessment
                    else None,
                    "system_context": system_context,
                    "incident_facts": incident_facts,
                    "evidence_search": {
                        "status": assessment.discovery_status,
                        "candidates_checked": assessment.candidates_checked,
                        "candidates": candidate_summaries,
                        "verification_attempts": list(assessment.attempts),
                        "reference_answer": assessment.reference_answer,
                        "covered_need_ids": list(assessment.covered_need_ids),
                        "required_need_ids": list(assessment.required_need_ids),
                    },
                }
                results.append(result)
                logger.info(
                    "Evaluasi case={} evidence={} stage={}",
                    case.case_id,
                    assessment.discovery_status,
                    review.failed_stage.value,
                )
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

    def _assess_evidence(
        self,
        case: EvaluationCase,
        candidates: list[EvidenceCandidate],
        documents: dict[str, RegisteredDocument],
    ) -> EvidenceAssessment:
        plan = case.question_plan or fallback_question_plan(
            case, {document.spec.domain for document in documents.values()}
        )
        required = required_need_ids(plan)
        covered: set[str] = set()
        supporting: list[EvidenceCandidate] = []
        related_scope: EvidenceCandidate | None = None
        attempts: list[dict] = []
        domains = set(plan.target_domains)
        for candidate in candidates:
            document = documents[candidate.version_id]
            attempt = {
                "document_slug": candidate.document_slug,
                "candidate_pages": [candidate.page_start, candidate.page_end],
            }
            attempts.append(attempt)
            if domains and document.spec.domain not in domains:
                attempt["rejection"] = "document_domain_mismatch"
                continue
            pages = self.reader.read_pages(document.spec.path)
            start = max(1, candidate.page_start - 1)
            end = min(len(pages), candidate.page_end + 1)
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
            attempt["verification"] = verification.model_dump(mode="json")
            contributes = verification.answers_question or verification.verdict == "partial"
            if not contributes and not verification.is_related_scope:
                continue
            rejection = validate_quote(verification, context_pages)
            if rejection is None and not grounded_numbers(
                verification.reference_answer, verification.corrected_evidence_text
            ):
                rejection = "reference_answer_invents_numbers"
            if rejection is None:
                rejection = validate_semantic_fit(verification)
            covered_by_quote = set(verification.covered_need_ids).intersection(required)
            applicable_needs = {
                need.need_id
                for need in plan.information_needs
                if not need.domains or document.spec.domain in need.domains
            }
            if contributes and not covered_by_quote:
                rejection = rejection or "no_information_need_covered"
            if covered_by_quote.difference(applicable_needs):
                rejection = rejection or "covered_need_wrong_document"
            if rejection:
                attempt["rejection"] = rejection
                continue
            assessed = candidate.model_copy(
                update={
                    "page_start": verification.page_start,
                    "page_end": verification.page_end,
                    "evidence_text": verification.corrected_evidence_text.strip(),
                    "explanation": verification.explanation,
                    "confidence": verification.confidence,
                    "covered_need_ids": sorted(covered_by_quote),
                    "reference_answer": verification.reference_answer,
                }
            )
            if contributes:
                new_needs = covered_by_quote.difference(covered)
                if not new_needs:
                    attempt["rejection"] = "duplicate_information_coverage"
                    continue
                supporting.append(assessed)
                covered.update(new_needs)
                if required.issubset(covered):
                    break
                continue
            related_scope = related_scope or assessed

        route_is_unresolved = plan.is_ambiguous and len(plan.target_domains) > 1
        complete = (
            bool(required)
            and required.issubset(covered)
            and not route_is_unresolved
        )
        finalized = tuple(
            evidence.model_copy(update={"is_verified": complete})
            for evidence in supporting
        )
        reference_answer = "\n".join(
            dict.fromkeys(
                evidence.reference_answer
                for evidence in finalized
                if evidence.reference_answer.strip()
            )
        )
        return EvidenceAssessment(
            direct=finalized[0] if complete else None,
            supporting=finalized,
            related_scope=related_scope,
            candidates_checked=len(attempts),
            attempts=tuple(attempts),
            reference_answer=reference_answer,
            covered_need_ids=tuple(sorted(covered)),
            required_need_ids=tuple(sorted(required)),
        )


def _format_evidence(items: tuple[EvidenceCandidate, ...]) -> str:
    return "\n\n".join(
        f"[{item.document_title}, halaman {item.page_start}-{item.page_end}]\n"
        f"{item.evidence_text}"
        for item in items
    )


def _merge_chunk_audits(audits: list[ChunkAudit]) -> ChunkAudit:
    """Combine audits for questions supported by more than one document."""

    if len(audits) == 1:
        return audits[0]
    statuses = {audit.status for audit in audits}
    if statuses == {"chunking_valid"}:
        status = "chunking_valid"
    elif any(value.startswith("extraction") for value in statuses):
        status = next(value for value in statuses if value.startswith("extraction"))
    elif "inconclusive" in statuses:
        status = "inconclusive"
    else:
        status = next(value for value in statuses if value != "chunking_valid")
    return ChunkAudit(
        status=status,
        explanation=" ".join(dict.fromkeys(audit.explanation for audit in audits)),
        affected_chunk_ids=list(
            dict.fromkeys(
                chunk_id for audit in audits for chunk_id in audit.affected_chunk_ids
            )
        ),
        matched_parent_ids=list(
            dict.fromkeys(
                parent_id for audit in audits for parent_id in audit.matched_parent_ids
            )
        ),
        matches=[match for audit in audits for match in audit.matches],
        diagnostics={
            "source_audits": [audit.model_dump(mode="json") for audit in audits]
        },
    )
