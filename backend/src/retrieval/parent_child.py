from __future__ import annotations

import time
from supabase import create_client, Client
from loguru import logger

from config.settings import get_settings

from src.retrieval.hybrid_search import HybridSearchResult


class ParentChildFetcher:

    def __init__(self, supabase_client: Client | None = None):
        settings = get_settings()
        self._supabase = supabase_client or create_client(
            settings.supabase_url, settings.supabase_service_key
        )
        self._parent_table = settings.table_parent_chunks

    def fetch_parents(self, search_results: list[HybridSearchResult]) -> list[dict]:
        if not search_results:
            logger.warning("No search results to fetch parent")
            return []

        parent_scores: dict[str, dict] = {}
        for result in search_results:
            pid = result.parent_id
            if not pid:
                logger.warning(f"Child '{result.child_id}' has no parent_id")
                continue

            score = result.hybrid_score

            if pid not in parent_scores:
                parent_scores[pid] = {
                    "best_score": score,
                    "matched_children": [result.child_id],
                }
            else:
                parent_scores[pid]["best_score"] = max(
                    parent_scores[pid]["best_score"], score
                )
                parent_scores[pid]["matched_children"].append(result.child_id)

        unique_parent_ids = list(parent_scores.keys())
        logger.info(
            f"De-duplikasi: {len(search_results)} children → "
            f"{len(unique_parent_ids)} unique parents"
        )

        t0 = time.time()
        response = (
            self._supabase.table(self._parent_table)
            .select("*")
            .in_("parent_id", unique_parent_ids)
            .execute()
        )
        t_fetch = time.time() - t0
        logger.info(f"  [Profile] Supabase Parent Fetch: {t_fetch:.2f}s")

        parents = response.data or []

        if len(parents) != len(unique_parent_ids):
            found_ids = {p["parent_id"] for p in parents}
            missing = set(unique_parent_ids) - found_ids
            logger.warning(f"Parent IDs not found in DB: {missing}")

        # Kumpulkan semua child_id yang cocok untuk query halaman
        all_matched_child_ids = []
        for info in parent_scores.values():
            all_matched_child_ids.extend(info.get("matched_children", []))

        # Ambil data halaman dari child_documents yang cocok
        child_pages_map: dict[str, list[int]] = {}
        if all_matched_child_ids:
            try:
                settings = get_settings()
                child_resp = (
                    self._supabase.table(settings.table_child_chunks)
                    .select("id, parent_id, pages")
                    .in_("id", all_matched_child_ids)
                    .execute()
                )
                for child_row in (child_resp.data or []):
                    pid = child_row.get("parent_id", "")
                    pages = child_row.get("pages") or []
                    if pid and pages:
                        if pid not in child_pages_map:
                            child_pages_map[pid] = []
                        child_pages_map[pid].extend(pages)
            except Exception as e:
                logger.warning(f"Gagal mengambil data halaman child: {e}")

        for parent in parents:
            pid = parent["parent_id"]
            info = parent_scores.get(pid, {})
            parent["best_child_score"] = info.get("best_score", 0.0)
            parent["matched_children"] = info.get("matched_children", [])
            # Ambil halaman pertama (terkecil) dari child yang cocok
            pages = sorted(set(child_pages_map.get(pid, [])))
            parent["matched_pages"] = pages

        parents.sort(key=lambda x: x["best_child_score"], reverse=True)

        if parents:
            logger.info(
                f"Fetched {len(parents)} parent chunks. "
                f"Top parent: '{parents[0]['title']}' "
                f"(score={parents[0]['best_child_score']:.4f}, "
                f"pages={parents[0].get('matched_pages', [])})"
            )
        else:
            logger.warning("No parents found")

        return parents