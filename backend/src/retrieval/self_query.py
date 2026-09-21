"""Parse natural-language queries into semantic query + retrieval filters."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from loguru import logger

from config.settings import get_settings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_KEYWORDS_PATH = (
    _PROJECT_ROOT / "config" / "section_keywords.yaml"
)

SectionConfidence = Literal["low", "medium", "high"]

@dataclass
class ParsedQuery:
    """Result of parsing a natural-language retrieval query."""

    semantic_query: str
    filters: dict[str, str]
    original_query: str
    detected_source: str | None = None
    detected_section: str | None = None
    confidence: SectionConfidence = "medium"

def _load_section_keywords(
    path: Path = _KEYWORDS_PATH,
) -> dict[str, list[str]]:
    """
    Load section keywords from YAML.

    Keywords are normalized to lowercase and deduplicated
    within each section.
    """

    if not path.exists():
        logger.error(
            "Section keywords file not found: {}",
            path,
        )
        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = yaml.safe_load(file) or {}
    except Exception as exc:
        logger.error(
            "Failed to load section keywords from {}: {}",
            path,
            exc,
        )
        return {}

    if not isinstance(data, dict):
        logger.error(
            "Invalid section keywords format in {}: "
            "expected a mapping",
            path,
        )
        return {}

    normalized: dict[str, list[str]] = {}

    for section, keywords in data.items():
        if not isinstance(section, str):
            logger.warning(
                "Skipping non-string section name: {!r}",
                section,
            )
            continue

        if not isinstance(keywords, list):
            logger.warning(
                "Section '{}' has non-list value; skipping",
                section,
            )
            continue

        normalized[section] = _normalize_keywords(
            keywords
        )

    _warn_on_duplicate_keywords(normalized)

    logger.info(
        "Loaded section keywords from {}: "
        "{} sections, {} keywords total",
        path.name,
        len(normalized),
        sum(len(keywords) for keywords in normalized.values()),
    )

    return normalized


def _normalize_keywords(
    keywords: list,
) -> list[str]:
    """Normalize and deduplicate keywords within one section."""

    seen: set[str] = set()
    normalized: list[str] = []

    for keyword in keywords:
        if not isinstance(keyword, str):
            continue

        value = keyword.strip().lower()

        if not value or value in seen:
            continue

        seen.add(value)
        normalized.append(value)

    return normalized


def _warn_on_duplicate_keywords(
    mapping: dict[str, list[str]],
) -> None:
    """
    Warn when a keyword belongs to multiple sections.

    Overlapping keywords can make section filtering ambiguous.
    """

    keyword_to_sections: dict[str, list[str]] = {}

    for section, keywords in mapping.items():
        for keyword in keywords:
            keyword_to_sections.setdefault(
                keyword,
                [],
            ).append(section)

    duplicates = {
        keyword: sections
        for keyword, sections in keyword_to_sections.items()
        if len(sections) > 1
    }

    if not duplicates:
        return

    logger.warning(
        "{} keyword(s) appear in multiple sections "
        "(may cause classification ambiguity)",
        len(duplicates),
    )

    for keyword, sections in list(
        duplicates.items()
    )[:5]:
        logger.warning(
            "  '{}' → {}",
            keyword,
            sections,
        )


SECTION_KEYWORDS: dict[str, list[str]] = (
    _load_section_keywords()
)

_PI_KEYWORDS_INSENSITIVE = [
    "penulisan ilmiah",
    "penulisan imliah",
    "penelitian ilmiah",
    "laporan pi",
    "ujian pi",
    "seminar pi",
    "panduan pi",
    "sidang pi",
    "bimbingan pi",
    "alur pi",
    "syarat pi",
    "judul pi",
]

_PI_KEYWORDS_CASE_SENSITIVE = [
    "PI",
]

_KKP_KEYWORDS = [
    "kuliah kerja praktik",
    "kuliah kerja praktek",
    "kkp",
    "laporan kkp",
    "ujian kkp",
    "seminar kkp",
    "panduan kkp",
    "tempat kkp",
    "instansi kkp",
    "untuk kkp",
]

_NON_SKRIPSI_EXPLICIT_KEYWORDS = [
    "non skripsi",
    "non-skripsi",
    "nonskripsi",
    "tugas akhir non skripsi",
    "tugas akhir non-skripsi",
    "jalur non skripsi",
]

_NON_SKRIPSI_TRACK_KEYWORDS = [
    "jalur karya ilmiah",
    "karya ilmiah",
    "prosiding",
    "jalur profesional",
    "jalur pekerja profesional",
    "pekerja profesional",
    "it profesional",
    "jalur wirausaha",
    "wirausaha",
    "startup",
    "business model canvas",
    "jalur kelulusan alternatif",
]

_SKRIPSI_KEYWORDS = [
    "skripsi",
    "tugas akhir skripsi",
    "proposal skripsi",
    "untuk skripsi",
    "jalur skripsi",
    "panduan skripsi",
]

_SOURCE_PI = (
    "Panduan Penyusunan Penulisan Imliah (PI) Cetak"
)

_SOURCE_KKP = (
    "Panduan Penyusunan Kuliah Kerja Praktik (KKP) Cetak"
)

_SOURCE_SKRIPSI = (
    "Panduan Penulisan Tugas Akhir Skripsi - "
    "STMIK Widya Cipta Dharma (2024)"
)

_SOURCE_NON_SKRIPSI = (
    "Panduan Penulisan Tugas Akhir Non Skripsi - "
    "STMIK Widya Cipta Dharma (2024)"
)


def _matches_keyword(
    text: str,
    keyword: str,
) -> bool:
    """
    Match a keyword against text.

    Multi-word/hyphenated keywords use substring matching.
    Single words use word-boundary matching.
    """

    if " " in keyword or "-" in keyword:
        return keyword in text

    return re.search(
        rf"\b{re.escape(keyword)}\b",
        text,
    ) is not None


def _contains_any(
    text: str,
    keywords: list[str],
) -> bool:
    """Return True when at least one keyword matches."""

    return any(
        _matches_keyword(text, keyword)
        for keyword in keywords
    )

def _detect_source(
    query_lower: str,
    raw_query: str = "",
) -> str | None:
    """
    Detect the source filter from the query.

    Non-Skripsi is checked before Skripsi so that
    "non skripsi" does not accidentally match "skripsi".
    """

    is_non_skripsi_explicit = _contains_any(
        query_lower,
        _NON_SKRIPSI_EXPLICIT_KEYWORDS,
    )

    # Remove non-skripsi phrases before checking skripsi.
    skripsi_query = query_lower

    for keyword in _NON_SKRIPSI_EXPLICIT_KEYWORDS:
        skripsi_query = skripsi_query.replace(
            keyword,
            " ",
        )

    is_skripsi = _contains_any(
        skripsi_query,
        _SKRIPSI_KEYWORDS,
    )

    is_pi = (
        _contains_any(query_lower, _PI_KEYWORDS_INSENSITIVE)
        or (bool(raw_query) and _contains_any(raw_query, _PI_KEYWORDS_CASE_SENSITIVE))
    )

    is_kkp = _contains_any(
        query_lower,
        _KKP_KEYWORDS,
    )

    matched_sources: list[str] = []

    if is_pi:
        matched_sources.append(_SOURCE_PI)

    if is_kkp:
        matched_sources.append(_SOURCE_KKP)

    if is_skripsi:
        matched_sources.append(_SOURCE_SKRIPSI)

    if is_non_skripsi_explicit:
        matched_sources.append(_SOURCE_NON_SKRIPSI)

    # Only apply a source filter when the query identifies
    # exactly one domain.
    if len(matched_sources) == 1:
        return matched_sources[0]

    # Track names identify Non-Skripsi only when the query did not already
    # name another guide explicitly. This prevents phrases such as
    # "karya ilmiah pada skripsi" from overriding the explicit Skripsi domain.
    if not matched_sources and _contains_any(
        query_lower,
        _NON_SKRIPSI_TRACK_KEYWORDS,
    ):
        return _SOURCE_NON_SKRIPSI

    return None

def _detect_section(
    query_lower: str,
    min_matches_for_filter: int = 2,
) -> tuple[str | None, SectionConfidence]:
    """
    Detect the most likely section.

    A section filter is applied only when it has at least
    `min_matches_for_filter` matching keywords.
    """

    if not SECTION_KEYWORDS:
        return None, "low"

    matched_sections: list[tuple[str, int]] = []

    for section, keywords in SECTION_KEYWORDS.items():
        match_count = sum(
            1
            for keyword in keywords
            if _matches_keyword(
                query_lower,
                keyword,
            )
        )

        if match_count > 0:
            matched_sections.append(
                (section, match_count)
            )

    if not matched_sections:
        return None, "low"

    matched_sections.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    best_section, best_count = (
        matched_sections[0]
    )

    if best_count >= min_matches_for_filter:
        return best_section, "high"

    logger.debug(
        "Section '{}' matched only {} keyword(s); "
        "skipping section filter for broader coverage",
        best_section,
        best_count,
    )

    return None, "medium"


def _resolve_section_filter(
    section: str | None,
    source: str | None,
) -> str | None:
    """Return a section substring that is safe for the selected source.

    The retrieval RPC performs a substring match. A bare Roman numeral is
    therefore unsafe: ``BAB II`` also occurs at the beginning of ``BAB III``.
    Use the shortest source-specific prefix that still separates chapters.
    Skripsi also stores its front matter as individual labels such as
    ``Kata Pengantar`` and ``Daftar Isi``, so ``Front Matter`` is not applied
    to that source. A coarse filter is unsafe before a source is identified.
    """

    if section is None:
        return None

    source_independent_sections = {
        "Lampiran",
        "Surat Keputusan",
    }

    if section in source_independent_sections:
        return section

    filters_by_source = {
        _SOURCE_PI: {
            "Front Matter": "Front Matter",
            "BAB I": "BAB I >",
            "BAB II": "BAB II >",
            "BAB III": "BAB III >",
            "BAB IV": "BAB IV >",
            "BAB V": "BAB V >",
        },
        _SOURCE_KKP: {
            "Front Matter": "Front Matter",
            "BAB I": "BAB I >",
            "BAB II": "BAB II >",
            "BAB III": "BAB III >",
            "BAB IV": "BAB IV >",
            "BAB V": "BAB V >",
        },
        _SOURCE_SKRIPSI: {
            "BAB I": "BAB I Pendahuluan",
            "BAB II": "BAB II >",
            "BAB III": "BAB III >",
            "BAB IV": "BAB IV >",
            "BAB V": "BAB V >",
        },
        _SOURCE_NON_SKRIPSI: {
            "Front Matter": "Front Matter",
            "BAB I": "BAB I PENDAHULUAN",
            "BAB II": "BAB II KETENTUAN UMUM",
            "BAB III": "BAB III BENTUK TUGAS AKHIR NON SKRIPSI",
            "BAB IV": "BAB IV PENJELASAN SISTEMATIKA PENULISAN LAPORAN",
            "BAB V": "BAB V FORMAT DAN TATA CARA PENULISAN",
        },
    }

    return filters_by_source.get(source, {}).get(section)

def extract_query_components(
    query: str,
) -> ParsedQuery:
    """
    Parse a natural-language query into semantic query + filters.
    """

    logger.debug(
        "Analyzing query: '{}'",
        query,
    )

    query_lower = query.lower()

    source = _detect_source(
        query_lower,
        raw_query=query,
    )

    section, confidence = _detect_section(
        query_lower
    )
    section_filter = _resolve_section_filter(
        section,
        source,
    )

    filters: dict[str, str] = {}

    if source:
        filters["source"] = source

    if section_filter:
        filters["section"] = section_filter

    if section and not section_filter:
        logger.debug(
            "Detected section '{}' but skipped its SQL filter because "
            "the current source metadata is not compatible",
            section,
        )

    logger.info(
        "Query analyzed — semantic='{}' | "
        "filters={} | confidence={}",
        query,
        filters,
        confidence,
    )

    return ParsedQuery(
        semantic_query=query,
        filters=filters,
        original_query=query,
        detected_source=source,
        detected_section=section,
        confidence=confidence,
    )


def get_available_sections(
    source: Literal[
        "PI",
        "KKP",
        "SKRIPSI",
        "NON_SKRIPSI",
        "both",
        "all",
    ] = "all",
) -> dict[str, list[str]]:
    """Return section names and short descriptions, optionally filtered/customized by source."""

    full_catalog = {
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
            "Sistematika Penyusunan Laporan PI/KKP/Skripsi/Non-Skripsi",
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

    if source in ("all", "both") or not source:
        return full_catalog

    normalized_source = source.upper()

    # Deskripsi BAB II yang spesifik per jenis panduan
    _bab2_by_source: dict[str, list[str]] = {
        "PI": [
            "Ketentuan Dosen Pembimbing dan Penguji PI",
            "Syarat dan Prosedur Penulisan Ilmiah",
            "Proses Penyusunan dan Pengajuan Laporan PI",
            "Prosedur Ujian dan Tahap Akhir PI",
            "Sistem Penilaian dan Kelulusan",
        ],
        "KKP": [
            "Ketentuan Dosen Pembimbing KKP",
            "Syarat dan Tempat Pelaksanaan KKP",
            "Proses Penyusunan dan Pengajuan Laporan KKP",
            "Prosedur Ujian dan Tahap Akhir KKP",
            "Sistem Penilaian dan Kelulusan",
        ],
        "SKRIPSI": [
            "Ketentuan Dosen Pembimbing dan Penguji Skripsi",
            "Syarat Pengajuan dan Seminar Proposal",
            "Proses Penyusunan Skripsi",
            "Prosedur Pendadaran/Ujian Skripsi",
            "Sistem Penilaian dan Kelulusan",
        ],
        "NON_SKRIPSI": [
            "Ketentuan Dosen Pembimbing Tugas Akhir Non Skripsi",
            "Jalur Kelulusan Alternatif (Jurnal, Wirausaha, Profesional)",
            "Proses Penyusunan dan Pengajuan",
            "Prosedur Ujian dan Tahap Akhir",
            "Sistem Penilaian dan Kelulusan",
        ],
    }

    filtered: dict[str, list[str]] = {}

    for section, descriptions in full_catalog.items():
        if section == "BAB II":
            filtered[section] = _bab2_by_source.get(
                normalized_source, list(descriptions)
            )
        elif section == "BAB III":
            filtered[section] = [
                f"Sistematika Penyusunan Laporan Panduan {normalized_source}",
                "Gambaran Umum dan Struktur Laporan",
            ]
        else:
            filtered[section] = list(descriptions)

    return filtered


_stats_cache: dict[str, Any] = {}
_stats_lock = threading.Lock()


def get_metadata_statistics(supabase_client=None) -> dict[str, Any]:
    """
    Return metadata statistics for the current dataset.
    
    Queries live counts from `parent_documents` with a 300-second TTL cache,
    and falls back gracefully to default figures if the database is unavailable.
    """
    now = time.time()
    with _stats_lock:
        cached_data = _stats_cache.get("data")
        expires_at = _stats_cache.get("expires_at", 0)
        if cached_data is not None and now < expires_at:
            return cached_data

    settings = get_settings()

    # Coba query live dari database
    try:
        from supabase import create_client
        client = supabase_client or create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )
        response = (
            client.table("parent_documents")
            .select("domain")
            .execute()
        )

        if response.data:
            counts: dict[str, int] = {}
            for row in response.data:
                domain_val = (row.get("domain") or "UNKNOWN").upper()
                counts[domain_val] = counts.get(domain_val, 0) + 1

            data = {
                "sources": [
                    _SOURCE_PI,
                    _SOURCE_KKP,
                    _SOURCE_SKRIPSI,
                    _SOURCE_NON_SKRIPSI,
                ],
                "sections": list(SECTION_KEYWORDS.keys()),
                "pi_parent_chunks": counts.get("PI", 23),
                "kkp_parent_chunks": counts.get("KKP", 23),
                "skripsi_parent_chunks": counts.get("SKRIPSI", 48),
                "non_skripsi_parent_chunks": counts.get("NON_SKRIPSI", 81),
                "total_parent_chunks": len(response.data),
                "is_live": True,
            }

            with _stats_lock:
                _stats_cache["data"] = data
                _stats_cache["expires_at"] = now + 300

            return data

    except Exception as exc:
        logger.warning(
            "Gagal mengambil metadata statistics live dari database: {}. Menggunakan fallback.",
            exc,
        )

    # Fallback nilai statis jika DB tidak dapat diakses
    fallback_data = {
        "sources": [
            _SOURCE_PI,
            _SOURCE_KKP,
            _SOURCE_SKRIPSI,
            _SOURCE_NON_SKRIPSI,
        ],
        "sections": list(SECTION_KEYWORDS.keys()),
        "pi_parent_chunks": 23,
        "kkp_parent_chunks": 23,
        "skripsi_parent_chunks": 48,
        "non_skripsi_parent_chunks": 81,
        "total_parent_chunks": 175,
        "is_live": False,
    }

    with _stats_lock:
        _stats_cache["data"] = fallback_data
        _stats_cache["expires_at"] = now + 300

    return fallback_data
