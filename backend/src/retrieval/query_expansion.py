"""
Query Expansion

melakukan ekspansi linguistik, memperluas akronim/singkatan akademik agar
matching FTS dan vector lebih konsisten.

Aturan:
- Akronim huruf kapital (PI, KKP, SKS, IPK, dst.) di-expand ke bentuk panjang
  HANYA kalau muncul dalam tulisan kapital. Ini menghindari false positive
  pada kata Indonesia umum (mis. "apa" tidak akan dianggap sebagai akronim
  "APA" / American Psychological Association).
- Bentuk panjang (case-insensitive) di-expand ke akronim agar matching FTS
  konsisten dua arah.
- Tidak ada angka, satuan, atau frasa jawaban yang ditambahkan.
"""

from __future__ import annotations

import re
from loguru import logger


# Akronim huruf kapital ke bentuk panjang. Match dilakukan case-sensitive
# pada bentuk uppercase utuh untuk menghindari false positive (mis. "Apa"
# bukan akronim "APA").
UPPERCASE_ACRONYMS: dict[str, list[str]] = {
    "PI": ["Penulisan Ilmiah"],
    "KKP": ["Kuliah Kerja Praktik", "Kuliah Kerja Praktek"],
    "TA": ["Tugas Akhir"],
    "SKS": ["Satuan Kredit Semester"],
    "IPK": ["Indeks Prestasi Kumulatif"],
    "KRS": ["Kartu Rencana Studi"],
    "BAAK": ["Biro Administrasi Akademik dan Kemahasiswaan"],
    "BAUK": ["Biro Administrasi Umum dan Keuangan"],
    "BKK": ["Bursa Kerja Khusus"],
    "EYD": ["Ejaan Yang Disempurnakan"],
}

# Bentuk panjang menjadi akronim. Match case-insensitive karena bentuk panjang
# tidak ambigu dengan kata umum.
LONG_FORM_TO_ACRONYM: dict[str, list[str]] = {
    "penulisan ilmiah": ["PI"],
    "kuliah kerja praktik": ["KKP"],
    "kuliah kerja praktek": ["KKP"],
    "tugas akhir": ["TA"],
    "satuan kredit semester": ["SKS"],
    "indeks prestasi kumulatif": ["IPK"],
    "kartu rencana studi": ["KRS"],
}

# Sinonim atau kata alternatif yang sering dipakai mahasiswa tapi punya istilah resmi.
SYNONYMS: dict[str, list[str]] = {
    "pendadaran": ["ujian skripsi", "sidang skripsi", "ujian tugas akhir", "seminar pendadaran"],
    "sidang": ["ujian skripsi", "pendadaran"],
    "pembimbing": ["dosen pembimbing"],
    "penguji": ["dosen penguji"],
}


def _has_uppercase_token(text: str, token: str) -> bool:
    """Cek apakah token (case-sensitive, uppercase) muncul sebagai kata utuh."""
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def _has_phrase(text_lower: str, phrase: str) -> bool:
    """Cek substring frasa di text yang sudah lowercase."""
    return phrase in text_lower


def expand_query(question: str) -> str:
    """
    Tambahkan bentuk panjang/pendek dari akronim akademik yang muncul di query.
    Tidak menambahkan kata kunci jawaban apa pun.
    """
    if not question:
        return question

    additions: list[str] = []
    text_lower = question.lower()

    # 1. Akronim uppercase ke bentuk panjang
    for acronym, expansions in UPPERCASE_ACRONYMS.items():
        if not _has_uppercase_token(question, acronym):
            continue
        for exp in expansions:
            if exp.lower() not in text_lower and exp not in additions:
                additions.append(exp)

    # 2. Bentuk panjang → akronim
    for phrase, expansions in LONG_FORM_TO_ACRONYM.items():
        if not _has_phrase(text_lower, phrase):
            continue
        for exp in expansions:
            if not _has_uppercase_token(question, exp) and exp not in additions:
                additions.append(exp)

    # 3. Sinonim / Istilah Alternatif
    for word, equivalents in SYNONYMS.items():
        # Match boundaries to avoid substring matching
        if re.search(rf"\b{word}\b", text_lower):
            for eq in equivalents:
                if eq.lower() not in text_lower and eq not in additions:
                    additions.append(eq)

    if not additions:
        return question

    expanded = f"{question} {' '.join(additions)}"
    logger.debug(
        f"Query expansion (acronym only): added {len(additions)} term(s): {additions}"
    )
    return expanded


def expand_query_smart(question: str, enable_expansion: bool = True) -> str:
    """Backward-compatible wrapper. Aman dipanggil dari HybridSearcher."""
    if not enable_expansion:
        return question
    return expand_query(question)
