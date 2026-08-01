"""Test single query untuk debug self-query filter."""

from src.retrieval.self_query import extract_query_components

questions = [
    "Apa saja berkas yang harus dilampirkan saat mendaftar ujian PI?",
    "Bagaimana pakaian yang harus dikenakan pria saat ujian PI?",
    "Berapa jumlah minimal halaman untuk laporan PI?",
]

for q in questions:
    print(f"\nQuery: {q}")
    parsed = extract_query_components(q)
    print(f"  Filters: {parsed.filters}")
    print(f"  Confidence: {parsed.confidence}")
    print(f"  Section: {parsed.detected_section}")
