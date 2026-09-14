"""Read original PDFs page-by-page without using production chunks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from src.evaluation_agent.models import DocumentPage, DocumentSpec, PageWindow


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_document_manifest(path: str | Path) -> list[DocumentSpec]:
    manifest_path = Path(path)
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    documents = data.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("Manifest evaluasi harus memiliki daftar documents")

    specs: list[DocumentSpec] = []
    for raw in documents:
        spec = DocumentSpec.model_validate(raw)
        resolved = (PROJECT_ROOT / spec.path).resolve()
        if not resolved.is_relative_to(PROJECT_ROOT):
            raise ValueError(f"Path dokumen berada di luar project: {spec.path}")
        if not resolved.is_file():
            raise FileNotFoundError(f"Dokumen asli tidak ditemukan: {resolved}")
        specs.append(spec.model_copy(update={"path": resolved}))
    return specs


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(block_size):
            digest.update(block)
    return digest.hexdigest()


class OriginalDocumentReader:
    """Extract every physical PDF page and preserve its original order."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], list[DocumentPage]] = {}

    def read_pages(self, path: Path) -> list[DocumentPage]:
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError(
                "pdfplumber diperlukan; install requirements-dev.txt"
            ) from exc

        stat = path.stat()
        cache_key = (str(path), stat.st_mtime_ns, stat.st_size)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        pages: list[DocumentPage] = []
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text(layout=True) or "").strip()
                warning = None
                if len(text) < 40:
                    warning = (
                        "Teks halaman sangat sedikit; periksa tabel, gambar, atau OCR"
                    )
                pages.append(
                    DocumentPage(
                        page_number=index,
                        text=text,
                        extraction_warning=warning,
                    )
                )
        self._cache = {
            key: value for key, value in self._cache.items() if key[0] != str(path)
        }
        self._cache[cache_key] = pages
        return pages

    @staticmethod
    def build_windows(
        pages: list[DocumentPage],
        *,
        document_slug: str,
        document_title: str,
        version_id: str,
        window_size: int,
        overlap: int = 1,
    ) -> list[PageWindow]:
        if window_size < 1 or overlap >= window_size:
            raise ValueError("window_size harus > overlap dan minimal 1")
        step = window_size - overlap
        windows: list[PageWindow] = []
        for start in range(0, len(pages), step):
            batch = pages[start : start + window_size]
            if not batch:
                continue
            text = "\n\n".join(
                f"--- HALAMAN FISIK {page.page_number} ---\n{page.text or '[TIDAK ADA TEKS]'}"
                for page in batch
            )
            windows.append(
                PageWindow(
                    document_slug=document_slug,
                    document_title=document_title,
                    version_id=version_id,
                    page_start=batch[0].page_number,
                    page_end=batch[-1].page_number,
                    text=text,
                    has_extraction_warning=any(
                        page.extraction_warning for page in batch
                    ),
                )
            )
            if batch[-1].page_number == pages[-1].page_number:
                break
        return windows
