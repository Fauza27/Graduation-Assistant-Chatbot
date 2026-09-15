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
                    "\n".join(
                        f"> {line}" for line in evidence["evidence_text"].splitlines()
                    ),
                    "",
                ]
            )
        recommendations = item["diagnosis"].get("recommendations", [])
        gates = item.get("incident_facts", {}).get("selection_counterfactuals", [])
        if gates:
            lines.extend(
                [
                    "**Jejak parent dengan bukti terkuat (skor cross-encoder):**",
                    "",
                    "| Parent | Rank | Skor | Batas skor saat request | Alasan seleksi | Dipotong |",
                    "|---|---|---|---|---|---|",
                ]
            )
            for gate in gates:
                lines.append(
                    f"| `{gate['parent_id']}` | {gate['rerank_rank']} | "
                    f"{gate['rerank_score']} | {gate['acceptance_threshold_at_request']} | "
                    f"{gate['selection_reason']} | {gate['truncated']} |"
                )
            lines.extend(
                [
                    "",
                    "Minimum top score menguji kandidat berskor tertinggi. "
                    "Penerimaan parent juga harus memenuhi relative gap dan top-N. "
                    "Batas gap/top-N hipotetis dalam report.json bukan rekomendasi "
                    "untuk langsung menaikkan parameter.",
                    "",
                ]
            )
        system_context = item.get("system_context")
        if system_context:
            historical = system_context["request_configuration"]
            current = system_context["current_configuration"]
            lines.extend(
                [
                    "**Konfigurasi request dan konfigurasi saat evaluasi:**",
                    "",
                    "| Parameter | Saat request | Saat evaluasi |",
                    "|---|---|---|",
                ]
            )
            for name, value in current.items():
                if name != "implementation_checksums":
                    lines.append(
                        f"| `{name}` | {historical.get(name, 'Tidak tercatat')} | {value} |"
                    )
            lines.extend(
                [
                    "",
                    "Potongan kode saat ini dan checksum tersimpan dalam report.json. "
                    "Untuk request lama tanpa checksum, kesamaan versi kode belum diketahui.",
                    "",
                ]
            )
        if recommendations:
            lines.append("**Rekomendasi:**")
            lines.append("")
            for recommendation in recommendations:
                lines.extend(
                    [
                        f"### {recommendation['target']}",
                        "",
                        f"**Risiko:** {recommendation['risk']}",
                        "",
                        "**Usulan perubahan:**",
                        "",
                        recommendation["action"],
                        "",
                        "**Dasar rekomendasi:**",
                        "",
                        recommendation["rationale"],
                        "",
                        "**Validasi:**",
                        "",
                        recommendation["validation_plan"],
                        "",
                    ]
                )
            lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return markdown_path
