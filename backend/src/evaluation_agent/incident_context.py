"""Focus diagnostic review on observed transitions and score provenance."""

from __future__ import annotations

from src.evaluation_agent.models import (
    ChunkAudit,
    Diagnosis,
    EvaluationCase,
    Recommendation,
)


def build_incident_context(
    trace: dict, audit: ChunkAudit, diagnosis: Diagnosis
) -> dict:
    """Provide facts, not an oracle-based algorithm for future requests."""
    best_coverage = max((match.coverage for match in audit.matches), default=0)
    strongest = {
        match.parent_id for match in audit.matches if match.coverage == best_coverage
    }
    scored = trace.get("reranked_candidates", [])
    relevant = [row for row in scored if row.get("parent_id") in strongest]
    checks = diagnosis.diagnostics.get("rerank_gate_checks", [])
    return {
        "earliest_failed_stage": diagnosis.failed_stage.value,
        "observed_failure": diagnosis.root_cause,
        "strongest_evidence_parent_ids": sorted(strongest),
        "strongest_evidence_coverage": best_coverage,
        "strongest_evidence_rerank_results": relevant,
        "accepted_rerank_results": [row for row in scored if row.get("accepted")],
        "selection_counterfactuals": [
            check for check in checks if check["parent_id"] in strongest
        ],
        "missing_score_parent_ids": diagnosis.diagnostics.get(
            "parents_without_recorded_rerank_score", []
        ),
        "interpretation_rules": [
            "Evidence matches come from an offline audit; production cannot identify the correct parent using these IDs.",
            "A low rank/score despite full evidence suggests a scoring/input mismatch; a gate change alone does not repair ordering.",
            "Required gap and top-N are counterfactual bounds with unchanged scores, not recommended production values.",
            "A parent marked truncated=false cannot have lost its evidence to the recorded character limit; model tokenizer truncation is a separate unmeasured possibility.",
            "Full score coverage means no need to add score logging or increase rerank candidate count to score these same parents.",
            "RRF/search scores cannot be compared with cross-encoder thresholds.",
            "rerank_min_top_score applies to the highest candidate score, not to the score of every individual parent.",
            "Acceptance requires highest score >= minimum top score, parent score >= highest score - relative gap, and position within top-N among gap survivors; parent score > 0 alone is insufficient.",
        ],
    }


def describe_reranking_failure(facts: dict) -> str | None:
    """Explain a recorded rejection without guessing why the model scored it low."""
    rows = {
        row["parent_id"]: row
        for row in facts.get("strongest_evidence_rerank_results", [])
    }
    for gate in facts.get("selection_counterfactuals", []):
        row = rows.get(gate["parent_id"], {})
        if row.get("accepted") or gate.get("top_score_passes_minimum_gate") is False:
            continue
        title = row.get("title") or gate["parent_id"]
        rank = gate.get("rerank_rank")
        score = gate.get("rerank_score")
        threshold = gate.get("acceptance_threshold_at_request")
        if not isinstance(score, (int, float)) or not isinstance(
            threshold, (int, float)
        ):
            continue
        if score < threshold:
            return (
                f"Bagian '{title}' ditemukan saat retrieval, tetapi berada pada peringkat {rank} "
                f"setelah reranking. Skornya ({score:.2f}) di bawah batas penerimaan "
                f"({threshold:.2f}), sehingga bukti tidak masuk ke konteks jawaban."
            )
        if gate.get("selection_reason") == "outside_top_n":
            return (
                f"Bagian '{title}' ditemukan, tetapi berada pada peringkat {rank} setelah "
                f"reranking, melewati batas {gate.get('request_top_n')} dokumen. "
                "Bukti akhirnya tidak masuk ke konteks jawaban."
            )
    return None


def reranking_success_criteria(
    case: EvaluationCase, context: dict, facts: dict
) -> list[str]:
    """Render the actual selection contract rather than LLM-invented thresholds."""
    config = context["current_configuration"]
    parents = (
        ", ".join(facts["strongest_evidence_parent_ids"])
        or "parent bukti terverifikasi"
    )
    criteria = [
        "Catat baseline dan konfigurasi eksperimen. Baseline saat evaluasi: "
        f"rerank_min_top_score={config['rerank_min_top_score']}, "
        f"rerank_relative_gap={config['rerank_relative_gap']}, rerank_top_n={config['rerank_top_n']}. "
        "Jika eksperimen mengubah parameter, laporkan nilai barunya secara eksplisit.",
        f"Dengan kandidat identik, parent bukti ({parents}) harus diterima: skor tertinggi "
        ">= rerank_min_top_score, skor parent >= skor tertinggi - rerank_relative_gap, "
        "dan rank di antara kandidat yang lolos gap <= rerank_top_n, menggunakan nilai "
        "konfigurasi eksperimen. Skor parent > 0 atau naik saja tidak cukup.",
        "Replay end-to-end: parent bukti harus tercatat dalam final_context.document_ids "
        "dan jawaban menjawab seluruh fakta bukti terverifikasi, bukan hanya topik yang mirip.",
        "Replay seluruh kasus pembanding yang sebelumnya benar dan kasus tanpa jawaban: "
        "tidak boleh ada jawaban benar yang menjadi salah atau jawaban tanpa dukungan dokumen. "
        "Bandingkan rank/acceptance bukti, akurasi jawaban, dan latency baseline versus eksperimen.",
    ]
    if case.expected_answer:
        criteria.append(
            f"Jawaban kasus ini harus memenuhi expected_answer: {case.expected_answer}"
        )
    return criteria


def build_reranking_recommendations(
    case: EvaluationCase,
    trace: dict,
    context: dict,
    facts: dict,
) -> list[Recommendation]:
    """Create bounded reranker experiments without inventing threshold changes."""

    query_plan = trace.get("query_plan", {})
    resolved_query = str(query_plan.get("resolved_query") or "").strip()
    rerank_query = str(query_plan.get("rerank_query") or "").strip()
    criteria = "\n".join(reranking_success_criteria(case, context, facts))
    rows = facts.get("strongest_evidence_rerank_results", [])
    strongest = rows[0] if rows else {}
    score = strongest.get("rerank_score")
    rank = strongest.get("rank")
    observed = (
        f"Bukti terverifikasi tercatat pada rank {rank} dengan skor {score}."
        if rank is not None and score is not None
        else "Bukti terverifikasi tidak memperoleh posisi penerimaan yang memadai."
    )

    recommendations: list[Recommendation] = []
    if resolved_query and rerank_query and resolved_query != rerank_query:
        recommendations.append(
            Recommendation(
                target="src/retrieval/query_planner.py::build_query_plan",
                action=(
                    "Uji penggunaan resolved_query sebagai query reranker setelah "
                    "reformulasi, sehingga referensi percakapan yang sudah diselesaikan "
                    "tidak kembali menjadi pertanyaan pendek yang ambigu."
                ),
                rationale=(
                    f"Request mencari dengan '{resolved_query}', tetapi reranker "
                    f"menilai kandidat memakai '{rerank_query}'."
                ),
                risk="medium",
                validation_plan=criteria,
            )
        )
    elif case.conversation_context:
        recommendations.append(
            Recommendation(
                target="src/generation/intent_classifier/reformulator.py",
                action=(
                    "Perluas deteksi follow-up pendek agar topik dari turn terakhir "
                    "masuk ke resolved_query sebelum pencarian dan reranking."
                ),
                rationale=(
                    "Kasus memiliki konteks percakapan, tetapi query reranker belum "
                    "membawa topik tersebut secara mandiri."
                ),
                risk="medium",
                validation_plan=criteria,
            )
        )

    recommendations.append(
        Recommendation(
            target="src/retrieval/reranker.py dan CROSS_ENCODER_MODEL",
            action=(
                "Bandingkan representasi input saat ini dan model cross-encoder "
                "multilingual menggunakan pasangan pertanyaan-bukti terverifikasi. "
                "Pilih perubahan hanya jika rank bukti membaik tanpa menurunkan kasus "
                "kontrol; jangan mengubah relative gap sebagai pengganti scoring."
            ),
            rationale=observed,
            risk="medium",
            validation_plan=criteria,
        )
    )
    return recommendations[:2]
