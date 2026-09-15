"""Explicit, credential-free configuration and implementation provenance."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from config.settings import get_settings
from src.retrieval.reranker import DEFAULT_MAX_CONTENT_CHARS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTING_NAMES = (
    "llm_model",
    "embedding_model",
    "cross_encoder_model",
    "cross_encoder_batch_size",
    "retrieval_top_k",
    "max_parent_for_rerank",
    "min_parent_for_rerank",
    "rerank_top_n",
    "rerank_min_top_score",
    "rerank_relative_gap",
    "bm25_weight",
    "dense_weight",
    "dense_fallback_threshold",
    "MEMORY_MAX_HISTORY_TOKENS",
    "MEMORY_MIN_RECENT_TURNS",
    "MEMORY_SUMMARY_MAX_TOKENS",
)
SOURCE_FILES = (
    "src/retrieval/query_planner.py",
    "src/retrieval/self_query.py",
    "src/retrieval/hybrid_search.py",
    "src/retrieval/parent_child.py",
    "src/retrieval/pipeline.py",
    "src/retrieval/reranker.py",
    "src/generation/chain.py",
)


def implementation_checksums() -> dict[str, str]:
    """Hash only fixed pipeline files; never inspect .env or credentials."""
    return {
        name: sha256((PROJECT_ROOT / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }


def capture_pipeline_snapshot(settings=None) -> dict:
    settings = settings or get_settings()
    return {
        "app_version": settings.VERSION,
        **{name: getattr(settings, name) for name in SETTING_NAMES},
        "max_context_tokens": settings.MAX_CONTEXT_TOKENS,
        "rerank_max_content_chars": DEFAULT_MAX_CONTENT_CHARS,
        "implementation_checksums": implementation_checksums(),
    }
