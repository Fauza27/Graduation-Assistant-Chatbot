"""Concise human reports with full diagnostic data retained in JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from src.evaluation_agent.incident_context import describe_reranking_failure


def recommendation_summary(action: str) -> str:
    """Keep older detailed recommendations readable without changing stored data."""
    if "\n\nUsulan: " in action:
        return action.split("\n\nUsulan: ", 1)[1].split("\n\n", 1)[0].strip()
    return action.strip()


def write_report(run_id: str, results: list[dict[str, Any]], root: Path) -> Path:
    output_dir = root / "results" / "evaluations" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(
            {"run_id": run_id, "results": results}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    lines = ["# Hasil evaluasi RAG", ""]
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
                f"**Alasan gagal:** {reason}",
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
