"""
Penggunaan:
    python main.py                                      # Start FastAPI server (REST API + Telegram Bot)
    python main.py --cli                                # Mode CLI interaktif
    python main.py --question "Apa syarat untuk mengambil PI?"
    python main.py --ingest --dataset all
    python main.py --evaluate --dataset both
    python main.py --evaluate-no-gt
    python main.py --debug --question "..."
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import itertools
import time
import uuid
from pathlib import Path
from loguru import logger
import uvicorn

from config.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent
SEPARATOR = "-" * 60

DATASET_FILES: dict[str, tuple[str, str]] = {
    "pi": ("PI/child_chunk_pi.json", "PI/parent_chunk_pi.json"),
    "kkp": ("KKP/child_chunk_kkp.json", "KKP/parent_chunk_kkp.json"),
    "skripsi": ("Skripsi/child_chunk_skripsi.json", "Skripsi/parent_chunk_skripsi.json"),
    "non_skripsi": ("Non-Skripsi/child_chunk_non-skripsi.json", "Non-Skripsi/parent_chunk_non-skripsi.json"),
}
 
DATASET_GROUPS: dict[str, list[str]] = {
    "both": ["pi", "kkp"],
    "skripsi_only": ["skripsi"],
    "non_skripsi_only": ["non_skripsi"],
    "skripsi_group": ["skripsi", "non_skripsi"],
    "all": list(DATASET_FILES.keys()),
}

class Spinner:
    """Menampilkan animasi loading sederhana di terminal."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        message="Sedang mencari jawaban...",
        delay=0.1,
    ):
        self.message = message
        self.delay = delay

        # Mengambil frame secara berulang: ⠋ → ⠙ → ⠹ → ... → ⠏ → ⠋ → ...
        self.frames = itertools.cycle(self.FRAMES)

        # Menandakan apakah spinner masih berjalan
        self.running = False

        # Thread yang menjalankan animasi
        self.thread = None

        # Digunakan agar thread tidak menulis ke terminal bersamaan
        self.lock = threading.Lock()

    def __enter__(self):
        """Dipanggil ketika masuk ke blok 'with'."""

        self.running = True

        self.thread = threading.Thread(
            target=self.run,
        )

        self.thread.start()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Dipanggil ketika keluar dari blok 'with'."""

        self.running = False

        if self.thread is not None:
            self.thread.join()

        self.clear()

    def run(self):
        """Menjalankan animasi spinner."""

        while self.running:
            self.show_frame()
            time.sleep(self.delay)

    def show_frame(self):
        """Menampilkan satu frame spinner."""

        frame = next(self.frames)

        with self.lock:
            sys.stdout.write(
                f"\r{frame} {self.message}"
            )
            sys.stdout.flush()

    def clear(self):
        """Menghapus spinner dari terminal."""

        with self.lock:
            spaces = " " * (len(self.message) + 2)

            sys.stdout.write("\r" + spaces + "\r")
            sys.stdout.flush()


def setup_logger(debug: bool = False) -> None:
    """Konfigurasi Loguru dengan format berbeda untuk mode debug."""
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    location = (
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        if debug else ""
    )

    log_format = (
        "<green>{time:HH:mm:ss}</green> |<level>{level: <8}</level> | "
        f"{location}"
        "<level>{message}</level>"
    )
    # contoh hasil
    # 12:34:56 | DEBUG    | module:function:42 | Pesan log

    logger.add(
        sys.stderr,
        level=level,
        format=log_format,
    )

def run_rag_pipeline(question: str, debug: bool = False) -> dict:
    """Jalankan pipeline RAG lengkap: retrieval (self-query -> hybrid search ->
    parent fetch -> rerank) lalu generation (prompt engineering -> LLM)."""
    from src.retrieval.pipeline import run_retrieval
    from src.generation.chain import format_context, generate_answer
 
    logger.info(SEPARATOR)
    logger.info("TAHAP 1-4: Self-Query -> Hybrid Search -> Parent Fetch -> Rerank")
    logger.info(SEPARATOR)
 
    retrieval = run_retrieval(query=question)
    reranked_parents = retrieval.parent_documents
    
    metadata: dict = {}
    metadata["retrieval"] = {
        "num_parents": retrieval.num_docs,
        "parents": [
            {
                "parent_id": p.get("parent_id", ""),
                "title": p.get("title", ""),
                "ce_score": round(p.get("cross_encoder_score", 0), 4),
                "matched_children": p.get("matched_children", []),
            }
            for p in reranked_parents
        ],
    }
 
    if debug:
        for i, p in enumerate(reranked_parents, 1):
            logger.debug(
                f"  [{i}] {p.get('parent_id')} | "
                f"CE={p.get('cross_encoder_score', 0):.4f} | "
                f"{p.get('title', '')[:50]}"
            )
 
    if retrieval.is_empty:
        return {
            "answer": (
                "Maaf, saya tidak menemukan informasi yang relevan "
                "dalam panduan Resmi. Silakan coba pertanyaan lain atau "
                "konsultasikan dengan Dosen Pembimbing."
            ),
            "contexts": [],
            "metadata": metadata,
        }
 
    logger.info(SEPARATOR)
    logger.info("TAHAP 5: Prompt Engineering + LLM Generation")
    logger.info(SEPARATOR)
 
    context_str = format_context(retrieval.parent_documents)
    contexts_list = [p["content"] for p in retrieval.parent_documents]
 
    if debug:
        logger.debug(f"  Context length: {len(context_str)} chars")
        logger.debug(f"  Num context docs: {len(contexts_list)}")
 
    answer = generate_answer(question=question, context=context_str)
 
    metadata["generation"] = {
        "context_length": len(context_str),
        "answer_length": len(answer),
    }
 
    return {"answer": answer, "contexts": contexts_list, "metadata": metadata}

def run_ingest(dataset: str = "all") -> None:
    """Jalankan ingestion (embed + upload ke Supabase) untuk satu dataset
    atau sekumpulan dataset ("both" = pi+kkp, "all" = semua dataset)."""
    from src.ingestion.embedder import run_ingestion
 
    names = DATASET_GROUPS.get(dataset, [dataset])
    for name in names:
        _ingest_dataset(name, run_ingestion)

def _ingest_dataset(name: str, run_ingestion) -> None:
    if name not in DATASET_FILES:
        logger.error(f"Dataset tidak dikenali: {name}")
        sys.exit(1)
 
    child_file, parent_file = DATASET_FILES[name]
    child_path = PROJECT_ROOT / "extract-pdf" / child_file
    parent_path = PROJECT_ROOT / "extract-pdf" / parent_file
 
    for path in (child_path, parent_path):
        if not path.exists():
            logger.error(f"File tidak ditemukan: {path}")
            sys.exit(1)
 
    stats = run_ingestion(
        child_chunks_path=str(child_path),
        parent_chunks_path=str(parent_path),
    )
    logger.info(f"Ingestion selesai untuk {name.upper()}!")
    logger.info(f"Stats: {stats}")

def run_eval(dataset: str = "pi") -> None:
    """Evaluasi RAG pipeline dengan RAGAS (menggunakan ground truth)."""
    from src.evaluation.ragas_eval import (
        run_evaluation,
        EVAL_QUESTIONS_PI,
        EVAL_QUESTIONS_KKP,
    )
 
    eval_question_map = {
        "pi": EVAL_QUESTIONS_PI,
        "kkp": EVAL_QUESTIONS_KKP,
        "both": EVAL_QUESTIONS_PI + EVAL_QUESTIONS_KKP,
    }
 
    if dataset not in eval_question_map:
        logger.error(
            f"Dataset '{dataset}' tidak didukung untuk --evaluate. "
            f"Pilihan yang valid: {', '.join(eval_question_map)}."
        )
        sys.exit(1)
 
    eval_data = eval_question_map[dataset]
    logger.info(f"Evaluasi dataset: {dataset.upper()} ({len(eval_data)} pertanyaan)")
 
    def pipeline_fn(question: str) -> dict:
        result = run_rag_pipeline(question, debug=False)
        return {"answer": result["answer"], "contexts": result["contexts"]}
 
    scores = run_evaluation(pipeline_fn=pipeline_fn, eval_data=eval_data)
    logger.info(f"Evaluation scores: {scores}")
 
 
def run_eval_no_gt(dataset: str = "all") -> None:
    """Evaluasi RAG pipeline TANPA ground truth (lebih objektif)."""
    from src.evaluation.ragas_eval_no_gt import run_full_evaluation_no_gt
 
    logger.info(f"Memulai evaluasi tanpa ground truth untuk dataset: {dataset}")
 
    def pipeline_fn(question: str):
        result = run_rag_pipeline(question, debug=False)
        return result["answer"], result["contexts"]
 
    results, main_file, review_file = run_full_evaluation_no_gt(pipeline_fn, dataset=dataset)
 
    logger.info("Evaluasi selesai!")
    logger.info(f"Hasil disimpan di: {main_file}")
    if review_file:
        logger.info(f"Item untuk review manual disimpan di: {review_file}")
 
    status = "LULUS" if results.get("overall_pass") else "TIDAK LULUS"
    logger.info(f"Ringkasan (tanpa guardrail failure): {status}")


def _print_answer(answer: str, num_docs: int = 0) -> None:
    print(SEPARATOR)
    print("JAWABAN:")
    print(SEPARATOR)
    print(answer)
    print(SEPARATOR)
    if num_docs > 0:
        print(f"Sumber: {num_docs} dokumen digunakan")
 
 
def run_interactive(debug: bool = False) -> None:
    """Mode CLI interaktif dengan sesi chat yang mempertahankan histori percakapan."""
    from src.services.ai_services import chat
 
    print("\n" + SEPARATOR)
    print("Chatbot Panduan KKP/PI")
    print("STMIK Widya Cipta Dharma")
    print(SEPARATOR)
    print("Ketik pertanyaan Anda, atau 'quit' untuk keluar.\n")
 
    session_id = f"cli_session_{uuid.uuid4().hex[:8]}"
    exit_commands = {"quit", "exit", "q", "keluar"}
 
    while True:
        try:
            question = input("Pertanyaan: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSampai jumpa!")
            break
 
        if not question:
            continue
        if question.lower() in exit_commands:
            print("\nSampai jumpa!")
            break
 
        try:
            with Spinner("Sedang mencari jawaban..."):
                result = chat(question, session_id=session_id, username="cli_user", channel="cli")
            _print_answer(result.get("answer", ""), result.get("num_docs", 0))
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\nTerjadi error: {e}")
            print("Silakan coba lagi.\n")
 
        print()

def run_server(settings) -> None:
    """Start FastAPI server (REST API + Telegram Bot)."""
    port = int(os.environ.get("PORT", 8000))
    is_reload = settings.ENVIRONMENT == "development"
 
    logger.info(f"Starting FastAPI server on port {port}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Reload mode: {'enabled' if is_reload else 'disabled'}")
 
    uvicorn.run(
        "application:create_app",
        host="0.0.0.0",
        port=port,
        reload=is_reload,
        factory=True,
        reload_dirs=[str(PROJECT_ROOT)] if is_reload else None,
    )

def build_arg_parser() -> argparse.ArgumentParser:
    """Buat parser argumen CLI."""
    parser = argparse.ArgumentParser(
        description="RAG Chatbot - Panduan KKP/PI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python main.py                                    # start FastAPI server (REST API + Telegram Bot)
  python main.py --cli                              # mode CLI interaktif
  python main.py --question "Apa syarat PI?"        # single question
  python main.py --ingest --dataset all             # ingest semua dataset (pi, kkp, skripsi, non_skripsi)
  python main.py --ingest --dataset both            # ingest dataset utama (pi, kkp)
  python main.py --ingest --dataset skripsi         # ingest data skripsi saja
  python main.py --evaluate --dataset both          # evaluasi RAGAS dengan ground truth
  python main.py --evaluate-no-gt                   # evaluasi RAGAS tanpa ground truth
  python main.py --debug --question "..."           # debug mode
        """,
    )
 
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument("--cli", action="store_true", help="Jalankan mode CLI interaktif")
    commands.add_argument("--question", "-q", type=str, help="Pertanyaan tunggal (tanpa mode interaktif)")
    commands.add_argument("--ingest", action="store_true", help="Jalankan ingestion: embed + upload data ke Supabase")
    commands.add_argument("--evaluate", action="store_true", help="Jalankan evaluasi RAGAS (dengan ground truth)")
    commands.add_argument("--evaluate-no-gt", action="store_true", help="Jalankan evaluasi RAGAS TANPA ground truth")
 
    parser.add_argument(
        "--dataset",
        choices=["pi", "kkp", "skripsi", "non_skripsi", "both", "all"],
        default="all",
        help="Dataset untuk --ingest/--evaluate/--evaluate-no-gt: pi, kkp, skripsi, non_skripsi, both, atau all",
    )
    parser.add_argument("--debug", action="store_true", help="Tampilkan detail setiap tahap pipeline")
 
    return parser


def _load_settings():
    try:
        return get_settings()
    except Exception as e:
        logger.error(f"Gagal load settings: {e}")
        logger.error("Pastikan file .env sudah dikonfigurasi dengan benar.")
        sys.exit(1)
 
 
def _handle_question(question: str, debug: bool) -> None:
    try:
        result = run_rag_pipeline(question, debug=debug)
    except Exception as e:
        logger.error(f"Gagal memproses pertanyaan: {e}")
        print(f"\nTerjadi error: {e}")
        sys.exit(1)
    else:
        _print_answer(result["answer"], num_docs=len(result.get("contexts", [])))
 
 
def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    setup_logger(debug=args.debug)
 
    settings = _load_settings()
    logger.info(
        f"Settings loaded: LLM={settings.llm_model}, "
        f"Embedding={settings.embedding_model}"
    )
 
    if args.ingest:
        run_ingest(args.dataset)
    elif args.evaluate:
        run_eval(dataset=args.dataset)
    elif args.evaluate_no_gt:
        run_eval_no_gt(dataset=args.dataset)
    elif args.question:
        _handle_question(args.question, debug=args.debug)
    elif args.cli:
        run_interactive(debug=args.debug)
    else:
        run_server(settings)
 
 
if __name__ == "__main__":
    main()
