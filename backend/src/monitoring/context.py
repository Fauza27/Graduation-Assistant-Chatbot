"""
Context-based request metrics collector.

Dipakai untuk mengumpulkan data monitoring (timing per tahap, token, error,
skor retrieval, dsb) sepanjang siklus hidup SATU request, tanpa mengubah
signature fungsi-fungsi yang sudah ada di pipeline.

Cara pakai di titik masuk request (mis. ai_services.chat()):
    from src.monitoring.context import new_collector, get_current

    collector = new_collector(session_id=session_id, channel=channel, mahasiswa_id=mahasiswa_id)
    ...
    # di dalam fungsi manapun yang dipanggil selama request ini:
    from src.monitoring.context import start_stage, end_stage
    start_stage("embedding")
    ... kode yang mau diukur ...
    end_stage()

WAJIB: modul ini tidak boleh PERNAH melempar exception ke pemanggilnya.
Kegagalan mencatat metrics TIDAK BOLEH mengganggu alur chat utama. Semua
fungsi publik di modul ini aman dipanggil meskipun belum ada collector aktif
(mis. dipanggil dari script evaluasi/testing) — dalam kasus itu jadi no-op.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# Nama tahap yang valid — HARUS sinkron dengan nama kolom stage_<name>_ms
# di tabel request_metrics (Fase 0).
VALID_STAGES = (
    "validation",
    "session_load",
    "reformulation",
    "embedding",
    "retrieval",
    "reranking",
    "parent_assembly",
    "generation",
    "db_save",
)

_current: contextvars.ContextVar[Optional["RequestMetricsCollector"]] = contextvars.ContextVar(
    "request_metrics_collector", default=None
)


@dataclass
class RequestMetricsCollector:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    mahasiswa_id: Optional[str] = None
    channel: str = "unknown"

    status: str = "success"
    error_type: Optional[str] = None
    error_source: Optional[str] = None
    http_status: Optional[int] = None

    num_docs_retrieved: Optional[int] = None
    num_docs_after_rerank: Optional[int] = None
    top_cross_encoder_score: Optional[float] = None
    avg_cross_encoder_score: Optional[float] = None
    domain_detected: Optional[str] = None
    is_no_relevant_doc: bool = False
    retrieved_parent_ids: Optional[list[str]] = None
    rewrite_method: Optional[str] = None

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    embedding_tokens: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    embedding_cost_usd: Optional[float] = None
    openai_retry_count: int = 0

    # G1-G6 (Fase 10): investigasi/drill-down. `question`/`username` idealnya
    # di-set SEDINI MUNGKIN (lewat new_collector() di bawah, atau langsung
    # set_field() tepat setelah query mentah tersedia) — supaya tetap
    # tercatat walau request ini berakhir error.
    question: Optional[str] = None
    username: Optional[str] = None
    retrieval_detail: Optional[list[dict]] = None

    _stage_ms: dict = field(default_factory=dict)
    _stage_name: Optional[str] = field(default=None, repr=False)
    _stage_start: Optional[float] = field(default=None, repr=False)
    _t_start: float = field(default_factory=time.time, repr=False)

    def start_stage(self, name: str) -> None:
        if name not in VALID_STAGES:
            logger.warning(f"[metrics] Nama stage tidak dikenal, akan tetap dicatat: {name}")
        # Kalau ada stage sebelumnya yang belum ditutup, tutup dulu (defensif).
        if self._stage_name is not None:
            self.end_stage()
        self._stage_name = name
        self._stage_start = time.time()

    def end_stage(self) -> None:
        if self._stage_name is None or self._stage_start is None:
            return
        elapsed_ms = (time.time() - self._stage_start) * 1000
        # Kalau stage yang sama dipanggil >1x (mis. reformulation kadang
        # tidak triggered), akumulasikan alih-alih menimpa.
        self._stage_ms[self._stage_name] = round(
            self._stage_ms.get(self._stage_name, 0) + elapsed_ms, 2
        )
        self._stage_name = None
        self._stage_start = None

    def add_retry(self) -> None:
        self.openai_retry_count += 1

    def total_ms(self) -> float:
        return round((time.time() - self._t_start) * 1000, 2)

    def to_row(self) -> dict[str, Any]:
        """Konversi ke dict siap di-insert ke tabel request_metrics."""
        # Tutup stage yang mungkin masih terbuka (defensif, seharusnya
        # sudah ditutup manual sebelum sampai sini).
        if self._stage_name is not None:
            self.end_stage()

        row: dict[str, Any] = {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "mahasiswa_id": self.mahasiswa_id,
            "channel": self.channel,
            "status": self.status,
            "error_type": self.error_type,
            "error_source": self.error_source,
            "http_status": self.http_status,
            "total_ms": self.total_ms(),
            "num_docs_retrieved": self.num_docs_retrieved,
            "num_docs_after_rerank": self.num_docs_after_rerank,
            "top_cross_encoder_score": self.top_cross_encoder_score,
            "avg_cross_encoder_score": self.avg_cross_encoder_score,
            "domain_detected": self.domain_detected,
            "is_no_relevant_doc": self.is_no_relevant_doc,
            "retrieved_parent_ids": self.retrieved_parent_ids,
            "rewrite_method": self.rewrite_method,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "embedding_tokens": self.embedding_tokens,
            "llm_cost_usd": self.llm_cost_usd,
            "embedding_cost_usd": self.embedding_cost_usd,
            "openai_retry_count": self.openai_retry_count,
            "question": self.question,
            "username": self.username,
            "retrieval_detail": self.retrieval_detail,
        }
        for stage in VALID_STAGES:
            row[f"stage_{stage}_ms"] = self._stage_ms.get(stage)
        return row


def new_collector(
    session_id: str | None,
    channel: str,
    mahasiswa_id: str | None = None,
    question: str | None = None,
    username: str | None = None,
) -> RequestMetricsCollector:
    """Buat collector baru dan pasang sebagai collector aktif di context saat ini.

    `question` sengaja jadi parameter di sini (bukan cuma set_field belakangan)
    supaya bisa langsung diisi di titik paling awal request (Fase 5), sebelum
    ada kemungkinan gagal di tengah jalan — lihat requirement G1/G3/G4/G6."""
    collector = RequestMetricsCollector(
        session_id=session_id, channel=channel, mahasiswa_id=mahasiswa_id,
        question=question, username=username,
    )
    _current.set(collector)
    return collector


def get_current() -> Optional[RequestMetricsCollector]:
    return _current.get()


def clear_current() -> None:
    _current.set(None)


# ── Helper module-level supaya call site tidak perlu import get_current()
# tiap kali (mengurangi boilerplate di titik-titik instrumentasi). ────────

def start_stage(name: str) -> None:
    c = get_current()
    if c is not None:
        c.start_stage(name)


def end_stage() -> None:
    c = get_current()
    if c is not None:
        c.end_stage()


def add_retry() -> None:
    c = get_current()
    if c is not None:
        c.add_retry()


def set_field(**kwargs: Any) -> None:
    """
    Set satu atau lebih field di collector aktif, no-op kalau tidak ada
    collector. Contoh: set_field(domain_detected="KKP", is_no_relevant_doc=True)
    """
    c = get_current()
    if c is None:
        return
    for key, value in kwargs.items():
        if hasattr(c, key):
            setattr(c, key, value)
        else:
            logger.warning(f"[metrics] set_field: field tidak dikenal: {key}")