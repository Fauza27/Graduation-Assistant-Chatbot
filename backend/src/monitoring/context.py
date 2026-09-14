"""
Context-based request metrics collector.

Dipakai untuk mengumpulkan data monitoring (timing per tahap, token, error,
skor retrieval, dsb) sepanjang siklus hidup SATU request, tanpa mengubah
signature fungsi-fungsi yang sudah ada di pipeline.

Cara pakai di titik masuk request (mis. ai_services.chat()):
    from src.monitoring.context import new_collector, clear_current

    collector = new_collector(
        session_id=session_id,
        channel=channel,
        mahasiswa_id=mahasiswa_id,
        question=question,
        username=username,
    )

    try:
        ...
    finally:
        clear_current()

Di dalam fungsi manapun yang dipanggil selama request:
    from src.monitoring.context import start_stage, end_stage

    start_stage("embedding")
    ... kode yang mau diukur ...
    end_stage()

WAJIB: modul ini tidak boleh PERNAH melempar exception ke pemanggilnya.
Kegagalan mencatat metrics TIDAK BOLEH mengganggu alur chat utama.

Semua fungsi publik di modul ini aman dipanggil meskipun belum ada collector
aktif (mis. dipanggil dari script evaluasi/testing) — dalam kasus itu menjadi
no-op.
"""

from __future__ import annotations

import contextvars
import functools
import time
import uuid
from dataclasses import dataclass, field, fields
from typing import Any, Optional

from loguru import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Nama stage harus sinkron dengan kolom:
# stage_<name>_ms di tabel request_metrics.
VALID_STAGES = (
    "validation",
    "session_load",
    "reformulation",
    "self_query",
    "embedding",
    "retrieval",
    "reranking",
    "parent_assembly",
    "generation",
    "db_save",
)


# ---------------------------------------------------------------------------
# Context state
# ---------------------------------------------------------------------------

_current: contextvars.ContextVar[Optional["RequestMetricsCollector"]] = (
    contextvars.ContextVar(
        "request_metrics_collector",
        default=None,
    )
)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

@dataclass
class RequestMetricsCollector:
    """Mengumpulkan seluruh metrics untuk satu request."""

    # Request identity
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    mahasiswa_id: Optional[str] = None
    channel: str = "unknown"

    # Request status / error
    status: str = "success"
    error_type: Optional[str] = None
    error_source: Optional[str] = None
    http_status: Optional[int] = None

    # Retrieval
    cache_hit: Optional[bool] = None
    num_docs_retrieved: Optional[int] = None
    num_docs_after_rerank: Optional[int] = None
    top_cross_encoder_score: Optional[float] = None
    avg_cross_encoder_score: Optional[float] = None
    domain_detected: Optional[str] = None
    is_no_relevant_doc: bool = False
    retrieved_parent_ids: Optional[list[str]] = None
    rewrite_method: Optional[str] = None

    # Token / cost / retry
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    embedding_tokens: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    embedding_cost_usd: Optional[float] = None
    openai_retry_count: int = 0

    # Investigation / drill-down
    # Idealnya diisi sedini mungkin agar tetap tersedia ketika request
    # berakhir error di tengah proses.
    question: Optional[str] = None
    username: Optional[str] = None
    retrieval_detail: Optional[list[dict[str, Any]]] = None

    # Internal timing state
    _stage_ms: dict[str, float] = field(default_factory=dict, repr=False)
    _stage_name: Optional[str] = field(default=None, repr=False)
    _stage_start: Optional[float] = field(default=None, repr=False)
    _request_start: float = field(
        default_factory=time.perf_counter,
        repr=False,
    )

    # ContextVar token untuk restore context sebelumnya.
    _context_token: Any = field(default=None, repr=False)
    _persisted: bool = field(default=False, repr=False)

    def start_stage(self, name: str) -> None:
        """
        Mulai timing untuk satu stage.

        Jika stage sebelumnya masih terbuka, stage tersebut ditutup lebih dulu
        secara defensif.
        """
        if name not in VALID_STAGES:
            logger.warning(
                f"[metrics] Nama stage tidak dikenal, "
                f"akan tetap dicatat: {name}"
            )

        if self._stage_name is not None:
            self.end_stage()

        self._stage_name = name
        self._stage_start = time.perf_counter()

    def end_stage(self) -> None:
        """Tutup stage aktif dan akumulasikan elapsed time."""
        if self._stage_name is None or self._stage_start is None:
            return

        elapsed_ms = (time.perf_counter() - self._stage_start) * 1000

        self._stage_ms[self._stage_name] = round(
            self._stage_ms.get(self._stage_name, 0.0) + elapsed_ms,
            2,
        )

        self._stage_name = None
        self._stage_start = None

    def add_retry(self) -> None:
        """Tambah counter untuk retryable OpenAI response."""
        self.openai_retry_count += 1

    def total_ms(self) -> float:
        """Return total elapsed time sejak collector dibuat."""
        return round(
            (time.perf_counter() - self._request_start) * 1000,
            2,
        )

    def to_row(self) -> dict[str, Any]:
        """
        Konversi collector menjadi row siap insert ke request_metrics.
        """
        # Pastikan stage yang masih terbuka tetap dihitung.
        if self._stage_name is not None:
            self.end_stage()

        row: dict[str, Any] = {
            # Identity / status
            "request_id": self.request_id,
            "session_id": self.session_id,
            "mahasiswa_id": self.mahasiswa_id,
            "channel": self.channel,
            "status": self.status,
            "error_type": self.error_type,
            "error_source": self.error_source,
            "http_status": self.http_status,
            "total_ms": self.total_ms(),

            # Retrieval
            "num_docs_retrieved": self.num_docs_retrieved,
            "num_docs_after_rerank": self.num_docs_after_rerank,
            "top_cross_encoder_score": self.top_cross_encoder_score,
            "avg_cross_encoder_score": self.avg_cross_encoder_score,
            "domain_detected": self.domain_detected,
            "is_no_relevant_doc": self.is_no_relevant_doc,
            "retrieved_parent_ids": self.retrieved_parent_ids,
            "rewrite_method": self.rewrite_method,

            # Token / cost
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "embedding_tokens": self.embedding_tokens,
            "llm_cost_usd": self.llm_cost_usd,
            "embedding_cost_usd": self.embedding_cost_usd,
            "openai_retry_count": self.openai_retry_count,
            "cache_hit": self.cache_hit,

            # Investigation
            "question": self.question,
            "username": self.username,
            "retrieval_detail": self.retrieval_detail,
        }

        for stage in VALID_STAGES:
            row[f"stage_{stage}_ms"] = self._stage_ms.get(stage)

        return row


# ---------------------------------------------------------------------------
# Public field protection
# ---------------------------------------------------------------------------

# Hanya field publik yang boleh dimodifikasi lewat set_field().
# Field internal diawali "_" dan sengaja dikecualikan.
_PUBLIC_FIELD_NAMES = frozenset(
    field_info.name
    for field_info in fields(RequestMetricsCollector)
    if not field_info.name.startswith("_")
)


# ---------------------------------------------------------------------------
# Context lifecycle
# ---------------------------------------------------------------------------

def new_collector(
    session_id: str | None,
    channel: str,
    mahasiswa_id: str | None = None,
    question: str | None = None,
    username: str | None = None,
) -> RequestMetricsCollector:
    """
    Buat collector baru dan pasang sebagai collector aktif.

    Token ContextVar disimpan agar clear_current() dapat melakukan reset
    dengan benar dan mengembalikan context sebelumnya.
    """
    collector = RequestMetricsCollector(
        session_id=session_id,
        channel=channel,
        mahasiswa_id=mahasiswa_id,
        question=question,
        username=username,
    )

    token = _current.set(collector)
    collector._context_token = token

    return collector


def get_current() -> Optional[RequestMetricsCollector]:
    """Return collector aktif pada context saat ini."""
    return _current.get()


def clear_current() -> None:
    """
    Bersihkan collector aktif dan restore context sebelumnya.

    Reset token lebih aman daripada set(None), khususnya jika suatu saat
    terdapat nested collector.
    """
    collector = _current.get()

    if collector is not None and collector._context_token is not None:
        try:
            _current.reset(collector._context_token)
            return
        except Exception:
            # Token mungkin sudah tidak valid atau berasal dari context lain.
            pass

    _current.set(None)


# ---------------------------------------------------------------------------
# Safe instrumentation helpers
# ---------------------------------------------------------------------------

def _safe(fn):
    """
    Pastikan helper instrumentation tidak pernah mengganggu request utama.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception(
                f"[metrics] {fn.__name__} gagal, diabaikan"
            )

    return wrapper


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

@_safe
def start_stage(name: str) -> None:
    """Mulai timing stage pada collector aktif."""
    collector = get_current()

    if collector is not None:
        collector.start_stage(name)


@_safe
def end_stage() -> None:
    """Tutup timing stage aktif."""
    collector = get_current()

    if collector is not None:
        collector.end_stage()


@_safe
def add_retry() -> None:
    """Tambah counter retryable response pada collector aktif."""
    collector = get_current()

    if collector is not None:
        collector.add_retry()


@_safe
def set_field(**kwargs: Any) -> None:
    """
    Set satu atau lebih field publik pada collector aktif.

    Field internal maupun attribute yang tidak dikenal tidak boleh ditimpa.

    Contoh:
        set_field(
            domain_detected="KKP",
            is_no_relevant_doc=True,
        )
    """
    collector = get_current()

    if collector is None:
        return

    for key, value in kwargs.items():
        if key in _PUBLIC_FIELD_NAMES:
            setattr(collector, key, value)
        else:
            logger.warning(
                f"[metrics] set_field: field tidak dikenal: {key}"
            )