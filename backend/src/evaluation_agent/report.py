"""Write reviewable JSON and Markdown artifacts for one evaluation run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_report(run_id: str, results: list[dict[str, Any]], root: Path) -> Path:
    output_dir = root / "results" / "evaluations" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(
        json.dumps(
            {"run_id": run_id, "results": results}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )

    lines = [f"# RAG Evaluation Run `{run_id}`", ""]
    for index, item in enumerate(results, start=1):
        lines.extend(
            [
                f"## {index}. {item['question']}",
                "",
                f"- **Tahap gagal:** `{item['diagnosis']['failed_stage']}`",
                f"- **Jawaban tersedia:** {item['answer_available']}",
                f"- **Confidence:** {item['diagnosis']['confidence']:.2f}",
                f"- **Penyebab:** {item['diagnosis']['root_cause']}",
                "",
            ]
        )
        evidence = item.get("evidence")
        if evidence:
            lines.extend(
                [
                    f"**Bukti:** {evidence['document_title']}, halaman fisik "
                    f"{evidence['page_start']}–{evidence['page_end']}",
                    "",
                    f"> {evidence['evidence_text']}",
                    "",
                ]
            )
        recommendations = item["diagnosis"].get("recommendations", [])
        if recommendations:
            lines.append("**Rekomendasi:**")
            lines.append("")
            for recommendation in recommendations:
                lines.append(
                    f"- `{recommendation['target']}`: {recommendation['action']} "
                    f"(risiko {recommendation['risk']})"
                )
            lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return markdown_path
