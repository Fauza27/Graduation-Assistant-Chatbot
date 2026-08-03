"""
Utilitas untuk deteksi tipe panduan (PI vs KKP) dari metadata dokumen.

Strategi deteksi diurutkan dari yang paling reliable ke yang paling fragile:
1. Field `source` (string nama file panduan) — paling reliable, selalu terisi
   saat ingestion.
2. Prefix `parent_id` atau `id` — `parent-kkp-*` / `kkp-*` → KKP. Selain itu
   diasumsikan PI (parent PI: `parent-NNN`, child PI: `pi-NNN`).
"""

from __future__ import annotations

from typing import Literal, Mapping

PanduanType = Literal["PI", "KKP", "SKRIPSI", "NON_SKRIPSI"]


def detect_panduan_type(meta: Mapping | None) -> PanduanType:
    """
    Deteksi tipe panduan dari metadata sumber.

    `meta` boleh dict (parent doc, child metadata, source dict) yang
    mengandung salah satu dari: `source`, `parent_id`, `id`. Kalau tidak ada
    yang reliable, fallback ke "PI" (lebih banyak chunk PI di dataset).
    """
    if not meta:
        return "PI"

    # 1. Pakai field `source` kalau ada.
    source = (meta.get("source") or "").lower()
    if source:
        if "non-skripsi" in source or "non skripsi" in source:
            return "NON_SKRIPSI"
        if "skripsi" in source:
            return "SKRIPSI"
        if "kkp" in source or "kuliah kerja" in source:
            return "KKP"
        if "pi" in source or "penulisan ilmiah" in source or "penulisan imliah" in source:
            return "PI"

    # 2. Pakai prefix ID. Cek parent_id dulu, lalu id.
    pid = (meta.get("parent_id") or meta.get("id") or "").lower()
    if pid.startswith("parent-non-skripsi") or pid.startswith("non-skripsi-"):
        return "NON_SKRIPSI"
    if pid.startswith("parent-skripsi") or pid.startswith("skripsi-"):
        return "SKRIPSI"
    if pid.startswith("parent-kkp-") or pid.startswith("kkp-"):
        return "KKP"
    if pid.startswith("parent-") or pid.startswith("pi-"):
        return "PI"

    return "PI"
