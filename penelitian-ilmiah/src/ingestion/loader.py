import json
from pathlib import Path
from loguru import logger


def load_child_chunks(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Child chunks file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Child chunks must be JSON array")

    required_fields = {"id", "title", "content", "section"}
    for i, chunk in enumerate(data):
        missing = required_fields - set(chunk.keys())
        if missing:
            raise ValueError(
                f"Child chunk index {i} (id={chunk.get('id', '?')}) "
                f"missing fields: {missing}"
            )

    ids = [c["id"] for c in data]
    if len(ids) != len(set(ids)):
        duplicates = [x for x in ids if ids.count(x) > 1]
        raise ValueError(f"Duplicate child chunk IDs: {set(duplicates)}")

    logger.info(f"Loaded {len(data)} child chunks dari {path.name}")
    return data


def load_parent_chunks(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Parent chunks file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Parent chunks must be JSON array")

    required_fields = {"parent_id", "title", "content", "section", "child_ids"}
    for i, chunk in enumerate(data):
        missing = required_fields - set(chunk.keys())
        if missing:
            raise ValueError(
                f"Parent chunk index {i} (id={chunk.get('parent_id', '?')}) "
                f"missing fields: {missing}"
            )

    ids = [c["parent_id"] for c in data]
    if len(ids) != len(set(ids)):
        duplicates = [x for x in ids if ids.count(x) > 1]
        raise ValueError(f"Duplicate parent chunk IDs: {set(duplicates)}")

    logger.info(f"Loaded {len(data)} parent chunks from {path.name}")
    return data


def validate_parent_child_links(
    parents: list[dict], children: list[dict]
) -> bool:
    child_ids_set = {c["id"] for c in children}

    for parent in parents:
        for cid in parent["child_ids"]:
            if cid not in child_ids_set:
                raise ValueError(
                    f"Parent '{parent['parent_id']}' refers to child '{cid}' "
                    f"which does not exist in child chunks"
                )

    child_to_parent = {}
    for parent in parents:
        for cid in parent["child_ids"]:
            child_to_parent[cid] = parent["parent_id"]

    orphan_children = child_ids_set - set(child_to_parent.keys())
    if orphan_children:
        logger.warning(
            f"Child chunks without parent: {orphan_children}. "
            f"They will not be able to fetch their parent."
        )

    logger.info(
        f"Validation OK: {len(parents)} parents, {len(children)} children, "
        f"{len(child_to_parent)} links valid"
    )
    return True