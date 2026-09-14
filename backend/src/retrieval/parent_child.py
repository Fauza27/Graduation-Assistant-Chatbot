"""Fetch parent documents for retrieved child chunks."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from loguru import logger
from src.monitoring.errors import RetrievalError
from supabase import Client, create_client

from config.settings import get_settings
from src.retrieval.hybrid_search import HybridSearchResult


from src.utils.page_sorting import smart_page_sort_key as _smart_page_sort_key


@dataclass
class ParentMatchInfo:
    """Aggregated matching information for one parent."""

    best_score: float
    matched_children: list[str] = field(
        default_factory=list
    )
    score_source: str = "rrf"


class ParentChildFetcher:
    """
    Fetch parent chunks corresponding to retrieved children.

    Responsibilities:
        - Deduplicate parent IDs
        - Track best child score
        - Track matched child IDs
        - Fetch parent documents
        - Fetch matched child pages
        - Attach retrieval metadata
    """

    def __init__(
        self,
        supabase_client: Client | None = None,
    ) -> None:
        settings = get_settings()

        self._supabase = (
            supabase_client
            or create_client(
                settings.supabase_url,
                settings.supabase_service_key,
            )
        )

        self._parent_table = (
            settings.table_parent_chunks
        )
        self._child_table = (
            settings.table_child_chunks
        )

    def fetch_parents(
        self,
        search_results: list[HybridSearchResult],
    ) -> list[dict]:
        """Fetch and enrich parent documents."""

        if not search_results:
            logger.warning(
                "No search results to fetch parent"
            )
            return []

        parent_matches = self._aggregate_parent_matches(
            search_results
        )

        if not parent_matches:
            logger.warning(
                "Tidak ada parent_id valid "
                "dari search results"
            )
            return []

        parent_ids = list(parent_matches.keys())

        logger.info(
            "De-duplikasi: {} children → {} unique parents",
            len(search_results),
            len(parent_ids),
        )

        parents = self._fetch_parent_rows(
            parent_ids
        )

        if not parents:
            return []

        child_pages = self._fetch_child_pages(
            parent_matches
        )

        self._attach_metadata(
            parents,
            parent_matches,
            child_pages,
        )

        parents.sort(
            key=lambda parent: parent.get(
                "best_child_score",
                0.0,
            ),
            reverse=True,
        )

        self._log_summary(parents)

        return parents

    @staticmethod
    def _aggregate_parent_matches(
        search_results: list[HybridSearchResult],
    ) -> dict[str, ParentMatchInfo]:
        """Group child search results by parent ID."""

        matches: dict[str, ParentMatchInfo] = {}

        for result in search_results:
            parent_id = result.parent_id

            if not parent_id:
                logger.warning(
                    "Child '{}' has no parent_id",
                    result.child_id,
                )
                continue

            info = matches.get(parent_id)

            if info is None:
                matches[parent_id] = ParentMatchInfo(
                    best_score=result.hybrid_score,
                    matched_children=[
                        result.child_id
                    ],
                    score_source=result.score_source,
                )
                continue

            info.best_score = max(
                info.best_score,
                result.hybrid_score,
            )

            info.matched_children.append(
                result.child_id
            )

        return matches

    def _fetch_parent_rows(
        self,
        parent_ids: list[str],
    ) -> list[dict]:
        """Fetch parent records from Supabase."""

        started_at = time.time()

        try:
            response = (
                self._supabase
                .table(self._parent_table)
                .select("*")
                .in_(
                    "parent_id",
                    parent_ids,
                )
                .execute()
            )

        except Exception as exc:
            logger.error(
                "Gagal mengambil parent documents: {}",
                exc,
            )
            raise RetrievalError("Parent document fetch gagal") from exc

        elapsed = time.time() - started_at

        logger.info(
            "[Profile] Supabase Parent Fetch: {:.2f}s",
            elapsed,
        )

        parents = response.data or []

        if len(parents) != len(parent_ids):
            found_ids = {
                parent.get(
                    "parent_id",
                    "",
                )
                for parent in parents
            }

            missing_ids = (
                set(parent_ids) - found_ids
            )

            logger.warning(
                "Parent IDs not found in DB: {}",
                missing_ids,
            )

        return parents

    def _fetch_child_pages(
        self,
        parent_matches: dict[str, ParentMatchInfo],
    ) -> dict[str, list[int]]:
        """Fetch page numbers for matched children."""

        child_ids = [
            child_id
            for info in parent_matches.values()
            for child_id in info.matched_children
        ]

        if not child_ids:
            return {}

        child_pages: dict[str, list[int]] = {}

        try:
            response = (
                self._supabase
                .table(self._child_table)
                .select(
                    "id, parent_id, pages"
                )
                .in_(
                    "id",
                    child_ids,
                )
                .execute()
            )

        except Exception as exc:
            logger.warning(
                "Gagal mengambil data halaman child: {}",
                exc,
            )
            return {}

        for row in response.data or []:
            parent_id = row.get(
                "parent_id",
                "",
            )

            pages = row.get(
                "pages"
            ) or []

            if not parent_id or not pages:
                continue

            child_pages.setdefault(
                parent_id,
                []
            ).extend(pages)

        return child_pages

    @staticmethod
    def _attach_metadata(
        parents: list[dict],
        parent_matches: dict[str, ParentMatchInfo],
        child_pages: dict[str, list[int]],
    ) -> None:
        """Attach retrieval metadata to parent records."""

        for parent in parents:
            parent_id = parent.get(
                "parent_id",
                "",
            )

            match = parent_matches.get(
                parent_id
            )

            if match is None:
                continue

            parent[
                "best_child_score"
            ] = match.best_score

            parent[
                "matched_children"
            ] = list(
                match.matched_children
            )

            parent[
                "score_source"
            ] = match.score_source

            parent[
                "search_score_source"
            ] = match.score_source

            parent[
                "matched_pages"
            ] = sorted(
                set(
                    child_pages.get(
                        parent_id,
                        [],
                    )
                ),
                key=_smart_page_sort_key,
            )

    @staticmethod
    def _log_summary(
        parents: list[dict],
    ) -> None:
        """Log final parent retrieval summary."""

        if not parents:
            logger.warning(
                "No parents found"
            )
            return

        top_parent = parents[0]

        logger.info(
            "Fetched {} parent chunks. "
            "Top parent: '{}' "
            "(score={:.4f}, pages={})",
            len(parents),
            top_parent.get(
                "title",
                "",
            ),
            top_parent.get(
                "best_child_score",
                0.0,
            ),
            top_parent.get(
                "matched_pages",
                [],
            ),
        )
