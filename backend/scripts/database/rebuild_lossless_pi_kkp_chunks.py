"""Rebuild PI and KKP chunk exports without summarizing source facts.

The legacy exports were written as summaries. This utility keeps the existing
parent and child identifiers, titles, sections, and page metadata, but replaces
their content with contiguous text from the extracted source document.

Run without ``--write`` to validate and preview statistics. Use ``--write`` to
replace the four canonical JSON exports after every validation passes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ALIGNMENT_PATH = ROOT / "config/chunk_rebuild_alignment.json"
WORD_RE = re.compile(r"[\w]+", re.UNICODE)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"</?(?:table|thead|tbody|tr|th|td)(?:\s[^>]*)?>", re.I)
PAGE_NUMBER_RE = re.compile(r"^(?:\d{1,3}|[ivxlcdm]{1,6})$", re.I)


@dataclass(frozen=True)
class DocumentSpec:
    name: str
    markdown_path: Path
    parent_path: Path
    child_path: Path
    parent_start_markers: tuple[str, ...]


PI_SPEC = DocumentSpec(
    name="PI",
    markdown_path=ROOT / "extract-pdf/PI/Panduan Penyusunan Penulisan Imliah (PI) Cetak.md",
    parent_path=ROOT / "extract-pdf/PI/parent_chunk_pi.json",
    child_path=ROOT / "extract-pdf/PI/child_chunk_pi.json",
    parent_start_markers=(
        "# KATA PENGANTAR",
        "## Surat Keputusan",
        "# BAB I\n\n# PENDAHULUAN",
        "# BAB II\n\n# KETENTUAN UMUM",
        "# 2.4 MAHASISWA BIMBINGAN",
        "## 2.5 SYARAT DAN KETENTUAN",
        "## 2.7 PROSES PENYUSUNAN",
        "### 2.7.3 Prosedur Pendaftaran dan Ujian PI",
        "## 2.8 SISTEM PENILAIAN",
        "# BAB III\n\n# SISTEMATIKA PENYUSUNAN PENULISAN ILMIAH",
        "# BAB IV\n\n# PENJELASAN SISTEMATIKA PENULISAN LAPORAN",
        "## 4.2. BAGIAN UTAMA",
        "# BAB V\n\n# FORMAT DAN TATA CARA PENULISAN",
        "# 8. Tabel dan Gambar",
        "# 5.3. BAHASA",
        "# 5.5. ATURAN PENULISAN PUSTAKA ATAU SUMBER RUJUKAN",
        "**Lampiran 1. Contoh Halaman Sampul Depan**",
        "**Lampiran 5. Contoh Daftar Isi**",
        "# **Lampiran 10. Contoh Jadwal Penelitian**",
        "Lampiran 13. Form Daftar Hadir Menyaksikan Ujian",
        "**Lampiran 17. Contoh Lembar Persetujuan Ujian**",
        "**Lampiran 20. Contoh Berita Acara**",
        "Lampiran 23. Form Permohonan Penggantian Dosen Pembimbing",
    ),
)


KKP_SPEC = DocumentSpec(
    name="KKP",
    markdown_path=ROOT / "extract-pdf/KKP/Panduan Penyusunan Kuliah Kerja Praktik (KKP) Cetak.md",
    parent_path=ROOT / "extract-pdf/KKP/parent_chunk_kkp.json",
    child_path=ROOT / "extract-pdf/KKP/child_chunk_kkp.json",
    parent_start_markers=(
        "# KATA PENGANTAR",
        "## Surat Keputusan",
        "# BAB I\n# PENDAHULUAN",
        "# BAB II\n# KETENTUAN UMUM",
        "# 2.4 MAHASISWA BIMBINGAN",
        "## 2.5 SYARAT DAN KETENTUAN",
        "## 2.7 PROSES PENYUSUNAN KKP",
        "### 2.7.3 Prosedur Pendaftaran dan Ujian KKP",
        "### 2.7.5 SISTEM PENILAIAN",
        "# BAB III\n# SISTEMATIKA PENYUSUNAN KKP",
        "# BAB IV\n# PENJELASAN SISTEMATIKA PENULISAN LAPORAN",
        "### 4.2 BAGIAN UTAMA",
        "# BAB V\n# FORMAT DAN TATA CARA PENULISAN",
        "# 8. Tabel dan Gambar",
        "# 5.3 BAHASA",
        "## 5.5 ATURAN PENULISAN PUSTAKA ATAU SUMBER RUJUKAN",
        "**Lampiran 1. Contoh Halaman Sampul Depan Kuliah Kerja Praktik**",
        "**Lampiran 4. Contoh Daftar Isi**",
        "# Lampiran 9. Contoh Rincian Tugas KKP",
        "**Lampiran 13. Form Daftar Hadir Menyaksikan Ujian KKP**",
        "**Lampiran 17. Contoh Lembar Persetujuan Ujian KKP**",
        "**Lampiran 20. Contoh Berita Acara Ujian KKP**",
        "**Lampiran 23. Contoh Form Penggantian Dosen Pembimbing**",
    ),
)


def _load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def _normalize_source(text: str) -> str:
    """Remove extraction noise while retaining all readable source text."""
    text = IMAGE_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        value = "\n".join(line.rstrip() for line in paragraph.splitlines()).strip()
        if not value or PAGE_NUMBER_RE.fullmatch(value):
            continue
        paragraphs.append(value)
    return "\n\n".join(paragraphs)


def _locate_parent_ranges(source: str, markers: tuple[str, ...]) -> list[str]:
    offsets: list[int] = []
    cursor = 0
    for marker in markers:
        offset = source.find(marker, cursor)
        if offset < 0:
            raise ValueError(f"Marker tidak ditemukan setelah offset {cursor}: {marker!r}")
        offsets.append(offset)
        cursor = offset + len(marker)
    offsets.append(len(source))
    return [source[start:end].strip() for start, end in zip(offsets, offsets[1:])]


def _paragraph_blocks(text: str) -> list[str]:
    """Keep headings with their following paragraph when possible."""
    raw = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    blocks: list[str] = []
    pending_headings: list[str] = []
    for part in raw:
        lines = part.splitlines()
        is_heading = bool(lines) and all(line.lstrip().startswith("#") for line in lines)
        if is_heading:
            pending_headings.append(part)
            continue
        if pending_headings:
            part = "\n\n".join([*pending_headings, part])
            pending_headings.clear()
        blocks.append(part)
    if pending_headings:
        if blocks:
            blocks[-1] = "\n\n".join([blocks[-1], *pending_headings])
        else:
            blocks.extend(pending_headings)
    return blocks


def _partition_for_children(
    source_text: str,
    existing_children: list[dict[str, Any]],
    alignment: dict[str, dict[str, Any]],
) -> list[str]:
    """Partition a parent contiguously using legacy child sizes as guidance."""
    child_count = len(existing_children)
    if child_count == 1:
        return [source_text.strip()]

    blocks = _paragraph_blocks(source_text)
    if len(blocks) < child_count:
        # Line boundaries are a safe fallback for extraction-heavy tables.
        blocks = [line.strip() for line in source_text.splitlines() if line.strip()]
    if len(blocks) < child_count:
        raise ValueError(
            f"Tidak cukup batas teks untuk {child_count} child: hanya {len(blocks)} blok"
        )

    block_weights = [max(_word_count(block), 1) for block in blocks]
    legacy_weights = [
        int(alignment[str(child["id"])]["weight"])
        for child in existing_children
    ]
    source_total = sum(block_weights)
    legacy_total = sum(legacy_weights)

    block_terms = [_term_counter(block) for block in blocks]
    target_terms = [
        _term_counter(str(alignment[str(child["id"])]["text"]))
        for child in existing_children
    ]
    prefix_weights = [0]
    for weight in block_weights:
        prefix_weights.append(prefix_weights[-1] + weight)

    def segment_score(child_index: int, start: int, end: int) -> float:
        terms: Counter[str] = Counter()
        for counter in block_terms[start:end]:
            terms.update(counter)
        target = target_terms[child_index]
        dot = sum(value * target.get(term, 0) for term, value in terms.items())
        norm = math.sqrt(
            sum(value * value for value in terms.values())
            * sum(value * value for value in target.values())
        )
        lexical_score = dot / norm if norm else 0.0
        matched_target_terms = sum(
            min(value, terms.get(term, 0))
            for term, value in target.items()
        )
        target_recall = matched_target_terms / max(sum(target.values()), 1)
        actual_size = prefix_weights[end] - prefix_weights[start]
        expected_size = source_total * legacy_weights[child_index] / legacy_total
        size_penalty = abs(actual_size - expected_size) / max(expected_size, 1)
        return target_recall * 10.0 + lexical_score - size_penalty * 0.2

    # Dynamic programming finds ordered semantic boundaries without dropping
    # any source block. Each child receives at least one contiguous block.
    block_count = len(blocks)
    negative_infinity = float("-inf")
    scores = [[negative_infinity] * (block_count + 1) for _ in range(child_count + 1)]
    previous = [[-1] * (block_count + 1) for _ in range(child_count + 1)]
    scores[0][0] = 0.0
    for child_number in range(1, child_count + 1):
        minimum_end = child_number
        maximum_end = block_count - (child_count - child_number)
        for end in range(minimum_end, maximum_end + 1):
            for start in range(child_number - 1, end):
                if scores[child_number - 1][start] == negative_infinity:
                    continue
                score = scores[child_number - 1][start] + segment_score(
                    child_number - 1, start, end
                )
                if score > scores[child_number][end]:
                    scores[child_number][end] = score
                    previous[child_number][end] = start

    boundaries = [block_count]
    end = block_count
    for child_number in range(child_count, 0, -1):
        start = previous[child_number][end]
        if start < 0:
            raise ValueError("Tidak dapat menentukan batas semantic child")
        boundaries.append(start)
        end = start
    boundaries.reverse()

    chunks = [
        "\n\n".join(blocks[start:end]).strip()
        for start, end in zip(boundaries, boundaries[1:])
    ]
    if any(not chunk for chunk in chunks):
        raise ValueError("Hasil pembagian menghasilkan child kosong")
    return chunks


def _term_counter(text: str) -> Counter[str]:
    """Token frequencies used only to align source blocks with legacy IDs."""
    return Counter(
        term
        for term in WORD_RE.findall(text.casefold())
        if len(term) > 2
    )


def rebuild(spec: DocumentSpec) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict]:
    parents = _load_json(spec.parent_path)
    children = _load_json(spec.child_path)
    children_by_id = {str(child["id"]): child for child in children}
    source = spec.markdown_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    alignment = json.loads(ALIGNMENT_PATH.read_text(encoding="utf-8"))[spec.name]

    if len(parents) != len(spec.parent_start_markers):
        raise ValueError(
            f"{spec.name}: {len(parents)} parent tetapi "
            f"{len(spec.parent_start_markers)} marker"
        )

    raw_parent_ranges = _locate_parent_ranges(source, spec.parent_start_markers)
    rebuilt_children: dict[str, dict[str, Any]] = {}
    rebuilt_parents: list[dict[str, Any]] = []

    for parent, raw_range in zip(parents, raw_parent_ranges):
        child_ids = [str(child_id) for child_id in parent.get("child_ids", [])]
        existing_children = [children_by_id[child_id] for child_id in child_ids]
        normalized_range = _normalize_source(raw_range)
        contents = _partition_for_children(
            normalized_range,
            existing_children,
            alignment,
        )

        for child, content in zip(existing_children, contents):
            rebuilt = dict(child)
            rebuilt["content"] = content
            rebuilt_children[str(child["id"])] = rebuilt

        rebuilt_parent = dict(parent)
        rebuilt_parent["content"] = "\n\n".join(contents)
        rebuilt_parents.append(rebuilt_parent)

    ordered_children = [rebuilt_children[str(child["id"])] for child in children]
    _validate_rebuild(spec, rebuilt_parents, ordered_children, source)

    old_words = sum(
        int(alignment[str(child["id"])]["weight"])
        for child in children
    )
    new_words = sum(_word_count(parent["content"]) for parent in rebuilt_parents)
    stats = {
        "document": spec.name,
        "parents": len(rebuilt_parents),
        "children": len(ordered_children),
        "old_parent_words": old_words,
        "new_parent_words": new_words,
        "word_growth_percent": round((new_words / old_words - 1) * 100, 1),
        "max_child_words": max(_word_count(child["content"]) for child in ordered_children),
    }
    return rebuilt_parents, ordered_children, stats


def _validate_rebuild(
    spec: DocumentSpec,
    parents: list[dict[str, Any]],
    children: list[dict[str, Any]],
    source: str,
) -> None:
    child_by_id = {str(child["id"]): child for child in children}
    if len(child_by_id) != len(children):
        raise ValueError(f"{spec.name}: child ID tidak unik")

    for parent in parents:
        child_ids = [str(child_id) for child_id in parent["child_ids"]]
        expected_parent = "\n\n".join(child_by_id[child_id]["content"] for child_id in child_ids)
        if parent["content"] != expected_parent:
            raise ValueError(f"{spec.name}: parent {parent['parent_id']} tidak sinkron")
        for child_id in child_ids:
            if child_by_id[child_id]["content"] not in parent["content"]:
                raise ValueError(f"{spec.name}: child {child_id} tidak terdapat dalam parent")

    normalized_source = _normalize_source(
        source[source.find(spec.parent_start_markers[0]) :]
    )
    rebuilt_text = "\n\n".join(parent["content"] for parent in parents)
    source_terms = set(WORD_RE.findall(normalized_source.casefold()))
    rebuilt_terms = set(WORD_RE.findall(rebuilt_text.casefold()))
    coverage = len(source_terms & rebuilt_terms) / max(len(source_terms), 1)
    if coverage < 0.99:
        raise ValueError(f"{spec.name}: cakupan istilah sumber hanya {coverage:.2%}")

    required_facts = (
        "sumber kecocokan yang terdeteksi",
        "header tabel harus tetap ditampilkan",
    )
    for fact in required_facts:
        if fact.casefold() not in rebuilt_text.casefold():
            raise ValueError(f"{spec.name}: fakta wajib hilang: {fact}")
    if spec.name == "KKP":
        for fact in (
            "keselarasan antara pekerjaan",
            "dampak langsung dari tugas",
            "baik dari sisi teknis, proses kerja, maupun pengalaman pribadi",
        ):
            if fact.casefold() not in rebuilt_text.casefold():
                raise ValueError(f"KKP: fakta wajib hilang: {fact}")


def _write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Replace the canonical PI and KKP parent/child JSON exports.",
    )
    args = parser.parse_args()

    all_stats = []
    rebuilt = []
    for spec in (PI_SPEC, KKP_SPEC):
        parents, children, stats = rebuild(spec)
        rebuilt.append((spec, parents, children))
        all_stats.append(stats)

    if args.write:
        for spec, parents, children in rebuilt:
            _write_json(spec.parent_path, parents)
            _write_json(spec.child_path, children)

    print(json.dumps({"write": args.write, "documents": all_stats}, indent=2))


if __name__ == "__main__":
    main()
