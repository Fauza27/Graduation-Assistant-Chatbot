"""Academic domains explicitly named by a student, without guessing from topics."""

import re


DOMAIN_PATTERNS = {
    "Tugas Akhir Non Skripsi": (
        r"\b(?:tugas\s+akhir\s+)?non[\s-]*skripsi\b|"
        r"\bjalur\s+(?:karya ilmiah|(?:pekerja\s+)?profesional|wirausaha)\b"
    ),
    "Skripsi": r"\bskripsi\b",
    "Penulisan Ilmiah": r"\b(?:pi|penulisan ilmiah|penelitian ilmiah)\b",
    "KKP": r"\b(?:kkp|kuliah kerja prakt[ie]k|magang)\b",
}


def explicit_domains(text: str) -> tuple[str, ...]:
    """Avoid interpreting the word 'skripsi' inside Non-Skripsi twice."""
    remaining = text
    domains = []
    for domain, pattern in DOMAIN_PATTERNS.items():
        if re.search(pattern, remaining, re.IGNORECASE):
            domains.append(domain)
            remaining = re.sub(pattern, " ", remaining, flags=re.IGNORECASE)
    return tuple(domains)
