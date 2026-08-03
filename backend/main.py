"""
Penggunaan:
    python main.py                                      # Start FastAPI server (REST API + Telegram Bot)
    python main.py --cli                                # Mode CLI interaktif
    python main.py --question "Apa syarat untuk mengambil PI?"
    python main.py --ingest
    python main.py --evaluate
    python main.py --debug --question "..."
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import itertools
import time
from pathlib import Path
from loguru import logger
import uvicorn

from config.settings import get_settings

class Spinner:
    def __init__(self, message="Sedang mencari jawaban..."):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.delay = 0.1
        self.busy = False
        self.spinner_visible = False
        self.message = message
        sys.stdout.write('\n')

    def write_next(self):
        with self._screen_lock:
            if not self.spinner_visible:
                sys.stdout.write(f"\r{next(self.spinner)} {self.message}")
                self.spinner_visible = True
                sys.stdout.flush()

    def remove_spinner(self, cleanup=False):
        with self._screen_lock:
            if self.spinner_visible:
                sys.stdout.write('\r' + ' ' * (len(self.message) + 2) + '\r')
                self.spinner_visible = False
                if cleanup:
                    sys.stdout.write('\r')
                sys.stdout.flush()

    def spinner_task(self):
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self):
        self._screen_lock = threading.Lock()
        self.busy = True
        self.thread = threading.Thread(target=self.spinner_task)
        self.thread.start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        self.remove_spinner(cleanup=True)
        if self.thread.is_alive():
            self.thread.join()

def setup_logger(debug: bool = False) -> None:
    """Setup loguru logger."""
    logger.remove()

    if debug:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<level>{message}</level>"
            ),
        )

def run_rag_pipeline(question: str, debug: bool = False) -> dict:
    from src.retrieval.pipeline import run_retrieval
    from src.generation.chain import _format_context, generate_answer

    metadata: dict = {}

    logger.info("=" * 60)
    logger.info("TAHAP 1-4: Self-Query → Hybrid Search → Parent Fetch → Rerank")
    logger.info("=" * 60)

    retrieval = run_retrieval(query=question)
    reranked_parents = retrieval.parent_documents

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
                "dalam panduan KKP/PI. Silakan coba pertanyaan lain atau "
                "konsultasikan dengan Dosen Pembimbing."
            ),
            "contexts": [],
            "metadata": metadata,
        }

    logger.info("=" * 60)
    logger.info("TAHAP 5: Prompt Engineering + LLM Generation")
    logger.info("=" * 60)

    context_str = _format_context(reranked_parents)
    contexts_list = [p["content"] for p in reranked_parents]

    if debug:
        logger.debug(f"  Context length: {len(context_str)} chars")
        logger.debug(f"  Num context docs: {len(contexts_list)}")

    answer = generate_answer(question=question, context=context_str)

    metadata["generation"] = {
        "context_length": len(context_str),
        "answer_length": len(answer),
    }

    return {
        "answer": answer,
        "contexts": contexts_list,
        "metadata": metadata,
    }


def run_ingest(dataset: str = "both") -> None:
    from src.ingestion.embedder import run_ingestion

    project_root = Path(__file__).resolve().parent
    dataset_map = {
        "pi": ("PI/child_chunk_pi.json", "PI/parent_chunk_pi.json"),
        "kkp": ("KKP/child_chunk_kkp.json", "KKP/parent_chunk_kkp.json"),
        "skripsi": ("Skripsi/child_chunk_skripsi.json", "Skripsi/parent_chunk_skripsi.json"),
        "non_skripsi": ("Non-Skripsi/child_chunk_non-skripsi.json", "Non-Skripsi/parent_chunk_non-skripsi.json"),
    }

    def ingest_one(name: str) -> None:
        child_file, parent_file = dataset_map[name]
        child_path = project_root / "extract-pdf" / child_file
        parent_path = project_root / "extract-pdf" / parent_file

        if not child_path.exists():
            logger.error(f"File tidak ditemukan: {child_path}")
            sys.exit(1)
        if not parent_path.exists():
            logger.error(f"File tidak ditemukan: {parent_path}")
            sys.exit(1)

        stats = run_ingestion(
            child_chunks_path=str(child_path),
            parent_chunks_path=str(parent_path),
        )

        logger.info(f"Ingestion selesai untuk {name.upper()}!")
        logger.info(f"Stats: {stats}")

    if dataset in ("both", "all"):
        for name in dataset_map.keys():
            ingest_one(name)
    else:
        ingest_one(dataset)


def run_eval(dataset: str = "pi") -> None:
    from src.evaluation.ragas_eval import (
        run_evaluation,
        EVAL_QUESTIONS_PI,
        EVAL_QUESTIONS_KKP,
    )

    dataset_map = {
        "pi": EVAL_QUESTIONS_PI,
        "kkp": EVAL_QUESTIONS_KKP,
        "both": EVAL_QUESTIONS_PI + EVAL_QUESTIONS_KKP,
    }

    eval_data = dataset_map.get(dataset, EVAL_QUESTIONS_PI)
    logger.info(f"Evaluasi dataset: {dataset.upper()} ({len(eval_data)} pertanyaan)")

    def pipeline_fn(question: str) -> dict:
        result = run_rag_pipeline(question, debug=False)
        return {"answer": result["answer"], "contexts": result["contexts"]}

    scores = run_evaluation(pipeline_fn=pipeline_fn, eval_data=eval_data)
    logger.info(f"Evaluation scores: {scores}")


def run_eval_no_gt(dataset: str = "both") -> None:
    from src.evaluation.ragas_eval_no_gt import run_full_evaluation_no_gt
    
    logger.info(f"🚀 Starting evaluation WITHOUT ground truth for {dataset} dataset...")
    
    def pipeline_fn(question: str):
        """Wrapper untuk RAG pipeline"""
        result = run_rag_pipeline(question, debug=False)
        return result["answer"], result["contexts"]
    
    results, main_file, review_file = run_full_evaluation_no_gt(pipeline_fn, dataset=dataset)
    
    logger.info(f"\n✅ Evaluation complete!")
    logger.info(f"📄 Results saved to: {main_file}")
    if review_file:
        logger.info(f"🔍 Manual review items saved to: {review_file}")
    logger.info(f"🎯 Overall Pass (No Guardrail Failures): {'✅ YES' if results.get('overall_pass') else '❌ NO'}")


def _print_answer(answer: str, num_docs: int) -> None:
    print("-" * 60)
    print("JAWABAN:")
    print("-" * 60)
    print(answer)
    print("-" * 60)
    if num_docs > 0:
        print(f"Sumber: {num_docs} dokumen digunakan")


def run_interactive(debug: bool = False) -> None:
    from src.services.ai_services import chat, get_or_create_memory

    print("\n" + "=" * 60)
    print("🎓 Chatbot Panduan KKP/PI")
    print("   STMIK Widya Cipta Dharma")
    print("=" * 60)
    print("Ketik pertanyaan Anda, atau 'quit' untuk keluar.\n")

    session_id = "cli_session_1"

    while True:
        try:
            question = input("📝 Pertanyaan: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSampai jumpa! 👋")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q", "keluar"):
            print("\nSampai jumpa! 👋")
            break

        try:
            with Spinner("Sedang mencari jawaban..."):
                result = chat(question, session_id=session_id)
            
            _print_answer(result.get("answer", ""), result.get("num_docs", 0))

        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\n❌ Terjadi error: {e}")
            print("Silakan coba lagi.\n")

        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG Chatbot - Panduan KKP/PI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python main.py                                    # start FastAPI server (REST API + Telegram Bot)
  python main.py --cli                              # mode CLI interaktif
  python main.py --question "Apa syarat PI?"        # single question
  python main.py --ingest --dataset all             # ingest semua data (pi, kkp, skripsi, non_skripsi)
  python main.py --ingest --dataset pi              # ingest data PI
  python main.py --ingest --dataset skripsi         # ingest data skripsi
  python main.py --evaluate                         # evaluasi dengan RAGAS
  python main.py --debug --question "..."           # debug mode
        """,
    )

    parser.add_argument(
        "--cli",
        action="store_true",
        help="Jalankan mode CLI interaktif",
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        help="Pertanyaan tunggal (tanpa mode interaktif)",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Jalankan ingestion: embed + upload data ke Supabase",
    )
    parser.add_argument(
        "--dataset",
        choices=["pi", "kkp", "skripsi", "non_skripsi", "both", "all"],
        default="all",
        help="Dataset ingestion: pi, kkp, skripsi, non_skripsi, atau all",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Jalankan evaluasi RAGAS pada pipeline (dengan ground truth)",
    )
    parser.add_argument(
        "--evaluate-no-gt",
        action="store_true",
        help="Jalankan evaluasi RAGAS TANPA ground truth (lebih objektif)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Tampilkan detail setiap tahap pipeline",
    )

    args = parser.parse_args()
    setup_logger(debug=args.debug)

    try:
        settings = get_settings()
        logger.info(
            f"Settings loaded: LLM={settings.llm_model}, "
            f"Embedding={settings.embedding_model}"
        )
    except Exception as e:
        logger.error(f"Gagal load settings: {e}")
        logger.error("Pastikan file .env sudah dikonfigurasi dengan benar.")
        sys.exit(1)

    if args.ingest:
        run_ingest(args.dataset)
    elif args.evaluate:
        run_eval(dataset=args.dataset)
    elif args.evaluate_no_gt:
        run_eval_no_gt(dataset=args.dataset)
    elif args.question:
        result = run_rag_pipeline(args.question, debug=args.debug)
        print("\n" + "-" * 60)
        print("JAWABAN:")
        print("-" * 60)
        print(result["answer"])
        print("-" * 60)
    elif args.cli:
        run_interactive(debug=args.debug)
    else:
        # Default: Start FastAPI server
        port = int(os.environ.get("PORT", 8000))
        is_reload = settings.ENVIRONMENT == "development"
        
        logger.info(f"Starting FastAPI server on port {port}")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Reload mode: {'enabled' if is_reload else 'disabled'}")
        
        project_root = Path(__file__).resolve().parent
        
        uvicorn.run(
            "application:create_app",
            host="0.0.0.0",
            port=port,
            reload=is_reload,
            factory=True,
            reload_dirs=[str(project_root)] if is_reload else None,
        )


if __name__ == "__main__":
    main()