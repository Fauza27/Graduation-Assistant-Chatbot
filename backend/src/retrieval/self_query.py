"""
Self-query parser: ekstrak filter (source, section) dari pertanyaan natural.

Keyword section dimuat dari file YAML eksternal (`config/section_keywords.yaml`)
agar mudah dimaintain tanpa menyentuh logic. Saat load, sistem akan memberi
warning kalau ada keyword yang muncul di lebih dari satu section (rawan
salah klasifikasi).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger

from config.settings import get_settings


# Lokasi file keyword. Di-load sekali saat modul di-import.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_KEYWORDS_PATH = _PROJECT_ROOT / "config" / "section_keywords.yaml"


@dataclass
class ParsedQuery:
    semantic_query: str
    filters: dict
    original_query: str
    detected_source: str | None = None
    detected_section: str | None = None
    confidence: str = "medium"  # low, medium, high


# ──────────────────────────────────────────────────────────────────────
# Keyword loading
# ──────────────────────────────────────────────────────────────────────

def _load_section_keywords(path: Path = _KEYWORDS_PATH) -> dict[str, list[str]]:
    """Load mapping section → keywords dari YAML, normalize ke lowercase."""
    if not path.exists():
        logger.error(f"Section keywords file not found: {path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        logger.error(f"Invalid format in {path}: expected mapping at top level")
        return {}

    normalized: dict[str, list[str]] = {}
    for section, keywords in data.items():
        if not isinstance(keywords, list):
            logger.warning(f"Section '{section}' has non-list value, skipping")
            continue
        # Normalize: lowercase + strip + dedupe within section
        seen: set[str] = set()
        cleaned: list[str] = []
        for kw in keywords:
            if not isinstance(kw, str):
                continue
            kw_norm = kw.strip().lower()
            if kw_norm and kw_norm not in seen:
                seen.add(kw_norm)
                cleaned.append(kw_norm)
        normalized[section] = cleaned

    _warn_on_duplicate_keywords(normalized)
    logger.info(
        f"Loaded section keywords from {path.name}: "
        f"{len(normalized)} sections, "
        f"{sum(len(v) for v in normalized.values())} keywords total"
    )
    return normalized


def _warn_on_duplicate_keywords(mapping: dict[str, list[str]]) -> None:
    """Warn jika satu keyword muncul di >1 section."""
    keyword_to_sections: dict[str, list[str]] = {}
    for section, keywords in mapping.items():
        for kw in keywords:
            keyword_to_sections.setdefault(kw, []).append(section)

    duplicates = {kw: secs for kw, secs in keyword_to_sections.items() if len(secs) > 1}
    if duplicates:
        logger.warning(
            f"⚠️ {len(duplicates)} keyword(s) appear in multiple sections "
            f"(may cause classification ambiguity)"
        )
        # Tampilkan beberapa contoh untuk debugging tanpa membanjiri log.
        for kw, secs in list(duplicates.items())[:5]:
            logger.warning(f"   '{kw}' → {secs}")


SECTION_KEYWORDS: dict[str, list[str]] = _load_section_keywords()


# ──────────────────────────────────────────────────────────────────────
# Source detection (PI vs KKP)
# ──────────────────────────────────────────────────────────────────────

# Keyword yang menandai pertanyaan tentang PI atau KKP. Hanya berisi term
# linguistik, tidak ada angka/jawaban.
_PI_KEYWORDS = [
    "penulisan ilmiah",
    "penelitian ilmiah",
    " pi ",
    "laporan pi",
    "ujian pi",
    "seminar pi",
    "panduan pi",
    "untuk pi",
]

_KKP_KEYWORDS = [
    "kuliah kerja praktik",
    "kuliah kerja praktek",
    " kkp ",
    "laporan kkp",
    "ujian kkp",
    "seminar kkp",
    "panduan kkp",
    "tempat kkp",
    "instansi kkp",
    "untuk kkp",
]

_SOURCE_PI = "Panduan Penyusunan Penulisan Imliah (PI) Cetak"
_SOURCE_KKP = "Panduan Penyusunan Kuliah Kerja Praktik (KKP) Cetak"


def _detect_source(query_lower: str) -> str | None:
    """Tentukan source filter berdasarkan keyword query."""
    is_pi = any(kw in query_lower for kw in _PI_KEYWORDS)
    is_kkp = any(kw in query_lower for kw in _KKP_KEYWORDS)

    if is_pi and not is_kkp:
        return _SOURCE_PI
    if is_kkp and not is_pi:
        return _SOURCE_KKP
    return None


# ──────────────────────────────────────────────────────────────────────
# Section detection
# ──────────────────────────────────────────────────────────────────────

def _matches_keyword(text: str, keyword: str) -> bool:
    """
    Match keyword di text:
    - Multi-word: substring match
    - Single word: word boundary match
    """
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _detect_section(
    query_lower: str,
    min_matches_for_filter: int = 2,
) -> tuple[str | None, str]:
    """
    Tentukan section filter. Return (section_or_none, confidence).

    Filter hanya diterapkan kalau minimal `min_matches_for_filter` keyword
    cocok (default 2). Kalau hanya 1, kembalikan None agar pencarian tetap
    luas.
    """
    if not SECTION_KEYWORDS:
        return None, "low"

    matched: list[tuple[str, int]] = []
    for section, keywords in SECTION_KEYWORDS.items():
        n = sum(1 for kw in keywords if _matches_keyword(query_lower, kw))
        if n > 0:
            matched.append((section, n))

    if not matched:
        return None, "low"

    matched.sort(key=lambda x: x[1], reverse=True)
    best_section, best_count = matched[0]

    if best_count >= min_matches_for_filter:
        return best_section, "high"

    logger.debug(
        f"Section '{best_section}' matched only {best_count} keyword "
        f"(< {min_matches_for_filter}), skipping section filter for broader coverage"
    )
    return None, "low"


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def extract_query_components(query: str) -> ParsedQuery:
    """Parse query natural → ParsedQuery dengan filter (source, section)."""
    logger.debug(f"Menganalisis query: '{query}'")

    query_lower = query.lower()
    filters: dict = {}

    source = _detect_source(query_lower)
    if source:
        filters["source"] = source

    section, confidence = _detect_section(query_lower)
    if section:
        filters["section"] = section

    logger.info(
        f"Query dianalisis — semantic: '{query}' | "
        f"filters: {filters} | confidence: {confidence}"
    )

    return ParsedQuery(
        semantic_query=query,
        filters=filters,
        original_query=query,
        detected_source=filters.get("source"),
        detected_section=filters.get("section"),
        confidence=confidence,
    )


# ──────────────────────────────────────────────────────────────────────
# Metadata helpers (untuk dokumentasi/debugging)
# ──────────────────────────────────────────────────────────────────────

def get_available_sections(
    source: Literal["PI", "KKP", "both"] = "both",
) -> dict[str, list[str]]:
    """Daftar section dan deskripsi singkat (untuk dokumentasi)."""
    return {
        "Front Matter": [
            "Kata Pengantar",
            "Daftar Isi, Daftar Tabel, Daftar Gambar",
        ],
        "Surat Keputusan": [
            "SK Pemberlakuan Panduan dari Ketua STMIK",
        ],
        "BAB I": [
            "Pendahuluan: Latar Belakang dan Tujuan Panduan",
        ],
        "BAB II": [
            "Ketentuan Dosen Pembimbing dan Penguji",
            "Hak dan Mekanisme Mahasiswa Bimbingan",
            "Syarat dan Tempat Penelitian/KKP",
            "Proses Penyusunan dan Pengajuan",
            "Prosedur Ujian dan Tahap Akhir",
            "Sistem Penilaian dan Kelulusan",
        ],
        "BAB III": [
            "Sistematika Penyusunan Laporan PI/KKP",
            "Gambaran Umum dan Struktur Laporan",
        ],
        "BAB IV": [
            "Penjelasan Bagian Awal (Sampul, Pengesahan, Abstrak, Kata Pengantar)",
            "Penjelasan Bagian Utama (BAB I-V)",
            "Penjelasan Bagian Akhir (Daftar Pustaka, Lampiran)",
        ],
        "BAB V": [
            "Format Penulisan Naskah (Kertas, Margin, Huruf, Spasi)",
            "Aturan Tabel dan Gambar",
            "Bahasa dan Huruf Miring",
            "Daftar Pustaka (APA Style)",
        ],
        "Lampiran": [
            "Contoh Halaman Awal",
            "Contoh Daftar (Isi, Tabel, Gambar, Pustaka)",
            "Form Jadwal dan Bimbingan",
            "Form Administrasi Ujian",
            "Form Persetujuan dan Perbaikan",
            "Form Berita Acara dan Penilaian",
            "Form Perubahan Pembimbing/Judul",
        ],
    }


def get_metadata_statistics() -> dict:
    """Statistik metadata untuk dokumentasi/debugging."""
    return {
        "sources": [_SOURCE_PI, _SOURCE_KKP],
        "sections": list(SECTION_KEYWORDS.keys()),
        "pi_parent_chunks": 23,
        "kkp_parent_chunks": 23,
        "total_parent_chunks": 46,
    }
