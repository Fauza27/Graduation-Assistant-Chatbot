"""Utilities for detecting academic guide type from document metadata."""

from __future__ import annotations

from typing import Literal, Mapping


PanduanType = Literal[
    "PI",
    "KKP",
    "SKRIPSI",
    "NON_SKRIPSI",
]


def detect_panduan_type(
    meta: Mapping | None,
) -> PanduanType:
    """
    Detect the academic guide type from document metadata.

    Detection priority:
        1. domain
        2. source
        3. parent_id / id
        4. PI fallback
    """

    if not meta:
        return "PI"

    # Explicit domain field
    domain = str(
        meta.get("domain") or ""
    ).upper().strip()

    if domain in {
        "PI",
        "KKP",
        "SKRIPSI",
        "NON_SKRIPSI",
    }:
        return domain 

    # Source name
    source = str(
        meta.get("source") or ""
    ).lower()

    if source:
        if (
            "non-skripsi" in source
            or "non skripsi" in source
        ):
            return "NON_SKRIPSI"

        if "skripsi" in source:
            return "SKRIPSI"

        if (
            "kkp" in source
            or "kuliah kerja" in source
        ):
            return "KKP"

        if (
            "pi" in source
            or "penulisan ilmiah" in source
            or "penulisan imliah" in source
        ):
            return "PI"

    # ID prefix
    identifier = str(
        meta.get("parent_id")
        or meta.get("id")
        or ""
    ).lower()

    normalized_id = identifier.replace("_", "-")

    if (
        normalized_id.startswith("parent-non-skripsi")
        or normalized_id.startswith("non-skripsi-")
    ):
        return "NON_SKRIPSI"

    if (
        normalized_id.startswith("parent-skripsi")
        or normalized_id.startswith("skripsi-")
    ):
        return "SKRIPSI"

    if (
        normalized_id.startswith("parent-kkp")
        or normalized_id.startswith("kkp-")
    ):
        return "KKP"

    if (
        normalized_id.startswith("parent-pi")
        or normalized_id.startswith("pi-")
        or normalized_id.startswith("parent-")
    ):
        return "PI"

    return "PI"