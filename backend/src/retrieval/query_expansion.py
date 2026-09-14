"""
Query Expansion

Melakukan ekspansi linguistik untuk query lexical/FTS. Query semantic untuk
vector search tetap menggunakan bentuk query dari QueryPlan tanpa expansion.

Aturan:
- Akronim yang TIDAK ambigu (SKS, IPK, KRS, KKP, BAAK, BAUK, BKK, EYD)
  di-match case-insensitive dengan word boundary — sehingga input casual
  seperti "sks", "ipk" tetap ter-expand.
- Akronim yang AMBIGU (PI, TA) di-match case-sensitive uppercase-only,
  karena "pi" dan "ta" terlalu umum sebagai kata/partikel Indonesia.
- Bentuk panjang (case-insensitive) di-expand ke akronim agar matching FTS
  konsisten dua arah.
- Tidak ada angka, satuan, atau frasa jawaban yang ditambahkan.
"""

from __future__ import annotations

import re
from loguru import logger


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

# Akronim yang aman untuk di-match case-insensitive (tidak ambigu dengan kata Indonesia umum).
SAFE_ACRONYMS: set[str] = {"SKS", "IPK", "KRS", "KKP", "BAAK", "BAUK", "BKK", "EYD"}

# Akronim yang HARUS di-match case-sensitive uppercase-only, karena versi lowercase-nya terlalu umum ("pi" = partikel, "ta" = kata ganti).
AMBIGUOUS_ACRONYMS: set[str] = {"PI", "TA"}

# Bentuk panjang menjadi akronim. Match case-insensitive karena bentuk panjang tidak ambigu dengan kata umum. Lengkap bidirectional untuk semua akronim.
LONG_FORM_TO_ACRONYM: dict[str, list[str]] = {
    "penulisan ilmiah": ["PI"],
    "kuliah kerja praktik": ["KKP"],
    "kuliah kerja praktek": ["KKP"],
    "tugas akhir": ["TA"],
    "satuan kredit semester": ["SKS"],
    "indeks prestasi kumulatif": ["IPK"],
    "kartu rencana studi": ["KRS"],
    "biro administrasi akademik dan kemahasiswaan": ["BAAK"],
    "biro administrasi umum dan keuangan": ["BAUK"],
    "bursa kerja khusus": ["BKK"],
    "ejaan yang disempurnakan": ["EYD"],
}

# Sinonim atau kata alternatif yang sering dipakai mahasiswa tapi punya istilah resmi.
SYNONYMS: dict[str, list[str]] = {
    "pendadaran": ["ujian skripsi", "sidang skripsi", "ujian tugas akhir", "seminar pendadaran"],
    "sidang": ["ujian akhir"],
    "pembimbing": ["dosen pembimbing"],
    "penguji": ["dosen penguji"],
}


def _has_token(text: str, token: str, *, case_sensitive: bool = True) -> bool:
    """Cek apakah token muncul sebagai kata utuh di text.

    Args:
        text: Teks yang dicari.
        token: Token yang dicocokkan.
        case_sensitive: Jika False, cocokkan case-insensitive.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.search(rf"\b{re.escape(token)}\b", text, flags) is not None


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

    # 1. Akronim → bentuk panjang
    #    - SAFE_ACRONYMS: case-insensitive (sks, ipk, krs → tetap match)
    #    - AMBIGUOUS_ACRONYMS: case-sensitive uppercase-only (pi, ta → TIDAK match)
    for acronym, expansions in UPPERCASE_ACRONYMS.items():
        if acronym in SAFE_ACRONYMS:
            matched = _has_token(question, acronym, case_sensitive=False)
        else:
            # AMBIGUOUS: hanya match kalau ditulis uppercase persis
            matched = _has_token(question, acronym, case_sensitive=True)

        if not matched:
            continue
        for exp in expansions:
            if exp.lower() not in text_lower and exp not in additions:
                additions.append(exp)

    # 2. Bentuk panjang → akronim
    for phrase, expansions in LONG_FORM_TO_ACRONYM.items():
        # Jangan ekspansi "tugas akhir" -> "TA" jika sudah merupakan "tugas akhir non skripsi"
        if phrase == "tugas akhir" and "tugas akhir non skripsi" in text_lower:
            continue

        if not _has_phrase(text_lower, phrase):
            continue
        for exp in expansions:
            # Case-insensitive check: hindari duplikasi jika user sudah
            # menulis akronim dalam bentuk apapun (mis. "kkp" atau "KKP").
            if not _has_token(question, exp, case_sensitive=False) and exp not in additions:
                additions.append(exp)

    # 3. Sinonim / Istilah Alternatif
    for word, equivalents in SYNONYMS.items():
        # re.escape untuk safety jika nanti ada entri dengan karakter regex
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
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


def expand_query_smart(question: str) -> str:
    """Backward-compatible wrapper. Aman dipanggil dari HybridSearcher."""
    return expand_query(question)
