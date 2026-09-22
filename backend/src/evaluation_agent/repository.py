"""Supabase persistence boundary for evaluation jobs and artifacts."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from config.settings import get_settings
from src.evaluation_agent.incident_context import describe_reranking_failure
from src.evaluation_agent.document_reader import (
    PROJECT_ROOT,
    OriginalDocumentReader,
    sha256_file,
)
from src.evaluation_agent.models import (
    ChunkAudit,
    ConversationTurn,
    DiagnosisReview,
    DocumentSpec,
    EvaluationCase,
    EvidenceCandidate,
    RegisteredDocument,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _all_rows(query, page_size: int = 500) -> list[dict]:
    """Supabase's response cap must not silently truncate evaluation evidence."""
    rows: list[dict] = []
    offset = 0
    while True:
        batch = list(query.range(offset, offset + page_size - 1).execute().data or [])
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def attach_case_context(
    cases: list[EvaluationCase],
    metric_rows: list[dict],
    trace_rows: list[dict],
    *,
    max_turns: int,
) -> list[EvaluationCase]:
    """Attach the recorded standalone query and preceding session turns.

    This is intentionally pure so context reconstruction can be tested without a
    database. The source rows remain the durable request and trace records.
    """

    trace_by_request = {
        str(row.get("request_id")): row for row in trace_rows if row.get("request_id")
    }
    metrics_by_request = {
        str(row.get("request_id")): row for row in metric_rows if row.get("request_id")
    }
    metrics_by_session: dict[str, list[dict]] = defaultdict(list)
    for row in metric_rows:
        session_id = row.get("session_id")
        if session_id:
            metrics_by_session[str(session_id)].append(row)
    for rows in metrics_by_session.values():
        rows.sort(
            key=lambda row: (
                str(row.get("created_at", "")),
                str(row.get("request_id", "")),
            )
        )

    enriched: list[EvaluationCase] = []
    for case in cases:
        request_id = str(case.request_id or "")
        current_metric = metrics_by_request.get(request_id, {})
        current_trace = trace_by_request.get(request_id, {})
        query_plan = current_trace.get("query_plan") or {}
        standalone = _compact_text(query_plan.get("resolved_query"), 500) or None

        session_rows = metrics_by_session.get(
            str(current_metric.get("session_id") or ""), []
        )
        current_position = next(
            (
                index
                for index, row in enumerate(session_rows)
                if str(row.get("request_id")) == request_id
            ),
            len(session_rows),
        )
        prior_rows = session_rows[
            max(0, current_position - max_turns) : current_position
        ]
        context: list[ConversationTurn] = []
        for row in prior_rows:
            prior_id = str(row.get("request_id") or "")
            prior_trace = trace_by_request.get(prior_id, {})
            prior_plan = prior_trace.get("query_plan") or {}
            question = _compact_text(row.get("question"), 300)
            if not question:
                continue
            context.append(
                ConversationTurn(
                    question=question,
                    answer=_compact_text(prior_trace.get("answer"), 600) or None,
                    resolved_question=(
                        _compact_text(prior_plan.get("resolved_query"), 500) or None
                    ),
                )
            )
        enriched.append(
            case.model_copy(
                update={
                    "session_id": str(current_metric.get("session_id") or "") or None,
                    "standalone_question": standalone,
                    "conversation_context": context,
                    "prior_questions": [
                        str(row["question"]).strip()
                        for row in session_rows[:current_position]
                        if row.get("question")
                    ],
                }
            )
        )
    return enriched


class EvaluationRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def register_document(
        self, spec: DocumentSpec, *, page_count: int | None = None
    ) -> RegisteredDocument:
        checksum = sha256_file(spec.path)
        document_result = (
            self.client.table("source_documents")
            .upsert(
                {
                    "slug": spec.slug,
                    "title": spec.title,
                    "domain": spec.domain,
                    "chunk_source": spec.chunk_source,
                    "is_active": True,
                    "updated_at": _now(),
                },
                on_conflict="slug",
            )
            .execute()
        )
        document_id = str(document_result.data[0]["document_id"])
        if page_count is None:
            page_count = len(OriginalDocumentReader().read_pages(spec.path))
        version_result = (
            self.client.table("source_document_versions")
            .upsert(
                {
                    "document_id": document_id,
                    "version_label": spec.version,
                    "checksum_sha256": checksum,
                    "storage_path": spec.path.relative_to(PROJECT_ROOT).as_posix(),
                    "page_count": page_count,
                    "extraction_status": "ready",
                    "extraction_error": None,
                },
                on_conflict="document_id,checksum_sha256",
            )
            .execute()
        )
        version_id = str(version_result.data[0]["version_id"])
        child_result = (
            self.client.table("child_documents")
            .select("parent_id")
            .eq("source", spec.chunk_source)
            .execute()
        )
        parent_ids = list(
            dict.fromkeys(
                str(row["parent_id"])
                for row in child_result.data or []
                if row.get("parent_id")
            )
        )
        (
            self.client.table("child_documents")
            .update({"source_document_version_id": version_id})
            .eq("source", spec.chunk_source)
            .execute()
        )
        if parent_ids:
            (
                self.client.table("parent_documents")
                .update({"source_document_version_id": version_id})
                .in_("parent_id", parent_ids)
                .execute()
            )
        return RegisteredDocument(
            document_id=document_id,
            version_id=version_id,
            spec=spec,
            checksum_sha256=checksum,
            page_count=page_count,
        )

    def list_cases(self, statuses: list[str]) -> list[EvaluationCase]:
        result = (
            self.client.table("evaluation_cases")
            .select("*")
            .in_("review_status", statuses)
            .order("created_at")
            .execute()
        )
        return [EvaluationCase.model_validate(row) for row in result.data or []]

    def get_cases(self, case_ids: list[str]) -> list[EvaluationCase]:
        if not case_ids:
            return []
        result = (
            self.client.table("evaluation_cases")
            .select("*")
            .in_("case_id", case_ids)
            .execute()
        )
        rows = {str(row["case_id"]): row for row in result.data or []}
        return [
            EvaluationCase.model_validate(rows[case_id])
            for case_id in case_ids
            if case_id in rows
        ]

    def enrich_cases_with_context(
        self,
        cases: list[EvaluationCase],
        *,
        max_turns: int,
    ) -> list[EvaluationCase]:
        """Reconstruct request-time context from metrics and execution traces."""

        request_ids = [str(case.request_id) for case in cases if case.request_id]
        if not request_ids:
            return cases
        current_result = (
            self.client.table("request_metrics")
            .select("request_id,session_id,created_at,question")
            .in_("request_id", request_ids)
            .execute()
        )
        current_rows = list(current_result.data or [])
        session_ids = list(
            dict.fromkeys(
                str(row["session_id"]) for row in current_rows if row.get("session_id")
            )
        )
        metric_rows = current_rows
        if session_ids:
            history_rows = _all_rows(
                self.client.table("request_metrics")
                .select("request_id,session_id,created_at,question")
                .in_("session_id", session_ids)
                .eq("status", "success")
                .order("created_at")
                .order("request_id")
            )
            combined_rows = {
                str(row.get("request_id")): row
                for row in [*current_rows, *history_rows]
                if row.get("request_id")
            }
            metric_rows = list(combined_rows.values())

        history_request_ids = [
            str(row["request_id"]) for row in metric_rows if row.get("request_id")
        ]
        trace_rows: list[dict] = []
        for start in range(0, len(history_request_ids), 100):
            batch = history_request_ids[start : start + 100]
            result = (
                self.client.table("rag_execution_traces")
                .select("request_id,query_plan,answer")
                .in_("request_id", batch)
                .execute()
            )
            trace_rows.extend(result.data or [])
        return attach_case_context(
            cases,
            metric_rows,
            trace_rows,
            max_turns=max_turns,
        )

    def create_case_from_request(
        self,
        request_id: str,
        *,
        review_status: str,
        expected_answer: str | None,
        expected_evidence: dict | None,
        review_notes: str | None,
        created_by: str,
        queue_reason: str = "manual_admin",
    ) -> dict:
        metric_result = (
            self.client.table("request_metrics")
            .select("request_id,question")
            .eq("request_id", request_id)
            .limit(1)
            .execute()
        )
        if not metric_result.data:
            raise LookupError("request_id tidak ditemukan")
        trace = self.load_trace(request_id)
        metric = metric_result.data[0]
        result = (
            self.client.table("evaluation_cases")
            .upsert(
                {
                    "request_id": request_id,
                    "question": metric.get("question") or "",
                    "actual_answer": trace.get("answer"),
                    "review_status": review_status,
                    "queue_reason": queue_reason,
                    "expected_answer": expected_answer,
                    "expected_evidence": expected_evidence,
                    "review_notes": review_notes,
                    "created_by": created_by,
                    "updated_at": _now(),
                },
                on_conflict="request_id",
            )
            .execute()
        )
        return dict(result.data[0])

    def get_case_by_request(self, request_id: str) -> dict | None:
        result = (
            self.client.table("evaluation_cases")
            .select("*")
            .eq("request_id", request_id)
            .limit(1)
            .execute()
        )
        return dict(result.data[0]) if result.data else None

    def update_case(self, case_id: str, fields: dict) -> dict:
        fields = {**fields, "updated_at": _now()}
        result = (
            self.client.table("evaluation_cases")
            .update(fields)
            .eq("case_id", case_id)
            .execute()
        )
        if not result.data:
            raise LookupError("evaluation case tidak ditemukan")
        return dict(result.data[0])

    def list_runs(self, limit: int = 50) -> list[dict]:
        result = (
            self.client.table("evaluation_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(result.data or [])

    def get_run_report(self, run_id: str) -> dict:
        run = (
            self.client.table("evaluation_runs")
            .select("*")
            .eq("run_id", run_id)
            .limit(1)
            .execute()
        )
        if not run.data:
            raise LookupError("evaluation run tidak ditemukan")
        findings = (
            self.client.table("evaluation_findings")
            .select("*")
            .eq("run_id", run_id)
            .execute()
        )
        finding_rows = list(findings.data or [])
        for finding in finding_rows:
            if finding["failed_stage"] == "reranking":
                reason = describe_reranking_failure(
                    finding.get("diagnostics", {}).get("incident_facts", {})
                )
                finding["root_cause"] = reason or finding["root_cause"]
        case_links = (
            self.client.table("evaluation_run_cases")
            .select("case_id,status,error_message")
            .eq("run_id", run_id)
            .execute()
        )
        case_ids = [str(row["case_id"]) for row in case_links.data or []]
        cases = self.get_cases(case_ids)
        evidence_result = (
            self.client.table("evaluation_evidence")
            .select("*")
            .eq("run_id", run_id)
            .order("confidence", desc=True)
            .execute()
        )
        finding_ids = [row["finding_id"] for row in finding_rows]
        recommendations: list[dict] = []
        if finding_ids:
            recommendation_result = (
                self.client.table("evaluation_recommendations")
                .select("*")
                .in_("finding_id", finding_ids)
                .execute()
            )
            recommendations = list(recommendation_result.data or [])
        return {
            "run": run.data[0],
            "cases": [case.model_dump(mode="json") for case in cases],
            "case_statuses": list(case_links.data or []),
            "evidence": list(evidence_result.data or []),
            "findings": finding_rows,
            "recommendations": recommendations,
        }

    def review_recommendation(
        self, recommendation_id: str, status: str, reviewed_by: str
    ) -> dict:
        result = (
            self.client.table("evaluation_recommendations")
            .update(
                {
                    "status": status,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": _now(),
                }
            )
            .eq("recommendation_id", recommendation_id)
            .execute()
        )
        if not result.data:
            raise LookupError("rekomendasi tidak ditemukan")
        return dict(result.data[0])

    def load_regression_inputs(self, run_id: str) -> list[dict]:
        links = (
            self.client.table("evaluation_run_cases")
            .select("case_id")
            .eq("run_id", run_id)
            .execute()
        )
        case_ids = [row["case_id"] for row in links.data or []]
        if not case_ids:
            return []
        cases = (
            self.client.table("evaluation_cases")
            .select("*")
            .in_("case_id", case_ids)
            .execute()
        )
        evidence = (
            self.client.table("evaluation_evidence")
            .select("case_id,evidence_text")
            .eq("run_id", run_id)
            .eq("is_verified", True)
            .execute()
        )
        findings = (
            self.client.table("evaluation_findings")
            .select("case_id,affected_chunk_ids")
            .eq("run_id", run_id)
            .execute()
        )
        evidence_parts: dict[str, list[str]] = defaultdict(list)
        for row in evidence.data or []:
            evidence_text = str(row.get("evidence_text", "")).strip()
            if evidence_text:
                evidence_parts[str(row["case_id"])].append(evidence_text)
        evidence_by_case = {
            case_id: "\n\n".join(parts) for case_id, parts in evidence_parts.items()
        }
        chunks_by_case = {
            str(row["case_id"]): row.get("affected_chunk_ids", [])
            for row in findings.data or []
        }
        return [
            {
                "case": EvaluationCase.model_validate(row),
                "evidence_text": evidence_by_case.get(str(row["case_id"]), ""),
                "affected_chunk_ids": chunks_by_case.get(str(row["case_id"]), []),
            }
            for row in cases.data or []
        ]

    def save_regression_result(self, row: dict) -> None:
        self.client.table("regression_results").insert(row).execute()

    def create_run(self, model: str, case_ids: list[str], config: dict) -> str:
        result = (
            self.client.table("evaluation_runs")
            .insert(
                {
                    "status": "pending",
                    "evaluator_model": model,
                    "configuration": config,
                    "total_cases": len(case_ids),
                }
            )
            .execute()
        )
        run_id = str(result.data[0]["run_id"])
        if case_ids:
            self.client.table("evaluation_run_cases").insert(
                [{"run_id": run_id, "case_id": case_id} for case_id in case_ids]
            ).execute()
        return run_id

    def get_run_case_ids(self, run_id: str) -> list[str]:
        result = (
            self.client.table("evaluation_run_cases")
            .select("case_id")
            .eq("run_id", run_id)
            .order("case_id")
            .execute()
        )
        return [str(row["case_id"]) for row in result.data or []]

    def get_run(self, run_id: str) -> dict:
        result = (
            self.client.table("evaluation_runs")
            .select("*")
            .eq("run_id", run_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise LookupError("evaluation run tidak ditemukan")
        return dict(result.data[0])

    def update_run(self, run_id: str, **fields: Any) -> None:
        self.client.table("evaluation_runs").update(fields).eq(
            "run_id", run_id
        ).execute()

    def claim_run(self, run_id: str) -> bool:
        """Atomically claim a pending or failed run for one worker."""
        result = (
            self.client.table("evaluation_runs")
            .update(
                {
                    "status": "running",
                    "processed_cases": 0,
                    "started_at": _now(),
                    "completed_at": None,
                    "error_message": None,
                }
            )
            .eq("run_id", run_id)
            .in_("status", ["pending", "failed"])
            .execute()
        )
        return bool(result.data)

    def update_run_case(self, run_id: str, case_id: str, **fields: Any) -> None:
        (
            self.client.table("evaluation_run_cases")
            .update(fields)
            .eq("run_id", run_id)
            .eq("case_id", case_id)
            .execute()
        )

    def clear_case_results(self, run_id: str, case_id: str) -> None:
        """Remove partial artifacts before safely retrying one case."""
        (
            self.client.table("evaluation_evidence")
            .delete()
            .eq("run_id", run_id)
            .eq("case_id", case_id)
            .execute()
        )
        # Recommendations are removed through the finding's ON DELETE CASCADE.
        (
            self.client.table("evaluation_findings")
            .delete()
            .eq("run_id", run_id)
            .eq("case_id", case_id)
            .execute()
        )

    def load_trace(self, request_id: str | None) -> dict:
        if not request_id:
            return {}
        result = (
            self.client.table("rag_execution_traces")
            .select("*")
            .eq("request_id", request_id)
            .limit(1)
            .execute()
        )
        return dict(result.data[0]) if result.data else {}

    def load_chunks(self, document: RegisteredDocument) -> list[dict]:
        rows = _all_rows(
            self.client.table("child_documents")
            .select("id,parent_id,title,content,section,pages,source,domain")
            .eq("source_document_version_id", document.version_id)
            .order("id")
        )
        if rows:
            return rows
        return _all_rows(
            self.client.table("child_documents")
            .select("id,parent_id,title,content,section,pages,source,domain")
            .eq("source", document.spec.chunk_source)
            .order("id")
        )

    def load_parents(self, chunks: list[dict]) -> list[dict]:
        """Read actual parent text; child separation alone is not a chunking defect."""
        ids = sorted({str(row["parent_id"]) for row in chunks if row.get("parent_id")})
        parents: list[dict] = []
        for start in range(0, len(ids), 100):
            result = (
                self.client.table("parent_documents")
                .select("parent_id,content,title")
                .in_("parent_id", ids[start : start + 100])
                .execute()
            )
            parents.extend(result.data or [])
        return parents

    def save_evidence(self, run_id: str, evidence: EvidenceCandidate) -> None:
        self.client.table("evaluation_evidence").insert(
            {
                "run_id": run_id,
                "case_id": evidence.case_id,
                "version_id": evidence.version_id,
                "page_start": evidence.page_start,
                "page_end": evidence.page_end,
                "evidence_text": evidence.evidence_text,
                "explanation": evidence.explanation,
                "confidence": evidence.confidence,
                "is_verified": evidence.is_verified,
            }
        ).execute()

    def save_finding(
        self,
        run_id: str,
        case_id: str,
        answer_available: bool,
        audit: ChunkAudit,
        review: DiagnosisReview,
        diagnostics: dict | None = None,
    ) -> str:
        result = (
            self.client.table("evaluation_findings")
            .upsert(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "answer_available": answer_available,
                    "failed_stage": review.failed_stage.value,
                    "root_cause": review.root_cause,
                    "confidence": review.confidence,
                    "affected_chunk_ids": audit.affected_chunk_ids,
                    "diagnostics": diagnostics
                    if diagnostics is not None
                    else audit.diagnostics,
                },
                on_conflict="run_id,case_id",
            )
            .execute()
        )
        finding_id = str(result.data[0]["finding_id"])
        if review.recommendations:
            self.client.table("evaluation_recommendations").insert(
                [
                    {
                        "finding_id": finding_id,
                        **recommendation.model_dump(mode="json"),
                    }
                    for recommendation in review.recommendations
                ]
            ).execute()
        return finding_id


@lru_cache(maxsize=1)
def get_evaluation_repository() -> EvaluationRepository:
    settings = get_settings()
    return EvaluationRepository(
        create_client(settings.supabase_url, settings.supabase_service_key)
    )
