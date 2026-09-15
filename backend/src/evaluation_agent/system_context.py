"""Bounded source excerpts and safe settings for actionable RAG reviews."""

from __future__ import annotations

import ast

from config.settings import get_settings
from src.monitoring.pipeline_snapshot import (
    PROJECT_ROOT,
    SETTING_NAMES,
    capture_pipeline_snapshot,
)


STAGE_SOURCES = {
    "query_processing": {
        "src/retrieval/query_planner.py": ("build_query_plan", "decompose_query"),
        "src/retrieval/self_query.py": ("_detect_source", "_detect_section"),
    },
    "retrieval": {
        "src/retrieval/hybrid_search.py": (
            "HybridSearcher.search",
            "HybridSearcher._execute_search",
        ),
    },
    "parent_assembly": {
        "src/retrieval/parent_child.py": (
            "ParentChildFetcher.fetch_parents",
            "ParentChildFetcher._attach_metadata",
        ),
    },
    "reranking": {
        "src/retrieval/pipeline.py": ("_select_reranked_documents",),
        "src/retrieval/reranker.py": (
            "CrossEncoderReranker.rerank",
            "CrossEncoderReranker._build_pairs",
        ),
    },
    "context_assembly": {
        "src/generation/chain.py": ("format_context", "build_messages")
    },
    "generation": {
        "src/generation/chain.py": (
            "SYSTEM_PROMPT",
            "USER_PROMPT",
            "RAGGenerator.generate",
        )
    },
}
MAX_EXCERPT_CHARS = 16_000


def _source_excerpt(path: str, symbols: tuple[str, ...], checksum: str) -> dict:
    text = (PROJECT_ROOT / path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    selected = []
    for symbol in symbols:
        parts = symbol.split(".")
        nodes = tree.body
        node = None
        for part in parts:
            node = next(
                (
                    item
                    for item in nodes
                    if getattr(item, "name", None) == part
                    or isinstance(item, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == part
                        for target in item.targets
                    )
                ),
                None,
            )
            if node is None:
                break
            nodes = getattr(node, "body", [])
        if node is not None:
            source = ast.get_source_segment(text, node) or ""
            selected.append(
                {
                    "symbol": symbol,
                    "line": node.lineno,
                    "code": source[:MAX_EXCERPT_CHARS],
                    "truncated": len(source) > MAX_EXCERPT_CHARS,
                }
            )
    return {"path": path, "sha256": checksum, "excerpts": selected}


def build_system_context(failed_stage: str, trace: dict, settings=None) -> dict:
    settings = settings or get_settings()
    current = capture_pipeline_snapshot(settings)
    allowed = set(current)
    historical = {
        key: value
        for key, value in trace.get("pipeline_snapshot", {}).items()
        if key in allowed
    }
    selected = dict(STAGE_SOURCES.get(failed_stage, {}))
    # Review downstream answer behavior as a secondary issue, without replacing
    # the earliest failure in the trace.
    selected.setdefault("src/generation/chain.py", ("SYSTEM_PROMPT", "USER_PROMPT"))
    checksums = current["implementation_checksums"]
    constraints = {}
    for name in (*SETTING_NAMES, "MAX_CONTEXT_TOKENS"):
        field = type(settings).model_fields[name]
        constraints[name] = {
            "description": field.description,
            **{
                bound: getattr(item, bound)
                for item in field.metadata
                for bound in ("ge", "le")
                if hasattr(item, bound)
            },
        }
    return {
        "request_configuration": historical,
        "current_configuration": current,
        "setting_constraints": constraints,
        "configuration_location": "config/settings.py; override via environment variables",
        "implementation_at_request_known": bool(
            historical.get("implementation_checksums")
        ),
        "source_matches_request": {
            path: historical.get("implementation_checksums", {}).get(path)
            == checksums[path]
            if path in historical.get("implementation_checksums", {})
            else None
            for path in selected
        },
        "current_source_excerpts": [
            _source_excerpt(path, symbols, checksums[path])
            for path, symbols in selected.items()
        ],
        "limitations": [
            "Source excerpts describe the current checkout, not necessarily the failed request.",
            "A missing historical rerank score cannot prove that a threshold was too strict.",
            "Changing a model or parameter is an experiment until regression tests pass.",
        ],
    }
