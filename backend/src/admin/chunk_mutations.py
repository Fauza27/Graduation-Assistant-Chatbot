"""Admin writes: validate inputs, call atomic database operations, embed content.

Parent synchronization and edit-log updates belong to the same database
transaction. See scripts/supabase_migration_chunk_consistency.sql.
"""

from typing import Any

from loguru import logger
from postgrest.exceptions import APIError
from supabase import Client

from src.admin.auth import ResourceNotFoundError


class ChunkConflictError(ValueError):
    """The chunk changed or cannot safely be synchronized with its parent."""


def _call_chunk_rpc(supabase: Client, name: str, params: dict) -> Any:
    """Translate database errors into the exceptions used by the admin API."""
    try:
        return supabase.rpc(name, params).execute().data
    except APIError as exc:
        if exc.code == "P0002":
            raise ResourceNotFoundError(exc.message) from exc
        if exc.code == "40001":
            raise ChunkConflictError(exc.message) from exc
        if exc.code == "22023":
            raise ValueError(exc.message) from exc
        raise


def _validate_updates(
    title: str | None, pages: str | None, content: str | None,
) -> None:
    if title is None and pages is None and content is None:
        raise ValueError("At least one field must be provided for update")
    for name, value, limit in (
        ("Title", title, 500),
        ("Pages", pages, 200),
        ("Content", content, 32000),
    ):
        if value is None:
            continue
        if not value.strip():
            raise ValueError(f"{name} tidak boleh kosong jika diisi")
        if len(value) > limit:
            raise ValueError(f"{name} terlalu panjang (maksimal {limit} karakter)")


def save_chunk(
    child_id: str,
    admin_id: str,
    supabase: Client,
    title: str | None = None,
    pages: str | None = None,
    content: str | None = None,
) -> dict:
    """Save draft changes and their audit log in one transaction."""
    _validate_updates(title, pages, content)
    return _call_chunk_rpc(supabase, "save_knowledge_chunk", {
        "p_child_id": child_id,
        "p_admin_id": admin_id,
        "p_title": title.strip() if title is not None else None,
        "p_pages": (
            [page.strip() for page in pages.split(",") if page.strip()]
            if pages is not None else None
        ),
        "p_content": content.strip() if content is not None else None,
    })


def trigger_reembed(child_id: str, admin_id: str, supabase: Client) -> dict:
    """Reserve the current draft so another job cannot embed an older edit."""
    return _call_chunk_rpc(supabase, "begin_chunk_reembed", {
        "p_child_id": child_id,
        "p_admin_id": admin_id,
    })


def delete_chunk(child_id: str, supabase: Client) -> dict:
    """Remove the child, published parent text, child ID, and logs atomically."""
    return _call_chunk_rpc(supabase, "delete_knowledge_chunk", {
        "p_child_id": child_id,
    })


def _create_chunk_embedding(content: str) -> list[float]:
    # Keep the existing embedding configuration; load it only for embedding work.
    from src.ingestion.embedder import get_openai_embeddings

    return get_openai_embeddings([content])[0]


def process_chunk_reembed(
    log_id: str,
    child_id: str,
    new_content: str,
    supabase: Client,
) -> None:
    """Embed outside a transaction, then atomically publish the reserved draft.

    This is synchronous so FastAPI runs the blocking work in its thread pool.
    A failed publish rolls back parent, child, and log changes together.
    """
    try:
        embedding = _create_chunk_embedding(new_content)
        _call_chunk_rpc(supabase, "complete_chunk_reembed", {
            "p_log_id": log_id,
            "p_child_id": child_id,
            "p_embedding": embedding,
        })
    except Exception as exc:
        logger.exception("Reembedding failed for chunk {} (log {})", child_id, log_id)
        try:
            _call_chunk_rpc(supabase, "fail_chunk_reembed", {
                "p_log_id": log_id,
                "p_child_id": child_id,
                "p_error": str(exc)[:500],
            })
        except Exception:
            # Preserve the original error; a failure report must not mask it.
            logger.exception("Failed to record reembedding failure for log {}", log_id)
        raise

    logger.info("Successfully reembedded chunk {}", child_id)
