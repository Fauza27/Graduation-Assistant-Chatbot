"""Concise human reports with full diagnostic data retained in JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from collections import Counter
from src.evaluation_agent.incident_context import describe_reranking_failure


def recommendation_summary(action: str) -> str:
    """Keep older detailed recommendations readable without changing stored data."""
    if "\n\nUsulan: " in action:
        return action.split("\n\nUsulan: ", 1)[1].split("\n\n", 1)[0].strip()
    return action.strip()


def write_report(run_id: str, results: list[dict[str, Any]], root: Path) -> Path:
    output_dir = root / "results" / "evaluations" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter(
        item.get("evidence_search", {}).get("status", "unknown") for item in results
    )
    summary = {
        "total_cases": len(results),
        "unique_question_texts": len(
            {" ".join(item["question"].lower().split()) for item in results}
        ),
        "evidence_status_counts": dict(counts),
        "note": "Jumlah bukti terverifikasi bukan ukuran akurasi agent; akurasi memerlukan penilaian manusia. Pertanyaan sama dapat berasal dari konteks/request berbeda.",
    }
    (output_dir / "report.json").write_text(
        json.dumps(
            {"run_id": run_id, "summary": summary, "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Hasil evaluasi RAG",
        "",
        f"Kasus: {len(results)}; teks pertanyaan unik: {summary['unique_question_texts']}.",
        "",
        summary["note"],
        "",
    ]
    for index, item in enumerate(results, start=1):
        diagnosis = item["diagnosis"]
        reason = diagnosis["root_cause"]
        if diagnosis["failed_stage"] == "reranking":
            reason = (
                describe_reranking_failure(item.get("incident_facts", {})) or reason
            )
        lines.extend(
            [
                f"## {index}. {item['question']}",
                "",
            ]
        )
        standalone = item.get("standalone_question")
        if (
            standalone
            and standalone.strip().lower() != item["question"].strip().lower()
        ):
            lines.extend([f"**Pertanyaan mandiri:** {standalone}", ""])
        evidence_status = item.get("evidence_search", {}).get("status")
        if evidence_status in {
            "inconclusive",
            "partial_evidence",
            "related_scope_only",
        }:
            lines.extend(
                [
                    "**Status bukti:** Pencarian belum meyakinkan; informasi belum "
                    "dapat dinyatakan tersedia atau tidak tersedia.",
                    "",
                ]
            )
        answer_assessment = item.get("answer_assessment") or {}
        if answer_assessment.get("verdict"):
            lines.extend([f"**Penilaian jawaban:** {answer_assessment['verdict']}", ""])
        evidence_items = item.get("supporting_evidence") or (
            [item["evidence"]] if item.get("evidence") else []
        )
        for evidence in evidence_items:
            lines.extend(
                [
                    f"**Bukti:** {evidence['document_title']}, halaman fisik {evidence['page_start']}–{evidence['page_end']}.",
                    "",
                    "> " + evidence["evidence_text"].replace("\n", "\n> "),
                    "",
                ]
            )
        lines.extend(
            [
                f"**Diagnosis:** {reason}",
                "",
                "**Rekomendasi perbaikan:**",
                "",
            ]
        )
        recommendations = diagnosis.get("recommendations", [])
        for recommendation in recommendations:
            lines.append(
                f"- `{recommendation['target']}`: {recommendation_summary(recommendation['action'])}"
            )
        if not recommendations:
            lines.append("Belum ada rekomendasi perbaikan yang didukung bukti.")
        lines.append("")
    path = output_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
