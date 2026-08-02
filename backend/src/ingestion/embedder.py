import time
from openai import OpenAI
from supabase import create_client, Client
from loguru import logger
from tqdm import tqdm

from config.settings import get_settings


def _get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.open_api_key)


def get_openai_embeddings(
    texts: list[str],
    model: str | None = None,
    batch_size: int = 20,
) -> list[list[float]]:
    settings = get_settings()
    client = _get_openai_client()
    model = model or settings.embedding_model

    all_embeddings = []

    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
        batch = texts[i : i + batch_size]

        response = client.embeddings.create(
            model=model,
            input=batch,
            dimensions=2000,
        )

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

        if i + batch_size < len(texts):
            time.sleep(0.5)

    logger.info(
        f"Generated {len(all_embeddings)} embeddings "
        f"(dim={len(all_embeddings[0]) if all_embeddings else 0})"
    )
    return all_embeddings


def _build_metadata_json(child: dict) -> dict:
    return {
        "parent_id": child.get("parent_id", ""),
        "title": child.get("title", ""),
        "section": child.get("section", ""),
        "pages": child.get("pages", []),
        "source": child.get("source", ""),
    }


def upsert_parent_chunks(parents: list[dict]) -> int:
    supabase = _get_supabase_client()
    settings = get_settings()
    table = settings.table_parent_chunks

    existing = supabase.table(table).select("parent_id").execute()
    existing_ids = {row["parent_id"] for row in existing.data}

    new_parents = [p for p in parents if p["parent_id"] not in existing_ids]

    if not new_parents:
        logger.info("all parent chunks already exists in database, skip.")
        return 0

    rows = []
    for p in new_parents:
        rows.append({
            "parent_id": p["parent_id"],
            "title": p["title"],
            "content": p["content"],
            "section": p["section"],
            "child_ids": p["child_ids"],
        })

    supabase.table(table).insert(rows).execute()
    logger.info(f"Inserted {len(rows)} parent chunks to '{table}'")
    return len(rows)


def upsert_child_chunks_with_embeddings(
    children: list[dict],
    embeddings: list[list[float]],
    child_to_parent_map: dict[str, str],
) -> int:
    if len(children) != len(embeddings):
        raise ValueError(
            f"Number of children ({len(children)}) != number of embeddings ({len(embeddings)})"
        )

    supabase = _get_supabase_client()
    settings = get_settings()
    table = settings.table_child_chunks

    existing = supabase.table(table).select("id").execute()
    existing_ids = {row["id"] for row in existing.data}

    new_indices = [
        i for i, c in enumerate(children)
        if c["id"] not in existing_ids
    ]

    if not new_indices:
        logger.info("all child chunks already exists in database, skip.")
        return 0

    batch_size = 20
    total_inserted = 0

    for batch_start in tqdm(
        range(0, len(new_indices), batch_size),
        desc="Inserting child chunks"
    ):
        batch_indices = new_indices[batch_start : batch_start + batch_size]
        rows = []

        for idx in batch_indices:
            child = children[idx]
            embedding = embeddings[idx]
            parent_id = child_to_parent_map.get(child["id"], "")

            child_with_parent = {**child, "parent_id": parent_id}
            metadata = _build_metadata_json(child_with_parent)

            rows.append({
                "id": child["id"],
                "parent_id": parent_id,
                "title": child["title"],
                "content": child["content"],
                "section": child["section"],
                "pages": child.get("pages", []),
                "source": child.get("source", ""),
                "metadata": metadata,
                "embedding": embedding,
            })

        supabase.table(table).insert(rows).execute()
        total_inserted += len(rows)

    logger.info(f"Inserted {total_inserted} child chunks ke '{table}'")
    return total_inserted


def build_child_to_parent_map(parents: list[dict]) -> dict[str, str]:
    mapping = {}
    for parent in parents:
        for child_id in parent["child_ids"]:
            mapping[child_id] = parent["parent_id"]
    return mapping


def run_ingestion(
    child_chunks_path: str,
    parent_chunks_path: str,
) -> dict:
    from src.ingestion.loader import (
        load_child_chunks,
        load_parent_chunks,
        validate_parent_child_links,
    )

    # 1. Load data
    logger.info("=" * 60)
    logger.info("STEP 1: Loading chunks from JSON...")
    children = load_child_chunks(child_chunks_path)
    parents = load_parent_chunks(parent_chunks_path)
    validate_parent_child_links(parents, children)

    # 2. Build mapping child → parent
    child_to_parent_map = build_child_to_parent_map(parents)

    # 3. Embed child chunks
    logger.info("=" * 60)
    logger.info("STEP 2: Generating embeddings untuk child chunks...")
    child_texts = [c["content"] for c in children]
    embeddings = get_openai_embeddings(child_texts)

    # 4. Upsert parent chunks
    logger.info("=" * 60)
    logger.info("STEP 3: Upsert parent chunks to Supabase...")
    n_parents = upsert_parent_chunks(parents)

    # 5. Upsert child chunks + embeddings
    logger.info("=" * 60)
    logger.info("STEP 4: Upsert child chunks + embeddings to Supabase...")
    n_children = upsert_child_chunks_with_embeddings(
        children, embeddings, child_to_parent_map
    )

    stats = {
        "total_parents": len(parents),
        "total_children": len(children),
        "new_parents_inserted": n_parents,
        "new_children_inserted": n_children,
        "embedding_dimension": len(embeddings[0]) if embeddings else 0,
    }

    logger.info("=" * 60)
    logger.info(f"Ingestion completed: {stats}")
    return stats