"""Publish rebuilt PI/KKP chunks and fresh embeddings to Supabase.

The default invocation is local and read-only. ``--apply`` performs network
calls and requires migration ``2026091601_chunk_quality.sql`` to be installed.
Each parent and its existing children are replaced atomically by a database RPC.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from scripts.database.rebuild_lossless_pi_kkp_chunks import (
    KKP_SPEC,
    PI_SPEC,
    _load_json,
    rebuild,
)


CHUNKING_VERSION = "lossless-v2-20260920"
MIGRATION_VERSION = "2026091601"
EMBEDDING_DIMENSIONS = 2000


def _load_payload() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for spec in (PI_SPEC, KKP_SPEC):
        rebuilt_parents, rebuilt_children, _ = rebuild(spec)
        if rebuilt_parents != _load_json(spec.parent_path):
            raise ValueError(f"{spec.name}: parent export is not reproducible")
        if rebuilt_children != _load_json(spec.child_path):
            raise ValueError(f"{spec.name}: child export is not reproducible")
        parents.extend(
            {**parent, "domain": spec.name}
            for parent in rebuilt_parents
        )
        children.extend(rebuilt_children)
    return parents, children


def _content_checksum(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(str(row.get("id") or row.get("parent_id")).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(row.get("content") or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _create_embeddings(
    children: list[dict[str, Any]],
    batch_size: int,
) -> dict[str, list[float]]:
    from langchain_openai import OpenAIEmbeddings

    from src.monitoring.openai_client import build_instrumented_http_client

    settings = get_settings()
    embedder = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.open_api_key,
        dimensions=EMBEDDING_DIMENSIONS,
        http_client=build_instrumented_http_client(),
    )
    embeddings: dict[str, list[float]] = {}
    for start in range(0, len(children), batch_size):
        batch = children[start : start + batch_size]
        vectors = embedder.embed_documents([child["content"] for child in batch])
        for child, vector in zip(batch, vectors):
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Embedding {child['id']} has {len(vector)} dimensions"
                )
            embeddings[str(child["id"])] = vector
        print(f"Embedded {min(start + len(batch), len(children))}/{len(children)} children")
    return embeddings


def _database_preflight(client: Any, parents: list[dict], children: list[dict]) -> None:
    migration_rows = (
        client.table("app_schema_migrations")
        .select("version")
        .eq("version", MIGRATION_VERSION)
        .execute()
        .data
        or []
    )
    if not migration_rows:
        raise ValueError(
            f"Database migration {MIGRATION_VERSION} has not been applied"
        )

    expected_parent_ids = {str(parent["parent_id"]) for parent in parents}
    expected_child_ids = {str(child["id"]) for child in children}
    db_parents = (
        client.table("parent_documents")
        .select("parent_id")
        .in_("domain", ["PI", "KKP"])
        .execute()
        .data
        or []
    )
    db_children = (
        client.table("child_documents")
        .select("id,embedding_status")
        .in_("domain", ["PI", "KKP"])
        .execute()
        .data
        or []
    )
    actual_parent_ids = {str(row["parent_id"]) for row in db_parents}
    actual_child_ids = {str(row["id"]) for row in db_children}
    if actual_parent_ids != expected_parent_ids:
        raise ValueError(
            "Database parent IDs differ from exports: "
            f"missing={sorted(expected_parent_ids - actual_parent_ids)}, "
            f"extra={sorted(actual_parent_ids - expected_parent_ids)}"
        )
    if actual_child_ids != expected_child_ids:
        raise ValueError(
            "Database child IDs differ from exports: "
            f"missing={sorted(expected_child_ids - actual_child_ids)}, "
            f"extra={sorted(actual_child_ids - expected_child_ids)}"
        )
    unfinished = sorted(
        str(row["id"])
        for row in db_children
        if row.get("embedding_status") != "success"
    )
    if unfinished:
        raise ValueError(
            "Resolve unfinished chunk edits or embeddings before publishing: "
            f"{unfinished}"
        )


def _publish(
    client: Any,
    parents: list[dict[str, Any]],
    children: list[dict[str, Any]],
    embeddings: dict[str, list[float]],
) -> None:
    children_by_id = {str(child["id"]): child for child in children}
    domain_sequence: dict[str, int] = {}
    for parent_index, parent in enumerate(parents, start=1):
        parent_payload = dict(parent)
        domain = str(parent["domain"])
        domain_sequence[domain] = domain_sequence.get(domain, 0) + 1
        parent_payload["sequence_no"] = domain_sequence[domain]
        child_payloads = []
        for child_id in parent["child_ids"]:
            child = dict(children_by_id[str(child_id)])
            child["sequence_no"] = len(child_payloads) + 1
            child["embedding"] = json.dumps(
                embeddings[str(child_id)],
                separators=(",", ":"),
            )
            child_payloads.append(child)

        result = client.rpc(
            "replace_knowledge_parent_chunks",
            {
                "p_parent": parent_payload,
                "p_children": child_payloads,
                "p_chunking_version": CHUNKING_VERSION,
            },
        ).execute().data
        print(
            f"Published {parent_index}/{len(parents)}: "
            f"{parent['parent_id']} ({result})"
        )


def _verify_database(client: Any, parents: list[dict], children: list[dict]) -> dict:
    expected_parents = {str(row["parent_id"]): row for row in parents}
    expected_children = {str(row["id"]): row for row in children}
    db_parents = (
        client.table("parent_documents")
        .select("parent_id,content,chunking_version")
        .in_("domain", ["PI", "KKP"])
        .execute()
        .data
        or []
    )
    db_children = (
        client.table("child_documents")
        .select(
            "id,content,section,metadata,embedding_status,chunking_version,embedding"
        )
        .in_("domain", ["PI", "KKP"])
        .execute()
        .data
        or []
    )

    parent_mismatches = [
        row["parent_id"]
        for row in db_parents
        if row.get("content") != expected_parents[row["parent_id"]]["content"]
        or row.get("chunking_version") != CHUNKING_VERSION
    ]
    child_mismatches = [
        row["id"]
        for row in db_children
        if row.get("content") != expected_children[row["id"]]["content"]
        or row.get("section") != expected_children[row["id"]]["section"]
        or (row.get("metadata") or {}).get("section") != row.get("section")
        or row.get("embedding_status") != "success"
        or row.get("chunking_version") != CHUNKING_VERSION
        or row.get("embedding") is None
    ]
    if parent_mismatches or child_mismatches:
        raise ValueError(
            f"Post-publish verification failed: parents={parent_mismatches}, "
            f"children={child_mismatches}"
        )
    return {
        "parents": len(db_parents),
        "children": len(db_children),
        "chunking_version": CHUNKING_VERSION,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create embeddings and publish to the configured Supabase project.",
    )
    parser.add_argument(
        "--check-database",
        action="store_true",
        help="Validate migration, IDs, and edit status without changing data.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 128:
        raise ValueError("batch-size must be between 1 and 128")

    parents, children = _load_payload()
    plan = {
        "apply": args.apply,
        "check_database": args.check_database,
        "chunking_version": CHUNKING_VERSION,
        "parents": len(parents),
        "children": len(children),
        "parent_checksum": _content_checksum(parents),
        "child_checksum": _content_checksum(children),
    }
    print(json.dumps(plan, indent=2))
    if not args.apply and not args.check_database:
        return

    from supabase import create_client

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_key)
    _database_preflight(client, parents, children)
    print("Database preflight passed")
    if not args.apply:
        return
    embeddings = _create_embeddings(children, args.batch_size)
    _publish(client, parents, children, embeddings)
    print(json.dumps(_verify_database(client, parents, children), indent=2))


if __name__ == "__main__":
    main()
