"""Thread-safe retrieval cache invalidated by a shared database revision."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import Any

from cachetools import TTLCache
from loguru import logger


@lru_cache(maxsize=1)
def _get_supabase_client():
    """Reuse the service client, but never cache the knowledge revision."""
    from supabase import create_client

    from config.settings import get_settings

    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def read_knowledge_revision() -> int:
    """Read the revision committed with the latest document mutation."""
    response = (
        _get_supabase_client()
        .table("knowledge_base_revision")
        .select("revision")
        .eq("id", 1)
        .execute()
    )
    rows = response.data
    if not rows or len(rows) != 1:
        raise ValueError("Knowledge revision row is missing")

    revision = rows[0].get("revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("Knowledge revision must be a non-negative integer")
    return revision


@dataclass
class RetrievalCacheEntry:
    documents: list[dict]
    metrics: dict[str, Any]


class RevisionedRetrievalCache:
    """Keep results locally while observing document edits from every worker.

    A database lookup is required before every cache read. If it fails, cached
    results are bypassed. Retrieval spanning a revision change is not cached.
    TTL bounds retention only; it is not the document invalidation mechanism.
    """

    def __init__(
        self,
        revision_reader: Callable[[], int] = read_knowledge_revision,
        *,
        maxsize: int = 500,
        ttl: int = 1800,
    ) -> None:
        self._revision_reader = revision_reader
        self._entries = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = Lock()

    def _read_revision(self) -> int | None:
        try:
            return self._revision_reader()
        except Exception as exc:
            logger.warning(
                "Retrieval cache bypassed: knowledge revision unavailable ({})",
                type(exc).__name__,
            )
            return None

    def lookup(
        self, resolved_query: str, original_question: str
    ) -> tuple[int | None, RetrievalCacheEntry | None]:
        revision = self._read_revision()
        if revision is None:
            return None, None

        # Both inputs affect retrieval: resolved_query selects candidates and
        # original_question determines their cross-encoder ranking.
        key = (revision, resolved_query, original_question)
        with self._lock:
            return revision, deepcopy(self._entries.get(key))

    def store_if_current(
        self,
        revision: int | None,
        resolved_query: str,
        original_question: str,
        documents: list[dict],
        metrics: dict[str, Any],
    ) -> bool:
        if revision is None or self._read_revision() != revision:
            return False

        key = (revision, resolved_query, original_question)
        entry = RetrievalCacheEntry(documents=documents, metrics=metrics)
        with self._lock:
            # Generation and monitoring can mutate their copies independently.
            self._entries[key] = deepcopy(entry)
        return True
