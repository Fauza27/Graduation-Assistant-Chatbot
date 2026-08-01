"""
RAGAS Evaluation WITHOUT Ground Truth
--------------------------------------
Versi yang sudah dimodifikasi berdasarkan prinsip:

1. Faithfulness sebagai HARD GUARDRAIL (bukan sekadar metrik biasa)
2. Custom metrics untuk mengukur kualitas yang RAGAS tidak bisa ukur
3. Deteksi otomatis "false negative" faithfulness yang perlu dicek manual
4. Threshold berbeda per metrik sesuai risiko dan prioritas bisnis
5. Kategorisasi hasil yang lebih actionable (bukan sekedar pass/fail)
"""

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
)
from ragas.metrics._context_precision import LLMContextPrecisionWithoutReference
from ragas.metrics import SimpleCriteriaScore, RubricsScore
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from loguru import logger
import json
import math
from datetime import datetime
from statistics import mean
from typing import List, Dict, Optional
from enum import Enum

from config.settings import get_settings


# ============================================================
# CONSTANTS & ENUMS
# ============================================================

class MetricRole(Enum):
    """
    Peran setiap metrik dalam sistem evaluasi.
    Ini yang menentukan bagaimana kita bereaksi saat score rendah.
    """
    HARD_GUARDRAIL = "hard_guardrail"   # Rendah = bahaya nyata, harus diperbaiki
    QUALITY_SIGNAL = "quality_signal"   # Rendah = perlu investigasi, bukan langsung panik
    BUSINESS_KPI   = "business_kpi"     # Diukur berdasarkan standar bisnis kita sendiri


METRIC_CONFIG = {
    "faithfulness": {
        "threshold": 0.70,
        "role": MetricRole.HARD_GUARDRAIL,
        "reason": "Halusinasi berbahaya untuk konteks akademik. Namun threshold dikalibrasi ke 0.70 "
                  "karena jawaban chatbot bersifat elaboratif (prefix sumber & penutup tujuan) yang "
                  "sering dihukum RAGAS sebagai false negative meskipun secara faktual akurat.",
        "false_negative_suspect_threshold": 0.80,
    },
    "answer_relevancy": {
        "threshold": 0.70,  
        "role": MetricRole.QUALITY_SIGNAL,
        "reason": "Jawaban yang elaboratif dan lengkap cenderung dihukum metrik ini. "
                  "Threshold diturunkan agar tidak menghukum jawaban yang genuinely helpful.",
    },
    "llm_context_precision_without_reference": {
        "threshold": 0.80,
        "role": MetricRole.HARD_GUARDRAIL,
        "reason": "Retriever yang mengambil chunk tidak relevan akan meracuni generator. "
                  "Ini masalah infrastruktur, bukan masalah prompt.",
    },
    # Custom metrics 
    "answer_completeness": {
        "threshold": 3.5,
        "role": MetricRole.BUSINESS_KPI,
        "reason": "Metrik ini mengukur apakah jawaban cukup lengkap sehingga mahasiswa "
                  "tidak perlu bertanya ulang. Ini yang paling relevan dengan kepuasan user.",
    },
    "answer_actionability": {
        "threshold": 3.5,
        "role": MetricRole.BUSINESS_KPI,
        "reason": "Jawaban harus memberikan informasi konkret yang bisa langsung dipakai, "
                  "bukan hanya penjelasan abstrak.",
    },
}


# ============================================================
# EVALUATION QUESTIONS
# ============================================================

EVAL_QUESTIONS_PI = [
    "Apa syarat SKS minimal untuk mengambil Penulisan Ilmiah (PI)?",
    "Berapa IP Kumulatif minimal untuk mengambil PI?",
    "Apakah PI wajib dilakukan di sebuah instansi atau perusahaan?",
    "Berapa lama minimal kegiatan penelitian PI jika dilakukan di perusahaan atau instansi?",
    "Siapa yang menjadi dosen pembimbing PI?",
    "Berapa jumlah dosen pembimbing dan dosen penguji untuk PI?",
    "Apa yang dimaksud dengan Tempat Penelitian PI?",
    "Apa syarat jabatan fungsional minimal untuk menjadi dosen pembimbing atau penguji PI?",
    "Dalam kondisi apa mahasiswa dapat mengajukan penggantian dosen pembimbing PI?",
    "Apa hak mahasiswa dalam proses bimbingan PI?",
    "Berapa lama maksimal masa bimbingan PI?",
    "Berapa kali minimal mahasiswa harus bertemu dengan dosen pembimbing selama PI?",
    "Di mana bimbingan PI dapat dilaksanakan?",
    "Apa yang harus dibawa mahasiswa setiap kali melakukan bimbingan PI?",
    "Berapa kali minimal mahasiswa harus melapor ke dosen pembimbing selama pelaksanaan penelitian PI?",
    "Berapa kali minimal mahasiswa harus menghadiri seminar PI orang lain sebelum melaksanakan seminar sendiri?",
    "Apa saja berkas yang harus dilampirkan saat mendaftar ujian PI?",
    "Berapa maksimal tingkat kemiripan (plagiarisme) yang diperbolehkan untuk laporan PI?",
    "Berapa lama waktu maksimal pelaksanaan seminar PI setelah persetujuan dosen pembimbing?",
    "Berapa minimal halaman laporan PI?",
    "Apa ketentuan pakaian saat ujian PI untuk mahasiswa pria?",
    "Apa ketentuan pakaian saat ujian PI untuk mahasiswi berjilbab?",
    "Berapa lama durasi ujian PI?",
    "Apa komponen penilaian dalam ujian PI?",
    "Berapa nilai minimal untuk dinyatakan lulus ujian PI?",
    "Apa yang harus dilakukan mahasiswa setelah ujian PI?",
    "Berapa jumlah minimal referensi yang harus ada dalam laporan PI?",
    "Apa format daftar pustaka yang digunakan dalam PI?",
    "Berapa spasi yang digunakan untuk penulisan naskah utama PI?",
    "Apa jenis dan ukuran font yang digunakan untuk naskah PI?",
    "Berapa margin yang digunakan untuk penulisan laporan PI?",
    "Apa ukuran kertas yang digunakan untuk laporan PI?",
    "Bagaimana aturan penulisan judul bab dalam PI?",
    "Bagaimana aturan penulisan judul tabel dalam PI?",
    "Bagaimana aturan penulisan judul gambar dalam PI?",
    "Berapa maksimal kata dalam abstrak PI?",
    "Berapa jumlah kata kunci yang harus ada dalam abstrak PI?",
    "Apa saja elemen yang harus ada di halaman sampul depan PI?",
    "Apa yang dimuat dalam halaman pengesahan PI?",
    "Apa saja bagian yang termasuk dalam Bagian Awal laporan PI?",
    "Apa saja bab yang termasuk dalam Bagian Utama laporan PI?",
    "Apa isi dari BAB I Pendahuluan dalam laporan PI?",
    "Apa isi dari BAB II Tinjauan Pustaka dalam laporan PI?",
    "Apa isi dari BAB III Metode Penelitian dalam laporan PI?",
    "Apa isi dari BAB IV Hasil Penelitian dan Pembahasan dalam laporan PI?",
    "Apa isi dari BAB V Penutup dalam laporan PI?",
    "Apa yang dimaksud dengan Kajian Empiris dalam Tinjauan Pustaka PI?",
    "Apa yang dimaksud dengan Landasan Teori dalam Tinjauan Pustaka PI?",
    "Bagaimana cara menulis referensi buku dalam daftar pustaka PI?",
    "Bagaimana cara menulis referensi jurnal dalam daftar pustaka PI?",
    "Bagaimana cara menulis referensi website dalam daftar pustaka PI?",
    "Bagaimana cara menulis referensi yang tidak dipublikasikan dalam daftar pustaka PI?",
    "Apa yang harus dilakukan jika referensi tidak memiliki nama penulis?",
    "Bagaimana urutan penyusunan daftar pustaka dalam PI?",
]

EVAL_QUESTIONS_KKP = [
    "Apa syarat SKS minimal untuk mengambil Kuliah Kerja Praktik (KKP)?",
    "Berapa IP Kumulatif minimal untuk mengambil KKP?",
    "Berapa jumlah dosen pembimbing dan dosen penguji untuk KKP?",
    "Berapa lama minimal pelaksanaan KKP di instansi?",
    "Apa yang dimaksud dengan Tempat KKP?",
    "Apa kriteria instansi yang dapat menjadi tempat KKP?",
    "Siapa yang menjadi dosen pembimbing KKP?",
    "Apa bidang yang menjadi sasaran pengalaman belajar dalam KKP?",
    "Apa syarat jabatan fungsional minimal untuk menjadi dosen pembimbing atau penguji KKP?",
    "Dalam kondisi apa mahasiswa dapat mengajukan penggantian dosen pembimbing KKP?",
    "Apa hak mahasiswa dalam proses bimbingan KKP?",
    "Berapa lama maksimal masa bimbingan KKP?",
    "Berapa kali minimal mahasiswa harus bertemu dengan dosen pembimbing selama KKP?",
    "Bagaimana mahasiswa diutamakan mencari tempat KKP?",
    "Apa yang harus dilakukan mahasiswa setelah mendapat surat balasan dari instansi tempat KKP?",
    "Berapa kali minimal mahasiswa harus melapor ke dosen pembimbing selama pelaksanaan KKP?",
    "Apa yang harus dibawa mahasiswa setiap kali melakukan bimbingan KKP?",
    "Apa saja berkas yang harus dilampirkan saat mendaftar ujian KKP?",
    "Berapa maksimal tingkat kemiripan (plagiarisme) yang diperbolehkan untuk laporan KKP?",
    "Berapa lama waktu maksimal pelaksanaan seminar KKP setelah persetujuan dosen pembimbing?",
    "Berapa minimal halaman laporan KKP?",
    "Apa ketentuan pakaian saat ujian KKP untuk mahasiswa pria?",
    "Apa ketentuan pakaian saat ujian KKP untuk mahasiswi berjilbab?",
    "Berapa lama durasi ujian KKP?",
    "Apa komponen penilaian dalam ujian KKP?",
    "Berapa nilai minimal untuk dinyatakan lulus ujian KKP?",
    "Apa yang harus dilakukan mahasiswa setelah ujian KKP?",
    "Berapa jumlah minimal referensi yang harus ada dalam laporan KKP?",
    "Apa format daftar pustaka yang digunakan dalam KKP?",
    "Berapa spasi yang digunakan untuk penulisan naskah utama KKP?",
    "Apa jenis dan ukuran font yang digunakan untuk naskah KKP?",
    "Berapa margin yang digunakan untuk penulisan laporan KKP?",
    "Apa ukuran kertas yang digunakan untuk laporan KKP?",
    "Berapa maksimal kata dalam abstrak KKP?",
    "Berapa jumlah kata kunci yang harus ada dalam abstrak KKP?",
    "Apa saja elemen yang harus ada di halaman sampul depan KKP?",
    "Apa yang dimuat dalam halaman pengesahan laporan KKP?",
    "Apa saja bagian yang termasuk dalam Bagian Awal laporan KKP?",
    "Apa saja bab yang termasuk dalam Bagian Utama laporan KKP?",
    "Bagaimana urutan penyusunan daftar pustaka dalam KKP?",
]


# ============================================================
# CUSTOM METRICS FACTORY
# ============================================================

def build_custom_metrics(evaluator_llm: LangchainLLMWrapper) -> Dict:
    """
    Membangun custom metrics yang mengukur dimensi kualitas yang
    tidak bisa diukur oleh RAGAS default.
    """

    # --- Metric 1: Completeness ---
    # Masalah yang kamu alami: jawaban singkat dapat skor tinggi di RAGAS
    # tapi tidak memuaskan user. Metric ini mengukur hal tersebut.
    answer_completeness = SimpleCriteriaScore(
        name="answer_completeness",
        definition=(
            "Nilai apakah jawaban memberikan informasi yang CUKUP LENGKAP "
            "sehingga mahasiswa tidak perlu bertanya lagi untuk memahami topik tersebut. "
            "Jawaban yang hanya menyebutkan angka/fakta tanpa konteks dianggap tidak lengkap. "
            "Jawaban ideal mencakup: fakta utama, kondisi/syarat jika ada, dan konteks yang membantu pemahaman. "
            "Gunakan bahasa Indonesia dalam penilaian."
        ),
        llm=evaluator_llm,
    )

    # --- Metric 2: Actionability ---
    # Mengukur apakah jawaban bisa langsung dipakai mahasiswa,
    # bukan sekadar informasi abstrak.
    answer_actionability = SimpleCriteriaScore(
        name="answer_actionability",
        definition=(
            "Nilai apakah jawaban memberikan informasi konkret yang dapat langsung "
            "digunakan mahasiswa untuk mengambil tindakan atau keputusan. "
            "Jawaban yang baik: menyebutkan angka spesifik jika ada, "
            "menyebutkan prosedur/langkah jika relevan, menghindari penjelasan terlalu abstrak. "
            "Jawaban yang hanya bilang 'sesuai ketentuan yang berlaku' tanpa detail "
            "dianggap tidak actionable. "
            "Gunakan bahasa Indonesia dalam penilaian."
        ),
        llm=evaluator_llm,
    )

    return {
        "answer_completeness": answer_completeness,
        "answer_actionability": answer_actionability,
    }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe_score(value) -> Optional[float]:
    """Konversi nilai metrik RAGAS ke float, return None jika tidak valid."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        values = [v for v in value if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return mean(values) if values else None
    if value is None:
        return None
    val = float(value)
    return None if math.isnan(val) else val


def _get_score_at_index(metric_result, index: int) -> Optional[float]:
    """Ambil score per item di index tertentu."""
    if hasattr(metric_result, "tolist"):
        metric_result = metric_result.tolist()
    if isinstance(metric_result, (list, tuple)):
        val = metric_result[index] if index < len(metric_result) else None
    else:
        val = metric_result
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return float(val)


def _is_faithfulness_false_negative_suspect(
    faithfulness_score: Optional[float],
    context: List[str],
    answer: str,
) -> bool:
    """
    Deteksi apakah faithfulness rendah kemungkinan adalah FALSE NEGATIVE,
    bukan halusinasi nyata.

    False negative terjadi ketika:
    - Jawaban parafrase info dari konteks (valid tapi tidak verbatim)
    - Jawaban sintesis dari beberapa chunk (inferensi valid)
    - LLM judge gagal karena bahasa Indonesia

    Heuristik sederhana: jika score sangat rendah (< threshold suspect)
    tapi konteks tidak kosong dan jawaban cukup panjang,
    tandai untuk review manual.
    """
    if faithfulness_score is None:
        return False

    suspect_threshold = METRIC_CONFIG["faithfulness"]["false_negative_suspect_threshold"]
    has_context = len(context) > 0 and any(len(c.strip()) > 50 for c in context)
    answer_has_substance = len(answer.split()) > 15

    return (
        faithfulness_score < suspect_threshold
        and has_context
        and answer_has_substance
    )


def _categorize_item_result(item_metrics: Dict) -> str:
    """
    Kategorisasi hasil per item menjadi actionable label.

    Ini lebih berguna dari sekadar pass/fail karena kamu tahu
    MENGAPA item tersebut bermasalah dan APA yang harus dilakukan.
    """
    faith = item_metrics.get("faithfulness")
    relevancy = item_metrics.get("answer_relevancy")
    precision = item_metrics.get("llm_context_precision_without_reference")
    completeness = item_metrics.get("answer_completeness")

    faith_threshold = METRIC_CONFIG["faithfulness"]["threshold"]
    precision_threshold = METRIC_CONFIG["llm_context_precision_without_reference"]["threshold"]

    # Prioritas 1: masalah di retriever (upstream problem)
    if precision is not None and precision < precision_threshold:
        return "RETRIEVER_ISSUE"  # Perbaiki chunking/embedding/similarity threshold

    # Prioritas 2: halusinasi (berbahaya untuk konteks akademik)
    if faith is not None and faith < faith_threshold:
        return "POSSIBLE_HALLUCINATION"  # Cek manual dulu, baru perbaiki prompt

    # Prioritas 3: jawaban kurang lengkap (user experience issue)
    if completeness is not None and completeness < METRIC_CONFIG["answer_completeness"]["threshold"]:
        return "INCOMPLETE_ANSWER"  # Perbaiki prompt untuk dorong jawaban lebih lengkap

    # Prioritas 4: jawaban OOT (relevancy issue, tapi toleransi lebih tinggi)
    if relevancy is not None and relevancy < METRIC_CONFIG["answer_relevancy"]["threshold"]:
        return "LOW_RELEVANCY"  # Investigasi dulu sebelum action

    return "PASS"


# ============================================================
# CORE EVALUATION FUNCTION
# ============================================================

def evaluate_rag_no_ground_truth(
    questions: List[str],
    answers: List[str],
    contexts: List[List[str]],
    dataset_name: str = "both",
) -> Dict:

    logger.info(f"Starting evaluation for dataset: {dataset_name} ({len(questions)} questions)")

    settings = get_settings()

    # --- Setup LLM & Embeddings ---
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.open_api_key,
            temperature=0,  # Deterministic untuk konsistensi antar run
        )
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
        )
    )

    # --- Build Metrics ---
    # Pisahkan RAGAS metrics dan custom metrics karena cara evaluasinya berbeda.
    # RAGAS metrics berjalan dalam satu batch evaluate() call.
    # Custom metrics (SimpleCriteriaScore) juga bisa dimasukkan ke evaluate()
    # tapi dipisahkan di sini agar config-nya lebih jelas.

    context_precision_no_ref = LLMContextPrecisionWithoutReference(llm=evaluator_llm)
    custom_metrics = build_custom_metrics(evaluator_llm)

    ragas_metrics = [
        faithfulness,
        answer_relevancy,
        context_precision_no_ref,
        custom_metrics["answer_completeness"],
        custom_metrics["answer_actionability"],
    ]

    # --- Prepare Dataset ---
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
    })

    # --- Run Evaluation ---
    logger.info("Running evaluation (this may take a while)...")
    raw_results = evaluate(
        dataset,
        metrics=ragas_metrics,
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
    )

    # --- Aggregate Scores ---
    aggregate_scores = {
        "faithfulness": _safe_score(raw_results["faithfulness"]),
        "answer_relevancy": _safe_score(raw_results["answer_relevancy"]),
        "llm_context_precision_without_reference": _safe_score(
            raw_results["llm_context_precision_without_reference"]
        ),
        "answer_completeness": _safe_score(raw_results["answer_completeness"]),
        "answer_actionability": _safe_score(raw_results["answer_actionability"]),
    }

    # --- Quality Gate Logic ---
    # Hard guardrails HARUS pass. Business KPI dan quality signal punya toleransi berbeda.
    # Ini menggantikan "all metrics must pass" yang terlalu naif.

    guardrail_failures = []
    quality_warnings = []
    business_kpi_failures = []

    for metric_name, score in aggregate_scores.items():
        if metric_name not in METRIC_CONFIG or score is None:
            continue
        config = METRIC_CONFIG[metric_name]
        threshold = config["threshold"]

        if score < threshold:
            if config["role"] == MetricRole.HARD_GUARDRAIL:
                guardrail_failures.append(metric_name)
            elif config["role"] == MetricRole.QUALITY_SIGNAL:
                quality_warnings.append(metric_name)
            elif config["role"] == MetricRole.BUSINESS_KPI:
                business_kpi_failures.append(metric_name)

    # Overall: PASS hanya jika tidak ada guardrail failure
    # (business KPI dan quality signal tidak memblokir, tapi dicatat)
    overall_pass = len(guardrail_failures) == 0

    # --- Per-Item Details ---
    details = []
    category_summary = {
        "PASS": 0,
        "RETRIEVER_ISSUE": 0,
        "POSSIBLE_HALLUCINATION": 0,
        "INCOMPLETE_ANSWER": 0,
        "LOW_RELEVANCY": 0,
    }

    for i in range(len(questions)):
        item_metrics = {
            "faithfulness": _get_score_at_index(raw_results["faithfulness"], i),
            "answer_relevancy": _get_score_at_index(raw_results["answer_relevancy"], i),
            "llm_context_precision_without_reference": _get_score_at_index(
                raw_results["llm_context_precision_without_reference"], i
            ),
            "answer_completeness": _get_score_at_index(raw_results["answer_completeness"], i),
            "answer_actionability": _get_score_at_index(raw_results["answer_actionability"], i),
        }

        category = _categorize_item_result(item_metrics)
        category_summary[category] = category_summary.get(category, 0) + 1

        # Flag kemungkinan false negative faithfulness untuk review manual
        needs_manual_review = (
            category == "POSSIBLE_HALLUCINATION"
            and _is_faithfulness_false_negative_suspect(
                item_metrics["faithfulness"],
                contexts[i],
                answers[i],
            )
        )

        details.append({
            "index": i + 1,
            "question": questions[i],
            "answer": answers[i],
            "contexts": contexts[i],
            "metrics": item_metrics,
            "category": category,
            # Jika True: jangan langsung fix prompt, cek dulu apakah
            # ini benar halusinasi atau false negative RAGAS
            "needs_manual_review": needs_manual_review,
            "manual_review_reason": (
                "Faithfulness rendah tapi konteks tersedia dan jawaban substansial. "
                "Kemungkinan RAGAS salah menilai parafrase/sintesis sebagai halusinasi. "
                "Cek manual: apakah jawaban benar-benar tidak didukung konteks?"
            ) if needs_manual_review else None,
        })

    # --- Final Result ---
    result = {
        "timestamp": datetime.now().isoformat(),
        "dataset_type": dataset_name,
        "num_questions": len(questions),

        # Scores agregat
        "scores": aggregate_scores,

        # Threshold yang digunakan (untuk audit/reproducibility)
        "thresholds": {k: v["threshold"] for k, v in METRIC_CONFIG.items() if k in aggregate_scores},

        # Quality gate: hanya guardrail yang memblokir
        "overall_pass": overall_pass,
        "guardrail_failures": guardrail_failures,       # Harus diperbaiki
        "quality_warnings": quality_warnings,           # Investigasi dulu
        "business_kpi_failures": business_kpi_failures, # Evaluasi apakah acceptable

        # Ringkasan kategori untuk triaging
        "category_summary": category_summary,
        "items_needing_manual_review": sum(
            1 for d in details if d["needs_manual_review"]
        ),

        # Detail per item
        "details": details,
    }

    _log_results(result)
    return result


# ============================================================
# LOGGING
# ============================================================

def _log_results(result: Dict):
    logger.info("\n" + "=" * 80)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 80)
    logger.info(f"Dataset  : {result['dataset_type']}")
    logger.info(f"Questions: {result['num_questions']}")

    logger.info("\n📊 Scores:")
    for metric, score in result["scores"].items():
        if score is None:
            logger.warning(f"  ⚠️  {metric}: N/A")
            continue
        threshold = result["thresholds"].get(metric, 0)
        config = METRIC_CONFIG.get(metric, {})
        role_label = config.get("role", MetricRole.QUALITY_SIGNAL).value
        status = "✅" if score >= threshold else "❌"
        logger.info(f"  {status} {metric}: {score:.4f} (threshold: {threshold}) [{role_label}]")

    logger.info("\n🚦 Quality Gate:")
    if result["guardrail_failures"]:
        logger.error(f"  ❌ FAILED — Guardrail failures: {result['guardrail_failures']}")
        for m in result["guardrail_failures"]:
            logger.error(f"     → {METRIC_CONFIG[m]['reason']}")
    else:
        logger.info("  ✅ PASSED — All hard guardrails met")

    if result["quality_warnings"]:
        logger.warning(f"  ⚠️  Quality warnings (investigate before action): {result['quality_warnings']}")

    if result["business_kpi_failures"]:
        logger.warning(f"  📉 Business KPI below target: {result['business_kpi_failures']}")

    logger.info("\n📁 Category Summary:")
    for category, count in result["category_summary"].items():
        logger.info(f"  {category}: {count} items")

    manual_review_count = result["items_needing_manual_review"]
    if manual_review_count > 0:
        logger.warning(
            f"\n🔍 {manual_review_count} item(s) flagged for MANUAL REVIEW "
            f"(faithfulness mungkin false negative — jangan langsung fix tanpa cek dulu)"
        )

    logger.info("=" * 80)


# ============================================================
# FILE I/O
# ============================================================

def save_evaluation_results(results: Dict, filename: str = None) -> str:
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"evaluation_results_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"Results saved to: {filename}")
    return filename


def export_manual_review_items(results: Dict, filename: str = None) -> Optional[str]:
    """
    Export item-item yang perlu dicek manual ke file terpisah.
    Berguna agar kamu tahu persis mana yang perlu dilihat,
    bukan scroll ratusan baris JSON.
    """
    items = [d for d in results["details"] if d["needs_manual_review"]]
    if not items:
        logger.info("Tidak ada item yang perlu manual review.")
        return None

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_review_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "total_flagged": len(items),
            "instruction": (
                "Untuk setiap item berikut: cek apakah jawaban BENAR-BENAR tidak didukung konteks "
                "(halusinasi nyata) atau RAGAS yang salah menilai (false negative). "
                "Jika false negative: jangan ubah sistem, catat sebagai limitasi RAGAS. "
                "Jika halusinasi nyata: perbaiki prompt/retriever."
            ),
            "items": items,
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"Manual review items saved to: {filename}")
    return filename


# ============================================================
# MAIN RUNNER
# ============================================================

def run_full_evaluation_no_gt(rag_pipeline_func, dataset: str = "both") -> tuple:
    if dataset == "pi":
        questions = EVAL_QUESTIONS_PI
    elif dataset == "kkp":
        questions = EVAL_QUESTIONS_KKP
    elif dataset == "both":
        questions = EVAL_QUESTIONS_PI + EVAL_QUESTIONS_KKP
    else:
        raise ValueError(f"Invalid dataset: {dataset}. Must be 'pi', 'kkp', or 'both'")

    # --- Generate answers ---
    answers, contexts = [], []
    for i, question in enumerate(questions, 1):
        logger.info(f"[{i}/{len(questions)}] {question[:70]}...")
        try:
            answer, context_list = rag_pipeline_func(question)
            answers.append(answer)
            contexts.append(context_list)
        except Exception as e:
            logger.error(f"Error pada pertanyaan {i}: {e}")
            answers.append("Error generating answer")
            contexts.append([])

    # --- Evaluate ---
    results = evaluate_rag_no_ground_truth(
        questions=questions,
        answers=answers,
        contexts=contexts,
        dataset_name=dataset,
    )

    # --- Save ---
    main_file = save_evaluation_results(results)
    review_file = export_manual_review_items(results)

    return results, main_file, review_file


# ============================================================
# ENTRY POINT
# ============================================================

# Catatan: entry point CLI sengaja dipindah ke `main.py`
# (subcommand `--evaluate-no-gt`). Modul evaluasi di dalam src/ tidak
# boleh mengimport `main.py` di root karena membuat dependency terbalik.
#
# Untuk menjalankan evaluasi gunakan:
#     python main.py --evaluate-no-gt --dataset both