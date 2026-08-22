# Rencana Pengembangan: Sistem Monitoring & Observability
### Chatbot RAG KKP/PI — `Fauza27/copy-skripsi`

---

## 0. Cara membaca dokumen ini (WAJIB dibaca dulu)

Dokumen ini adalah **spesifikasi implementasi**, bukan ringkasan konsep. Setiap fase berisi:
- **File yang disentuh** (path pasti, relatif ke `backend/`)
- **Kode "cari" (old)** — potongan kode yang sudah ada di repo saat ini, disalin persis dari source asli
- **Kode "ganti" (new)** — kode pengganti/tambahan, ditulis lengkap (bukan pseudocode abstrak) supaya bisa langsung dipakai
- **Definition of Done** — cara memverifikasi fase itu berhasil

**Aturan pengerjaan:**
1. Kerjakan fase **berurutan** (0 → 8). Fase belakang bergantung pada modul yang dibuat di fase sebelumnya.
2. Jangan mengubah behavior chat yang sudah ada. Semua instrumentasi **fail-safe**: kalau logging/metrics gagal, JANGAN sampai request user ikut gagal. Selalu bungkus dengan `try/except` dan `logger.error(...)`, jangan `raise`.
3. Kalau sebuah blok kode "cari" tidak ditemukan persis (karena file sudah berubah), STOP dan laporkan — jangan menebak dan menimpa kode yang salah.
4. Setelah tiap fase, jalankan checklist verifikasi di bagian 12 sebelum lanjut ke fase berikutnya.
5. Semua path di dokumen ini relatif terhadap folder `backend/` di root repo.

---

## 1. Prinsip desain

- **Tanpa infrastruktur baru.** Tidak ada Prometheus/Grafana/Loki. Server produksi saat ini berjalan di container kecil (2GB RAM / 1 CPU, lihat `docker-compose.yml`), jadi kita pakai **Supabase Postgres yang sudah ada** sebagai satu-satunya data store untuk metrics.
- **Non-invasive.** Sebisa mungkin tidak mengubah signature fungsi yang sudah ada (`run_retrieval()`, `HybridSearcher.search()`, dll). Kita pakai pola **context-based collector** (mirip `contextvars` yang dipakai Python `logging`/`sentry-sdk`) supaya kode instrumentasi bisa "titip" data dari dalam fungsi manapun tanpa mengubah return type-nya.
- **Fail-open.** Kegagalan mencatat metrics tidak boleh pernah membuat chat gagal. Semua write ke tabel metrics dibungkus try/except terpisah dari logic utama.
- **Satu titik masuk data = satu titik keluar data.** Baik request dari website (`POST /api/ai/chat`) maupun Telegram (`chat_handler.py`) sama-sama memanggil `ai_services.chat()`. Kita taruh sebagian besar instrumentasi di titik ini supaya otomatis berlaku untuk kedua channel.
- **Additive, bukan breaking.** Semua tabel/kolom baru bersifat tambahan. Tabel `chat_logs` yang sudah ada TIDAK diubah/dihapus — kita buat tabel baru `request_metrics` di sampingnya.

---

## 2. Peta requirement → implementasi (traceability)

Gunakan tabel ini untuk mengecek progres. Kolom "Fase" merujuk ke bagian di dokumen ini.

| # | Requirement (dari user) | Sumber data | Fase |
|---|---|---|---|
| A1 | Latency rata-rata + p50/p95/p99 + histori | `request_metrics.total_ms` | 0, 7 |
| A2 | E2E latency breakdown per 8 tahap | `request_metrics.stage_*_ms` | 0, 3, 4, 5, 6 |
| A3 | Throughput (RPS/RPM) | `request_metrics.created_at` (count per interval) | 7 |
| B1 | Error rate / timeout rate | `request_metrics.status` | 0, 6, 7 |
| B2 | Breakdown error by source | `request_metrics.error_source` | 0, 6, 7 |
| B3 | Retry rate ke OpenAI | `request_metrics.openai_retry_count` | 6 |
| B4 | Quota-rejection rate | `request_metrics.status = 'quota_rejected'` | 5, 7 |
| C1 | % + jumlah query no relevant document | `request_metrics.is_no_relevant_doc` | 3, 7 |
| C2 | Dokumen paling sering diambil | `request_metrics.retrieved_parent_ids` (lihat catatan di 3.3) | 3, 7 |
| C3 | Rata-rata chunk lolos rerank | `request_metrics.num_docs_after_rerank` | 3, 7 |
| C4 | Distribusi skor cross-encoder | `request_metrics.top_cross_encoder_score`, `avg_cross_encoder_score` | 3, 7 |
| C5 | Breakdown query per domain (KKP/PI/SKRIPSI/NON_SKRIPSI) | `request_metrics.domain_detected` | 3, 7 |
| D1 | Token usage input/output per request | `request_metrics.input_tokens`, `output_tokens` | 4, 7 |
| D2 | LLM cost, embedding cost | `request_metrics.llm_cost_usd`, `embedding_cost_usd` | 1, 4, 7 |
| D3 | Cost per request, per user/session | view `v_cost_daily`, `v_cost_per_user` | 7 |
| E1 | Active users harian/bulanan (mahasiswa vs Telegram) | view `v_active_users_daily` | 7 |
| E2 | Sesi baru vs lanjutan, avg turn/sesi | view `v_new_vs_returning_daily`, `v_avg_turns_per_session` | 7 |
| E3 | Distribusi channel | `request_metrics.channel` | 7 |
| E4 | % user kena limit kuota harian | sama dengan B4 | 5, 7 |
| E5 | Repeat/follow-up question rate | `request_metrics.rewrite_method` (proxy) | 2 (sudah ada), 7 |
| F1 | Active session vs `MAX_ACTIVE_SESSIONS`, efektivitas idle cleanup | `get_session_stats()` (sudah ada) | 8 |
| F2 | Uptime / health check | `src/api/health.py` (**sudah ada, tidak perlu kerja baru**) | — |
| F3 | Audit trail admin (chunk edit + re-embed) | tabel `chunk_edit_logs` (**sudah ada**) + view `v_admin_activity_daily` | 7, 8 |

### 2.1 Requirement tambahan — investigasi/drill-down (iterasi mockup ke-2)

Ditambahkan setelah mockup UI iterasi kedua menunjukkan kebutuhan untuk "klik lebih dalam" dari angka agregat ke data mentah per-request. Semua ini butuh **Fase 10** (bagian baru, lihat setelah Fase 8).

| # | Requirement (dari user) | Sumber data | Fase |
|---|---|---|---|
| G1 | Klik tahap pipeline → ranking request terlambat/tercepat + session + pertanyaan | `request_metrics.question`, `stage_*_ms` | 0, 2, 5, 10 |
| G2 | Klik baris histori request → detail lengkap 1 request | `request_metrics` (semua kolom, via `request_id`) | 10 |
| G3 | Info session + akun yang mengalami error | `request_metrics.session_id`, `mahasiswa_id`, `username` | 0, 2, 5, 10 |
| G4 | List pertanyaan per domain | `request_metrics.question`, `domain_detected` | 0, 2, 5, 10 |
| G5 | Detail skor cross-encoder per pertanyaan (semua kandidat, bukan cuma top/avg) | `request_metrics.retrieval_detail` (JSONB baru) | 0, 3, 10 |
| G6 | List pertanyaan berlabel no-relevant-doc | `request_metrics.question`, `is_no_relevant_doc` | 0, 2, 5, 10 |

---

## 3. Ringkasan fase pengerjaan

| Fase | Nama | Estimasi | Hasil |
|---|---|---|---|
| 0 | Migrasi database | Kecil | Tabel `request_metrics` + semua kolom siap |
| 1 | Modul inti monitoring | Sedang | `src/monitoring/` (context, errors, writer, pricing, http client) |
| 2 | Wiring di `ai_services.chat()` | Sedang | Timing session_load, db_save, status, error klasifikasi, quota, rewrite_method tercatat |
| 3 | Instrumentasi retrieval | Sedang | Timing embedding/retrieval/reranking/parent_assembly, skor, domain, no-relevant-doc tercatat |
| 4 | Instrumentasi generation & token/cost | Sedang | Token asli dari OpenAI, cost, timing generation tercatat |
| 5 | Instrumentasi entrypoint (validation + quota) | Kecil | Timing validation, quota-rejection tercatat dari kedua channel |
| 6 | Error taxonomy & retry counter | Sedang | `error_source` akurat, `openai_retry_count` terisi |
| 7 | SQL views agregasi | Sedang | Semua angka di tabel bagian 2 bisa di-query langsung |
| 8 | API endpoint admin | Sedang | `/api/admin/metrics/*` mengembalikan hasil view di atas sebagai JSON |
| 9 (opsional) | Dashboard frontend | Besar, di luar cakupan dokumen ini | Visualisasi di admin panel Next.js |
| 10 | Investigasi & drill-down (G1-G6) | Sedang | `question`/`username`/`retrieval_detail` tersimpan sejak awal request + endpoint investigasi baru |

> **Catatan urutan pengerjaan:** Fase 10 **memperluas** Fase 0, 2, 3, 5, dan 8 — bukan fase yang berdiri sendiri di akhir. Kalau Anda BELUM mulai coding sama sekali, langsung terapkan perubahan di Fase 10 pada saat mengerjakan Fase 0/2/3/5/8 masing-masing (dokumen ini sudah saya susun supaya "cari" di Fase 10 cocok dengan hasil "ganti" di fase-fase itu). Kalau Anda **sudah terlanjur** mengerjakan Fase 0-8 versi lama, jalankan Fase 10 sebagai tambahan/migrasi susulan di akhir.

---

## 4. FASE 0 — Migrasi database

### 4.1 File baru: `scripts/supabase_migration_observability.sql`

Jalankan file ini di Supabase SQL Editor (pola yang sama seperti migrasi-migrasi sebelumnya di folder `scripts/`).

```sql
-- ============================================================
-- Migrasi: Observability / Request Metrics
-- Menambahkan tabel request_metrics untuk mencatat timing,
-- token, cost, error, dan kualitas retrieval per request chat.
-- Tidak mengubah tabel yang sudah ada (chat_logs tetap dipakai
-- sebagaimana adanya).
-- ============================================================

CREATE TABLE IF NOT EXISTS request_metrics (
    id                      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    request_id              UUID NOT NULL DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Identitas request
    session_id              TEXT,
    mahasiswa_id             TEXT,
    channel                 TEXT NOT NULL DEFAULT 'unknown',   -- 'website' | 'telegram'

    -- Status akhir
    status                  TEXT NOT NULL DEFAULT 'success',   -- 'success' | 'error' | 'quota_rejected'
    error_type              TEXT,                              -- nama class exception Python
    error_source            TEXT,                              -- 'openai' | 'supabase' | 'validation' | 'rate_limit' | 'unknown'
    http_status              INT,

    -- A2: timing per tahap pipeline (dalam milidetik)
    stage_validation_ms      NUMERIC,
    stage_session_load_ms    NUMERIC,
    stage_reformulation_ms   NUMERIC,   -- tahap tambahan (query rewrite), nullable, 0 kalau tidak triggered
    stage_embedding_ms       NUMERIC,
    stage_retrieval_ms       NUMERIC,
    stage_reranking_ms       NUMERIC,
    stage_parent_assembly_ms NUMERIC,
    stage_generation_ms      NUMERIC,
    stage_db_save_ms         NUMERIC,
    total_ms                 NUMERIC,

    -- C: kualitas retrieval
    num_docs_retrieved       INT,       -- hasil hybrid search sebelum rerank
    num_docs_after_rerank    INT,       -- hasil akhir setelah threshold
    top_cross_encoder_score  NUMERIC,
    avg_cross_encoder_score  NUMERIC,
    domain_detected          TEXT,      -- 'PI' | 'KKP' | 'SKRIPSI' | 'NON_SKRIPSI' | 'UNKNOWN'
    is_no_relevant_doc       BOOLEAN NOT NULL DEFAULT FALSE,
    retrieved_parent_ids     TEXT[],    -- daftar parent_id yang dipakai jadi context akhir
    rewrite_method           TEXT,      -- 'None' | 'Rule' | 'LLM' (lihat reformulator.py)

    -- D: token & cost
    input_tokens             INT,
    output_tokens             INT,
    embedding_tokens          INT,       -- estimasi (lihat catatan Fase 4)
    llm_cost_usd              NUMERIC(12, 6),
    embedding_cost_usd        NUMERIC(12, 6),

    -- B: reliability
    openai_retry_count        INT NOT NULL DEFAULT 0,

    -- G1-G6 (Fase 10): investigasi/drill-down — ditambahkan setelah iterasi
    -- mockup UI kedua. `question` dan `username` WAJIB diisi di AWAL request
    -- (sebelum try/except di ai_services.chat(), lihat Fase 10.2), BUKAN
    -- diambil dari tabel chat_logs — karena chat_logs cuma tertulis saat
    -- request SUKSES, sedangkan kita butuh data ini juga untuk request yang
    -- ERROR (lihat requirement G3).
    question                  TEXT,      -- teks pertanyaan asli
    username                  TEXT,      -- nama tampilan (bukan ID) — dari JWT (website) atau profil Telegram
    retrieval_detail           JSONB     -- SEMUA kandidat dokumen yang sempat direranking beserta skornya,
                                          -- bukan cuma top/avg. Bentuk: [{"parent_id":"...","title":"...",
                                          -- "score":0.82,"accepted":true}, ...] — lihat Fase 10.3
);

-- Index untuk pola query agregasi (dashboard, view)
CREATE INDEX IF NOT EXISTS idx_request_metrics_created_at   ON request_metrics (created_at);
CREATE INDEX IF NOT EXISTS idx_request_metrics_session_id   ON request_metrics (session_id);
CREATE INDEX IF NOT EXISTS idx_request_metrics_channel      ON request_metrics (channel);
CREATE INDEX IF NOT EXISTS idx_request_metrics_status       ON request_metrics (status);
CREATE INDEX IF NOT EXISTS idx_request_metrics_domain       ON request_metrics (domain_detected);
CREATE INDEX IF NOT EXISTS idx_request_metrics_mahasiswa_id ON request_metrics (mahasiswa_id);
-- G4/G6: mempercepat query "list pertanyaan per domain" & "list pertanyaan no-relevant-doc"
CREATE INDEX IF NOT EXISTS idx_request_metrics_domain_no_doc ON request_metrics (domain_detected, is_no_relevant_doc);

-- Row Level Security: ikuti pola tabel lain di project ini —
-- hanya service_role (backend) yang boleh baca/tulis.
ALTER TABLE request_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on request_metrics"
    ON request_metrics
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
```

> **Catatan:** kalau project ini TIDAK memakai Supabase Auth RLS berbasis `auth.role()` (cek pola RLS di `scripts/supabase.sql` untuk tabel lain seperti `chat_logs` sebelum menjalankan blok RLS di atas — samakan polanya). Kalau tabel lain tidak pakai RLS sama sekali (karena akses selalu lewat `service_role` key dari backend), boleh skip bagian `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` dan `CREATE POLICY`.

> **Kalau tabel `request_metrics` SUDAH terlanjur dibuat** memakai versi dokumen sebelumnya (tanpa `question`/`username`/`retrieval_detail`), tidak perlu `DROP TABLE` — cukup jalankan migrasi susulan ini:
> ```sql
> ALTER TABLE request_metrics ADD COLUMN IF NOT EXISTS question TEXT;
> ALTER TABLE request_metrics ADD COLUMN IF NOT EXISTS username TEXT;
> ALTER TABLE request_metrics ADD COLUMN IF NOT EXISTS retrieval_detail JSONB;
> CREATE INDEX IF NOT EXISTS idx_request_metrics_domain_no_doc ON request_metrics (domain_detected, is_no_relevant_doc);
> ```

### 4.2 Definition of Done — Fase 0
- [ ] Tabel `request_metrics` ada di Supabase (cek lewat Table Editor atau `select * from request_metrics limit 1;`)
- [ ] Insert manual satu baris dummy berhasil tanpa error
- [ ] Kolom `question`, `username`, `retrieval_detail` ada (cek lewat Table Editor, tipe `retrieval_detail` harus `jsonb`)

---

## 5. FASE 1 — Modul inti monitoring

Semua file baru di folder `src/monitoring/` (folder baru, buat dulu foldernya).

### 5.1 File baru: `src/monitoring/__init__.py`

```python
# Modul monitoring & observability. Lihat context.py untuk API utama.
```

### 5.2 File baru: `src/monitoring/context.py`

Ini modul paling penting di seluruh fase. Berfungsi sebagai "tempat titip data" metrics yang bisa diakses dari fungsi manapun sepanjang satu request, tanpa mengubah signature fungsi manapun.

```python
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
```

### 5.3 File baru: `src/monitoring/errors.py`

```python
"""
Taksonomi error kustom untuk klasifikasi `error_source` di request_metrics.

Dua cara pakai:
1. Raise exception spesifik (ValidationServiceError, dst) di titik yang kita
   kontrol sendiri — paling akurat.
2. Untuk exception yang datang dari library pihak ketiga (openai-python,
   supabase-py, httpx) yang TIDAK kita bungkus manual, pakai
   `classify_exception()` sebagai fallback berbasis nama modul exception.
"""

from __future__ import annotations


class ChatError(Exception):
    """Base exception untuk semua error di alur chat."""
    error_source = "unknown"


class ValidationServiceError(ChatError):
    error_source = "validation"


class OpenAIServiceError(ChatError):
    error_source = "openai"


class SupabaseServiceError(ChatError):
    error_source = "supabase"


class RetrievalError(ChatError):
    """Dipertahankan agar kompatibel dengan RetrievalError yang sudah ada
    di ai_services.py (Fase 2 akan memindahkan definisinya ke sini)."""
    error_source = "supabase"


class RateLimitServiceError(ChatError):
    error_source = "rate_limit"


def classify_exception(exc: Exception) -> tuple[str, str]:
    """
    Kembalikan (error_source, error_type) dari exception APA PUN — baik
    yang sudah dibungkus manual (ChatError dan turunannya) maupun exception
    mentah dari library pihak ketiga yang belum sempat dibungkus.
    """
    if isinstance(exc, ChatError):
        return exc.error_source, type(exc).__name__

    exc_module = type(exc).__module__ or ""

    if "openai" in exc_module:
        return "openai", type(exc).__name__
    if "postgrest" in exc_module or "supabase" in exc_module or "httpx" in exc_module:
        return "supabase", type(exc).__name__
    if isinstance(exc, ValueError):
        return "validation", type(exc).__name__

    return "unknown", type(exc).__name__
```

### 5.4 File baru: `config/pricing.yaml`

Mengikuti pola `config/section_keywords.yaml` yang sudah ada di project ini (konfigurasi eksternal, bukan hardcode di Python).

```yaml
# Harga OpenAI API dalam USD per 1 JUTA token.
# Sumber acuan: openai.com/pricing.
# TERAKHIR DIVERIFIKASI: 2026-06-07 — WAJIB DICEK ULANG SEBELUM DIPAKAI
# UNTUK KEPUTUSAN BISNIS, karena harga OpenAI bisa berubah sewaktu-waktu.
llm:
  gpt-4o-mini:
    input_per_1m: 0.15
    output_per_1m: 0.60
  gpt-4o:
    input_per_1m: 2.50
    output_per_1m: 10.00

embedding:
  text-embedding-3-large:
    input_per_1m: 0.13
  text-embedding-3-small:
    input_per_1m: 0.02
```

### 5.5 File baru: `src/monitoring/pricing.py`

```python
"""
Kalkulasi cost dari token usage, berdasarkan config/pricing.yaml.

Pola loading sama seperti `_load_section_keywords` di
src/retrieval/self_query.py — load sekali saat import, cache di module level.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PRICING_PATH = _PROJECT_ROOT / "config" / "pricing.yaml"


def _load_pricing(path: Path = _PRICING_PATH) -> dict:
    if not path.exists():
        logger.error(f"Pricing file tidak ditemukan: {path}. Cost akan selalu 0.")
        return {"llm": {}, "embedding": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


_PRICING = _load_pricing()


def calculate_llm_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    """Hitung cost generation LLM dalam USD. Return 0.0 kalau model tidak ada di pricing.yaml."""
    pricing = _PRICING.get("llm", {}).get(model)
    if not pricing or input_tokens is None or output_tokens is None:
        if not pricing:
            logger.warning(f"[pricing] Model '{model}' tidak ada di config/pricing.yaml, cost dihitung 0.")
        return 0.0
    cost = (input_tokens / 1_000_000 * pricing.get("input_per_1m", 0)) + (
        output_tokens / 1_000_000 * pricing.get("output_per_1m", 0)
    )
    return round(cost, 6)


def calculate_embedding_cost(model: str, tokens: int | None) -> float:
    """Hitung cost embedding dalam USD. Embedding cuma charge input tokens."""
    pricing = _PRICING.get("embedding", {}).get(model)
    if not pricing or tokens is None:
        if not pricing:
            logger.warning(f"[pricing] Model embedding '{model}' tidak ada di config/pricing.yaml, cost dihitung 0.")
        return 0.0
    cost = tokens / 1_000_000 * pricing.get("input_per_1m", 0)
    return round(cost, 6)
```

### 5.6 File baru: `src/monitoring/writer.py`

```python
"""
Persist RequestMetricsCollector ke tabel `request_metrics` di Supabase.

Pola sama seperti insert ke `chat_logs` yang sudah ada di
src/services/ai_services.py: sinkron, dibungkus try/except, TIDAK PERNAH
melempar exception ke pemanggil.
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger
from supabase import Client, create_client

from config.settings import get_settings
from src.monitoring.context import RequestMetricsCollector


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def persist_metrics(collector: RequestMetricsCollector) -> None:
    settings = get_settings()
    if not getattr(settings, "ENABLE_REQUEST_METRICS", True):
        return
    try:
        row = collector.to_row()
        _get_supabase_client().table("request_metrics").insert(row).execute()
    except Exception as e:
        logger.error(f"[metrics] Gagal menyimpan request_metrics request_id={collector.request_id}: {e}")


def persist_quota_rejection(
    session_id: str | None,
    channel: str,
    mahasiswa_id: str | None,
) -> None:
    """Catat baris minimal saat request ditolak KARENA KUOTA HARIAN HABIS
    (terjadi sebelum ai_services.chat() dipanggil, jadi butuh fungsi terpisah)."""
    settings = get_settings()
    if not getattr(settings, "ENABLE_REQUEST_METRICS", True):
        return
    try:
        _get_supabase_client().table("request_metrics").insert(
            {
                "session_id": session_id,
                "channel": channel,
                "mahasiswa_id": mahasiswa_id,
                "status": "quota_rejected",
                "total_ms": 0,
            }
        ).execute()
    except Exception as e:
        logger.error(f"[metrics] Gagal mencatat quota rejection untuk session {session_id}: {e}")
```

### 5.7 File baru: `src/monitoring/openai_client.py`

Untuk kategori **B3 (retry rate ke OpenAI)**. OpenAI Python SDK v1.x (dipakai oleh `langchain-openai`) berjalan di atas `httpx`, dan `httpx.Client` mendukung `event_hooks` yang terpanggil di setiap response HTTP — termasuk response yang di-retry secara internal oleh SDK sebelum akhirnya sukses/gagal total.

```python
"""
HTTP client kustom untuk OpenAI (dipakai ChatOpenAI & OpenAIEmbeddings)
yang menghitung jumlah retry (response 429/5xx) lewat httpx event hook.
"""

from __future__ import annotations

import httpx

from src.monitoring.context import add_retry

_RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


def _on_response(response: httpx.Response) -> None:
    if response.status_code in _RETRYABLE_STATUS_CODES:
        add_retry()


def build_instrumented_http_client() -> httpx.Client:
    """Buat httpx.Client baru dengan event hook penghitung retry terpasang.

    Dipakai sebagai parameter `http_client=` saat membuat instance
    ChatOpenAI / OpenAIEmbeddings di seluruh codebase (lihat Fase 6)."""
    return httpx.Client(event_hooks={"response": [_on_response]})
```

### 5.8 Environment variable & settings baru

**File:** `config/settings.py`

Cari blok ini:
```python
    # Memory Management
    MAX_ACTIVE_SESSIONS: int = Field(default=1000, ge=100, le=10000)
    SESSION_CLEANUP_INTERVAL: int = Field(default=3600, ge=300, le=7200)  # seconds
    USE_DATABASE_SESSIONS: bool = Field(default=True, description="Use database-backed sessions instead of in-memory")
    MAX_HISTORY_TURNS: int = Field(default=3, ge=1, le=10, description="Maximum number of conversation turns sent to LLM")
```

Tambahkan tepat setelahnya (sebelum baris `@field_validator`):
```python
    # Monitoring & Observability
    ENABLE_REQUEST_METRICS: bool = Field(default=True, description="Aktifkan pencatatan request_metrics")
```

**File:** `.env.example` — tambahkan baris:
```
# Monitoring
ENABLE_REQUEST_METRICS=true
```

### 5.9 Dependency baru

Cek apakah `pyyaml` sudah ada (kemungkinan besar sudah, karena `self_query.py` sudah memakainya untuk `section_keywords.yaml`). Kalau belum ada di dependency list project (`requirements.txt` / `pyproject.toml` — cek dulu file mana yang dipakai project ini), tambahkan:
```
pyyaml
```
`httpx` juga hampir pasti sudah terpasang sebagai dependency transitif dari `openai`/`langchain-openai`, tidak perlu ditambahkan manual.

### 5.10 Definition of Done — Fase 1
- [ ] `python -c "from src.monitoring.context import new_collector; c = new_collector('s1','website'); c.start_stage('embedding'); c.end_stage(); print(c.to_row())"` berjalan tanpa error dan mencetak dict dengan semua field
- [ ] `python -c "from src.monitoring.pricing import calculate_llm_cost; print(calculate_llm_cost('gpt-4o-mini', 1000, 500))"` mencetak angka > 0

---

## 6. FASE 2 — Wiring di `ai_services.chat()`

Ini perubahan paling besar. File `src/services/ai_services.py` di-refactor supaya:
1. Membuat collector di awal request
2. Mengukur `session_load` dan `db_save`
3. Mengklasifikasi error dan menyimpan status akhir
4. Memanggil `persist_metrics()` di akhir (baik sukses maupun gagal)
5. Memindahkan `ChatError`/`RetrievalError` ke `src/monitoring/errors.py` (Fase 1) supaya konsisten dipakai di seluruh codebase

### 6.1 File: `src/services/ai_services.py`

**Cari (bagian import & exception class, baris 1–31 saat ini):**
```python
from typing import Dict, Any, Optional
import time
from loguru import logger
from cachetools import TTLCache

from src.generation.memory import ConversationMemory
from src.generation.intent_classifier.reformulator import normalize_query, needs_rewrite, reformulate_query
from src.generation.chain import RAGChain
from src.services.session_strategy import create_session_store, SessionStore
from config.settings import get_settings

settings = get_settings()

# Cache for retrieval results (max 500 items, TTL 30 minutes)
retrieval_cache = TTLCache(maxsize=500, ttl=1800)
KNOWLEDGE_VERSION = "v1"

# Initialize session store strategy (dipilih sekali saat startup)
_session_store_strategy: SessionStore = create_session_store()

_rag_chain = RAGChain()


class ChatError(Exception):
    """Custom exception for chat-related errors"""
    pass


class RetrievalError(ChatError):
    """Exception for retrieval-related errors"""
    pass
```

**Ganti dengan:**
```python
from typing import Dict, Any, Optional
import time
from loguru import logger
from cachetools import TTLCache

from src.generation.memory import ConversationMemory
from src.generation.intent_classifier.reformulator import normalize_query, needs_rewrite, reformulate_query
from src.generation.chain import RAGChain
from src.services.session_strategy import create_session_store, SessionStore
from src.monitoring.context import new_collector, start_stage, end_stage, set_field, get_current
from src.monitoring.writer import persist_metrics
from src.monitoring.errors import ChatError, RetrievalError, classify_exception
from config.settings import get_settings

settings = get_settings()

# Cache for retrieval results (max 500 items, TTL 30 minutes)
retrieval_cache = TTLCache(maxsize=500, ttl=1800)
KNOWLEDGE_VERSION = "v1"

# Initialize session store strategy (dipilih sekali saat startup)
_session_store_strategy: SessionStore = create_session_store()

_rag_chain = RAGChain()

# NOTE: ChatError & RetrievalError sekarang didefinisikan di
# src/monitoring/errors.py (diimpor di atas) supaya taksonomi error
# konsisten dipakai di seluruh codebase, termasuk untuk klasifikasi
# `error_source` di request_metrics.
```

**Cari (fungsi `chat()` lengkap, baris 62–188 saat ini):**
```python
def chat(query: str, session_id: str, username: str, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main chat function implementing Retrieval-First Architecture.
    """
    if not query or not query.strip():
        return {"answer": "Pertanyaan tidak boleh kosong.", "num_docs": 0, "error": "empty_query"}

    if not session_id:
        return {"answer": "Session ID diperlukan.", "num_docs": 0, "error": "missing_session_id"}

    t_start = time.time()
    question = query.strip()
    logger.info(f"[session={session_id}] Question: {question}")
    
    try:
        # 1. Normalization
        normalized_query = normalize_query(question)
        
        # 2. Need Rewrite?
        rewrite_needed = needs_rewrite(normalized_query)
        
        resolved_query = normalized_query
        rewrite_method = "None"
        memory = None
        
        # SLOW PATH: Load memory early for query rewrite
        if rewrite_needed:
            memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
            memory.add_user_turn(question)
            
            t_rewrite_start = time.time()
            resolved_query, rewrite_method = reformulate_query(normalized_query, memory)
            t_rewrite_end = time.time()
            logger.info(f"[session={session_id}] [Rewrite] {rewrite_method}: '{normalized_query}' → '{resolved_query}' [⏱️ {t_rewrite_end - t_rewrite_start:.2f}s]")
            
        # 3. Cache Check
        cache_key = f"{KNOWLEDGE_VERSION}_{resolved_query}"
        cached_result = retrieval_cache.get(cache_key)
        
        if cached_result is not None:
            logger.info(f"⚡ [Cache Hit] Retrieval skipped for: '{resolved_query}'")
            retrieval_docs = cached_result
        else:
            logger.info(f"🔍 [Cache Miss] Running retrieval for: '{resolved_query}'")
            from src.retrieval.pipeline import run_retrieval
            retrieval = run_retrieval(query=resolved_query, rerank_query=question)
            retrieval_docs = retrieval.parent_documents
            # Cache the results
            retrieval_cache[cache_key] = retrieval_docs

        # FAST PATH: Load memory here if not loaded yet
        if memory is None:
            memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
            memory.add_user_turn(question)
            
        # 4. LLM Generation
        t_gen_start = time.time()
        result = _rag_chain.invoke_with_history(
            question=question,
            context_documents=retrieval_docs,
            conversation_history=memory.get_history_for_llm(),
        )
        t_gen_end = time.time()
        logger.info(f"[session={session_id}] Generation time [⏱️ {t_gen_end - t_gen_start:.2f}s]")
        
        answer = result["answer"]
        
        # Prepare sources metadata
        sources_list = [
            {
                "section": p.get("section", ""),
                "title": p.get("title", ""),
                "parent_id": p.get("parent_id", ""),
                "score": p.get("cross_encoder_score", 0.0),
                "pages": p.get("matched_pages", []),
            }
            for p in retrieval_docs[:3]
        ] if retrieval_docs else []

        # 5. Save state
        if retrieval_docs:
            memory.add_assistant_turn(
                content=answer,
                retrieved_doc_contents=[p["content"] for p in retrieval_docs],
                sources=sources_list,
            )
        else:
            memory.add_assistant_turn(content=answer)
            
        _save_memory_if_needed(session_id, memory, channel=channel, mahasiswa_id=mahasiswa_id)
        
        t_total_end = time.time()
        logger.info(f"[session={session_id}] Total process time [⏱️ {t_total_end - t_start:.2f}s]")
        
        # 6. Catat chat log
        try:
            # Use strategy untuk get database access jika menggunakan database sessions
            if hasattr(_session_store_strategy, '_store') and hasattr(_session_store_strategy._store, '_supabase'):
                user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
                _session_store_strategy._store._supabase.table("chat_logs").insert({
                    "user_id": user_id_log,
                    "username": username,
                    "question": question,
                    "answer": answer,
                }).execute()
        except Exception as e:
            user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
            logger.error(f"Gagal menyimpan log chat untuk user {user_id_log}: {e}")

        return {
            "answer": answer,
            "num_docs": len(retrieval_docs),
            "rewrite_method": rewrite_method,
            "sources": sources_list,
        }
        
    except Exception as e:
        logger.error(f"[session={session_id}] Error processing query: {e}", exc_info=True)
        return {
            "answer": (
                "Maaf, terjadi kesalahan saat memproses pertanyaan Anda. "
                "Silakan coba lagi atau hubungi administrator jika masalah berlanjut."
            ),
            "num_docs": 0,
            "error": str(e),
            "error_type": type(e).__name__,
        }
```

**Ganti dengan:**
```python
def chat(query: str, session_id: str, username: str, channel: str = "telegram", mahasiswa_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main chat function implementing Retrieval-First Architecture.
    """
    if not query or not query.strip():
        return {"answer": "Pertanyaan tidak boleh kosong.", "num_docs": 0, "error": "empty_query"}

    if not session_id:
        return {"answer": "Session ID diperlukan.", "num_docs": 0, "error": "missing_session_id"}

    # Kalau titik masuk (ai.py / chat_handler.py, Fase 5) SUDAH membuat
    # collector duluan untuk mengukur tahap "validation", pakai itu.
    # Kalau belum ada (mis. dipanggil langsung dari script/test), buat baru
    # di sini supaya fungsi ini tetap bisa dipakai standalone.
    collector = get_current()
    if collector is None:
        collector = new_collector(
            session_id=session_id, channel=channel, mahasiswa_id=mahasiswa_id,
            question=query.strip(), username=username,
        )
    else:
        collector.session_id = session_id
        collector.mahasiswa_id = mahasiswa_id
        collector.channel = channel
        # G1/G3/G4/G6: pastikan question/username terisi walau collector-nya
        # sudah dibuat lebih dulu di Fase 5 (ai.py/chat_handler.py) — di sana
        # `username` final (hasil resolve JWT/profil Telegram) baru diketahui
        # SETELAH collector dibuat, jadi di-set (ulang) di sini untuk jaga-jaga.
        collector.question = collector.question or query.strip()
        collector.username = username

    t_start = time.time()
    question = query.strip()
    logger.info(f"[session={session_id}] Question: {question}")

    try:
        # 1. Normalization
        normalized_query = normalize_query(question)

        # 2. Need Rewrite?
        rewrite_needed = needs_rewrite(normalized_query)

        resolved_query = normalized_query
        rewrite_method = "None"
        memory = None

        # SLOW PATH: Load memory early for query rewrite
        if rewrite_needed:
            start_stage("session_load")
            memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
            end_stage()
            memory.add_user_turn(question)

            start_stage("reformulation")
            t_rewrite_start = time.time()
            resolved_query, rewrite_method = reformulate_query(normalized_query, memory)
            t_rewrite_end = time.time()
            end_stage()
            logger.info(f"[session={session_id}] [Rewrite] {rewrite_method}: '{normalized_query}' → '{resolved_query}' [⏱️ {t_rewrite_end - t_rewrite_start:.2f}s]")

        set_field(rewrite_method=rewrite_method)

        # 3. Cache Check
        cache_key = f"{KNOWLEDGE_VERSION}_{resolved_query}"
        cached_result = retrieval_cache.get(cache_key)

        if cached_result is not None:
            logger.info(f"⚡ [Cache Hit] Retrieval skipped for: '{resolved_query}'")
            retrieval_docs = cached_result
        else:
            logger.info(f"🔍 [Cache Miss] Running retrieval for: '{resolved_query}'")
            from src.retrieval.pipeline import run_retrieval
            retrieval = run_retrieval(query=resolved_query, rerank_query=question)
            retrieval_docs = retrieval.parent_documents
            # Cache the results
            retrieval_cache[cache_key] = retrieval_docs
            # NOTE: retrieval.* field tambahan (domain_detected, skor, dst)
            # sudah otomatis ditulis ke collector oleh run_retrieval() itu
            # sendiri di Fase 3 — tidak perlu diulang manual di sini.
            # Kalau cache HIT, field-field itu TIDAK terisi untuk request
            # ini (retrieval tidak benar-benar jalan) — ini trade-off yang
            # disengaja, cache hit memang tidak merepresentasikan retrieval
            # baru.

        # FAST PATH: Load memory here if not loaded yet
        if memory is None:
            start_stage("session_load")
            memory = get_or_create_memory(session_id, mahasiswa_id=mahasiswa_id)
            end_stage()
            memory.add_user_turn(question)

        # 4. LLM Generation
        start_stage("generation")
        t_gen_start = time.time()
        result = _rag_chain.invoke_with_history(
            question=question,
            context_documents=retrieval_docs,
            conversation_history=memory.get_history_for_llm(),
        )
        t_gen_end = time.time()
        end_stage()
        logger.info(f"[session={session_id}] Generation time [⏱️ {t_gen_end - t_gen_start:.2f}s]")

        answer = result["answer"]

        # Prepare sources metadata
        sources_list = [
            {
                "section": p.get("section", ""),
                "title": p.get("title", ""),
                "parent_id": p.get("parent_id", ""),
                "score": p.get("cross_encoder_score", 0.0),
                "pages": p.get("matched_pages", []),
            }
            for p in retrieval_docs[:3]
        ] if retrieval_docs else []

        # 5. Save state
        if retrieval_docs:
            memory.add_assistant_turn(
                content=answer,
                retrieved_doc_contents=[p["content"] for p in retrieval_docs],
                sources=sources_list,
            )
        else:
            memory.add_assistant_turn(content=answer)

        start_stage("db_save")
        _save_memory_if_needed(session_id, memory, channel=channel, mahasiswa_id=mahasiswa_id)

        t_total_end = time.time()
        logger.info(f"[session={session_id}] Total process time [⏱️ {t_total_end - t_start:.2f}s]")

        # 6. Catat chat log (chat_logs, tabel lama — TIDAK diubah)
        try:
            # Use strategy untuk get database access jika menggunakan database sessions
            if hasattr(_session_store_strategy, '_store') and hasattr(_session_store_strategy._store, '_supabase'):
                user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
                _session_store_strategy._store._supabase.table("chat_logs").insert({
                    "user_id": user_id_log,
                    "username": username,
                    "question": question,
                    "answer": answer,
                }).execute()
        except Exception as e:
            user_id_log = str(mahasiswa_id) if mahasiswa_id else str(session_id)
            logger.error(f"Gagal menyimpan log chat untuk user {user_id_log}: {e}")
        end_stage()  # menutup db_save

        collector.status = "success"
        persist_metrics(collector)

        return {
            "answer": answer,
            "num_docs": len(retrieval_docs),
            "rewrite_method": rewrite_method,
            "sources": sources_list,
        }

    except Exception as e:
        logger.error(f"[session={session_id}] Error processing query: {e}", exc_info=True)

        error_source, error_type = classify_exception(e)
        collector.status = "error"
        collector.error_source = error_source
        collector.error_type = error_type
        persist_metrics(collector)

        return {
            "answer": (
                "Maaf, terjadi kesalahan saat memproses pertanyaan Anda. "
                "Silakan coba lagi atau hubungi administrator jika masalah berlanjut."
            ),
            "num_docs": 0,
            "error": str(e),
            "error_type": type(e).__name__,
        }
```

> **Catatan penting soal tahap "db_save":** blok `try/except` pencatatan `chat_logs` sudah dibungkus except-nya sendiri (supaya kegagalan log tidak menggagalkan chat) — jangan hapus itu, `start_stage("db_save")` / `end_stage()` cuma membungkus di LUAR blok itu.

### 6.2 Definition of Done — Fase 2
- [ ] Kirim satu request chat lewat endpoint `/api/ai/chat` (atau lewat Telegram), lalu cek di Supabase: `select * from request_metrics order by created_at desc limit 1;` — harus muncul baris baru dengan `status='success'`, `stage_session_load_ms` dan `stage_db_save_ms` terisi
- [ ] Matikan sementara koneksi internet / masukkan API key OpenAI yang salah, kirim chat, pastikan chat tetap mengembalikan pesan error yang sopan ke user (behavior lama tidak berubah) **dan** baris baru muncul di `request_metrics` dengan `status='error'`

---

## 7. FASE 3 — Instrumentasi retrieval

Tahap ini mengisi: `stage_embedding_ms`, `stage_retrieval_ms`, `stage_reranking_ms`, `stage_parent_assembly_ms`, `num_docs_retrieved`, `num_docs_after_rerank`, `top_cross_encoder_score`, `avg_cross_encoder_score`, `domain_detected`, `is_no_relevant_doc`, `retrieved_parent_ids`.

### 7.1 File: `src/retrieval/hybrid_search.py`

Timing embedding (`t_embed`) dan retrieval (`t_rpc`) **sudah dihitung secara lokal** di file ini — kita cuma perlu menyalurkannya ke collector.

**Cari:**
```python
        t0 = time.time()
        query_embedding = self._embedder.embed_query(query)
        t_embed = time.time() - t0
        logger.info(f"  [Profile] Query Embedding: {t_embed:.2f}s")
```

**Ganti dengan:**
```python
        from src.monitoring.context import start_stage, end_stage

        start_stage("embedding")
        t0 = time.time()
        query_embedding = self._embedder.embed_query(query)
        t_embed = time.time() - t0
        end_stage()
        logger.info(f"  [Profile] Query Embedding: {t_embed:.2f}s")
```

**Cari:**
```python
        t1 = time.time()
        response = self._supabase.rpc("hybrid_search", rpc_params).execute()
        t_rpc = time.time() - t1
        logger.info(f"  [Profile] Supabase Hybrid RPC: {t_rpc:.2f}s")
```

**Ganti dengan:**
```python
        start_stage("retrieval")
        t1 = time.time()
        response = self._supabase.rpc("hybrid_search", rpc_params).execute()
        t_rpc = time.time() - t1
        end_stage()
        logger.info(f"  [Profile] Supabase Hybrid RPC: {t_rpc:.2f}s")
```

> Catatan: fallback ke `match_child_documents` (dense-only) di bawahnya TIDAK perlu timing terpisah — biarkan tetap masuk hitungan `retrieval` kalau memang jalur itu yang dieksekusi. Kalau mau presisi lebih tinggi, boleh bungkus blok fallback dengan `start_stage("retrieval")`/`end_stage()` juga, tapi ini opsional.

Juga tambahkan import di bagian atas file (dekat import lain), untuk konsistensi (opsional kalau sudah pakai local import di atas):
```python
from src.monitoring.context import set_field
```

**Cari (bagian akhir fungsi `search`):**
```python
        logger.info(f"Hybrid search selesai: {len(results)} results")
        if results:
            logger.info(
                f"  Top: {results[0].child_id} | hybrid={results[0].hybrid_score:.4f}"
            )

        return results
```

**Ganti dengan:**
```python
        logger.info(f"Hybrid search selesai: {len(results)} results")
        if results:
            logger.info(
                f"  Top: {results[0].child_id} | hybrid={results[0].hybrid_score:.4f}"
            )

        set_field(num_docs_retrieved=len(results))
        return results
```

### 7.2 File: `src/retrieval/pipeline.py`

Ini tempat kita mengukur `reranking`, `parent_assembly`, menentukan `domain_detected`, `is_no_relevant_doc`, `num_docs_after_rerank`, `retrieved_parent_ids`, dan skor cross-encoder.

**Cari (bagian import di atas file):**
```python
from __future__ import annotations

from dataclasses import dataclass
import time

from loguru import logger

from config.settings import get_settings
```

**Ganti dengan:**
```python
from __future__ import annotations

from dataclasses import dataclass
import time

from loguru import logger

from config.settings import get_settings
from src.monitoring.context import start_stage, end_stage, set_field
```

**Cari:**
```python
    from src.retrieval.self_query import extract_query_components
    from src.retrieval.hybrid_search import HybridSearcher
    from src.retrieval.parent_child import ParentChildFetcher
    from src.retrieval.reranker import CrossEncoderReranker

    settings = get_settings()
    rerank_query = rerank_query or query

    t_start = time.time()
    parsed = extract_query_components(query)
    t_parse = time.time()

    searcher = HybridSearcher()
    search_results = searcher.search(
        query=parsed.semantic_query,
        filters=parsed.filters,
    )
    t_search = time.time()

    if not search_results:
        logger.info("⏭️ Zero documents found in Hybrid Search. Short-circuiting.")
        return RetrievalResult(parent_documents=[], is_empty=True)

    fetcher = ParentChildFetcher()
    parent_results = fetcher.fetch_parents(search_results)
    t_fetch = time.time()

    if not parent_results:
        logger.info("⏭️ Zero parent documents fetched. Short-circuiting.")
        return RetrievalResult(parent_documents=[], is_empty=True)
```

**Ganti dengan:**
```python
    from src.retrieval.self_query import extract_query_components
    from src.retrieval.hybrid_search import HybridSearcher
    from src.retrieval.parent_child import ParentChildFetcher
    from src.retrieval.reranker import CrossEncoderReranker
    from src.retrieval.source_utils import detect_panduan_type

    settings = get_settings()
    rerank_query = rerank_query or query

    t_start = time.time()
    parsed = extract_query_components(query)
    t_parse = time.time()

    # C5: domain_detected dihitung dari hasil self-query classifier, BUKAN
    # dari dokumen yang berhasil diambil — supaya tetap ada atribusi domain
    # walaupun retrieval-nya gagal total (dibutuhkan untuk analisis "domain
    # mana paling sering gagal retrieval").
    domain_detected = (
        detect_panduan_type({"source": parsed.detected_source})
        if parsed.detected_source
        else "UNKNOWN"
    )
    set_field(domain_detected=domain_detected)

    searcher = HybridSearcher()
    search_results = searcher.search(
        query=parsed.semantic_query,
        filters=parsed.filters,
    )
    t_search = time.time()

    if not search_results:
        logger.info("⏭️ Zero documents found in Hybrid Search. Short-circuiting.")
        set_field(is_no_relevant_doc=True, num_docs_after_rerank=0, retrieved_parent_ids=[])
        return RetrievalResult(parent_documents=[], is_empty=True)

    start_stage("parent_assembly")
    fetcher = ParentChildFetcher()
    parent_results = fetcher.fetch_parents(search_results)
    end_stage()
    t_fetch = time.time()

    if not parent_results:
        logger.info("⏭️ Zero parent documents fetched. Short-circuiting.")
        set_field(is_no_relevant_doc=True, num_docs_after_rerank=0, retrieved_parent_ids=[])
        return RetrievalResult(parent_documents=[], is_empty=True)
```

**Cari (jalur adaptive-skip-reranking):**
```python
    if len(candidate_parents) <= settings.min_parent_for_rerank:
        logger.info(f"⏭️ Skipping Reranking: only {len(candidate_parents)} candidates (<= {settings.min_parent_for_rerank})")
        
        final_results = candidate_parents[: settings.rerank_top_n]
        # Pastikan ada key cross_encoder_score agar format seragam
        for p in final_results:
            p["cross_encoder_score"] = p.get("best_child_score", 0.0)
            
        t_rerank = time.time()
        logger.info(f"⏱️ [Retrieval Pipeline] Total: {t_rerank - t_start:.2f}s | "
                    f"Parse: {t_parse - t_start:.2f}s | "
                    f"Search: {t_search - t_parse:.2f}s | "
                    f"Fetch: {t_fetch - t_search:.2f}s | "
                    f"Rerank (Skipped): 0.00s")
        return RetrievalResult(parent_documents=final_results, is_empty=False)
```

**Ganti dengan:**
```python
    if len(candidate_parents) <= settings.min_parent_for_rerank:
        logger.info(f"⏭️ Skipping Reranking: only {len(candidate_parents)} candidates (<= {settings.min_parent_for_rerank})")
        
        final_results = candidate_parents[: settings.rerank_top_n]
        # Pastikan ada key cross_encoder_score agar format seragam
        for p in final_results:
            p["cross_encoder_score"] = p.get("best_child_score", 0.0)
            
        t_rerank = time.time()
        logger.info(f"⏱️ [Retrieval Pipeline] Total: {t_rerank - t_start:.2f}s | "
                    f"Parse: {t_parse - t_start:.2f}s | "
                    f"Search: {t_search - t_parse:.2f}s | "
                    f"Fetch: {t_fetch - t_search:.2f}s | "
                    f"Rerank (Skipped): 0.00s")

        _record_final_retrieval_metrics(final_results, all_scored_candidates=candidate_parents)
        return RetrievalResult(parent_documents=final_results, is_empty=False)
```

> **Catatan (G5, ditambahkan setelah iterasi mockup ke-2):** parameter `all_scored_candidates=candidate_parents` di sini sengaja ditambahkan — di jalur skip-rerank ini skornya adalah `best_child_score` (bukan cross-encoder asli, karena reranker memang tidak dipanggil), jadi `retrieval_detail` hasil jalur ini akan otomatis ditandai berbasis skor fallback itu. Ini normal dan sudah ditangani oleh `_build_retrieval_detail()` di bagian 7.2 bawah.

**Cari (jalur reranking penuh, sampai akhir fungsi):**
```python
    try:
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query=rerank_query, documents=candidate_parents)
        
        if reranked:
            top_score = reranked[0].get("cross_encoder_score", 0.0)
            
            if top_score < settings.rerank_min_top_score:
                final_results = []
                reason = "Minimum Evidence Triggered"
            else:
                min_accepted_score = top_score - settings.rerank_relative_gap
                final_results = [
                    doc for doc in reranked 
                    if doc.get("cross_encoder_score", 0.0) >= min_accepted_score
                ][: settings.rerank_top_n]
                reason = "Adaptive Relative Gap"
        else:
            final_results = []
            reason = "No documents reranked"
            top_score = 0.0
            
    except Exception as e:
        logger.warning(f"Reranking failed, using unranked top-N: {e}")
        final_results = candidate_parents[: settings.rerank_top_n]
        reason = "Reranking Failed (Fallback)"
        top_score = final_results[0].get("best_child_score", 0.0) if final_results else 0.0
        
    t_rerank = time.time()
    
    summary_log = (
        f"\n========== Retrieval Summary ==========\n"
        f"Retrieved Parents : {len(candidate_parents)}\n"
        f"After Threshold   : {len(final_results)}\n"
        f"Top Score         : {top_score:.2f}\n"
        f"Reason            : {reason}\n"
        f"LLM Mode          : {'Conversation (Empty Context)' if not final_results else 'RAG'}\n"
        f"======================================="
    )
    logger.info(summary_log)
    
    logger.info(f"⏱️ [Retrieval Pipeline] Total: {t_rerank - t_start:.2f}s | "
                f"Parse: {t_parse - t_start:.2f}s | "
                f"Search: {t_search - t_parse:.2f}s | "
                f"Fetch: {t_fetch - t_search:.2f}s | "
                f"Rerank: {t_rerank - t_fetch:.2f}s")

    return RetrievalResult(parent_documents=final_results, is_empty=(len(final_results) == 0))
```

**Ganti dengan:**
```python
    start_stage("reranking")
    try:
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query=rerank_query, documents=candidate_parents)
        
        if reranked:
            top_score = reranked[0].get("cross_encoder_score", 0.0)
            
            if top_score < settings.rerank_min_top_score:
                final_results = []
                reason = "Minimum Evidence Triggered"
            else:
                min_accepted_score = top_score - settings.rerank_relative_gap
                final_results = [
                    doc for doc in reranked 
                    if doc.get("cross_encoder_score", 0.0) >= min_accepted_score
                ][: settings.rerank_top_n]
                reason = "Adaptive Relative Gap"
        else:
            final_results = []
            reason = "No documents reranked"
            top_score = 0.0
            
    except Exception as e:
        logger.warning(f"Reranking failed, using unranked top-N: {e}")
        final_results = candidate_parents[: settings.rerank_top_n]
        reason = "Reranking Failed (Fallback)"
        top_score = final_results[0].get("best_child_score", 0.0) if final_results else 0.0
    end_stage()

    t_rerank = time.time()
    
    summary_log = (
        f"\n========== Retrieval Summary ==========\n"
        f"Retrieved Parents : {len(candidate_parents)}\n"
        f"After Threshold   : {len(final_results)}\n"
        f"Top Score         : {top_score:.2f}\n"
        f"Reason            : {reason}\n"
        f"LLM Mode          : {'Conversation (Empty Context)' if not final_results else 'RAG'}\n"
        f"======================================="
    )
    logger.info(summary_log)
    
    logger.info(f"⏱️ [Retrieval Pipeline] Total: {t_rerank - t_start:.2f}s | "
                f"Parse: {t_parse - t_start:.2f}s | "
                f"Search: {t_search - t_parse:.2f}s | "
                f"Fetch: {t_fetch - t_search:.2f}s | "
                f"Rerank: {t_rerank - t_fetch:.2f}s")

    _record_final_retrieval_metrics(final_results, all_scored_candidates=(reranked if reranked else candidate_parents))
    return RetrievalResult(parent_documents=final_results, is_empty=(len(final_results) == 0))
```

**Tambahkan fungsi helper baru di akhir file** (dipakai oleh kedua jalur di atas — reranked & skipped):
```python
def _record_final_retrieval_metrics(
    final_results: list[dict],
    all_scored_candidates: list[dict] | None = None,
) -> None:
    """Kirim skor cross-encoder & daftar parent_id akhir ke metrics collector.
    Dipanggil di kedua jalur (reranking penuh maupun adaptive-skip).

    `all_scored_candidates` (G5, Fase 10): SEMUA kandidat yang sempat diberi
    skor SEBELUM di-threshold — dipakai untuk retrieval_detail supaya admin
    bisa lihat "kenapa dokumen X tidak lolos" (skornya berapa), bukan cuma
    yang lolos akhir. Kalau tidak diisi, fallback pakai final_results saja.
    """
    accepted_ids = {p.get("parent_id", "") for p in final_results}
    candidates_for_detail = all_scored_candidates if all_scored_candidates is not None else final_results

    if not final_results:
        set_field(
            is_no_relevant_doc=True,
            num_docs_after_rerank=0,
            retrieved_parent_ids=[],
            retrieval_detail=_build_retrieval_detail(candidates_for_detail, accepted_ids),
        )
        return

    scores = [p.get("cross_encoder_score", 0.0) for p in final_results]
    set_field(
        is_no_relevant_doc=False,
        num_docs_after_rerank=len(final_results),
        top_cross_encoder_score=max(scores) if scores else None,
        avg_cross_encoder_score=(sum(scores) / len(scores)) if scores else None,
        retrieved_parent_ids=[p.get("parent_id", "") for p in final_results],
        retrieval_detail=_build_retrieval_detail(candidates_for_detail, accepted_ids),
    )


def _build_retrieval_detail(candidates: list[dict], accepted_ids: set[str]) -> list[dict]:
    """(G5, Fase 10) Bentuk struktur ringkas untuk kolom JSONB retrieval_detail —
    dipakai fitur 'detail cross-encoder per pertanyaan' di admin panel.
    Skor diambil dari cross_encoder_score kalau ada (jalur reranking penuh),
    fallback ke best_child_score (jalur adaptive-skip, lihat catatan di atas)."""
    return [
        {
            "parent_id": c.get("parent_id", ""),
            "title": c.get("title") or c.get("section") or "",
            "score": round(c.get("cross_encoder_score", c.get("best_child_score", 0.0)), 4),
            "accepted": c.get("parent_id", "") in accepted_ids,
        }
        for c in candidates
    ]
```

> **Catatan soal C2 ("dokumen/source yang paling sering diambil"):** kolom `retrieved_parent_ids` (array) di atas menyimpan parent_id yang muncul di jawaban akhir tiap request. Untuk menghitung "dokumen paling sering diambil", query agregasinya memakai `unnest(retrieved_parent_ids)` — lihat view `v_top_retrieved_documents` di Fase 7.

### 7.3 Definition of Done — Fase 3
- [ ] Kirim chat dengan pertanyaan yang PASTI ada jawabannya di knowledge base → cek baris terbaru di `request_metrics`: `stage_embedding_ms`, `stage_retrieval_ms`, `stage_reranking_ms`, `stage_parent_assembly_ms` semua terisi angka > 0, `is_no_relevant_doc = false`, `domain_detected` terisi salah satu dari PI/KKP/SKRIPSI/NON_SKRIPSI/UNKNOWN
- [ ] Kirim chat dengan pertanyaan yang PASTI tidak nyambung dengan knowledge base (mis. "resep rendang") → `is_no_relevant_doc = true`, `num_docs_after_rerank = 0`
- [ ] (G5) Cek kolom `retrieval_detail` di baris manapun yang `num_docs_retrieved > 0` — harus berupa array JSON berisi minimal 1 object dengan key `parent_id`, `title`, `score`, `accepted`

---

## 8. FASE 4 — Instrumentasi generation & token/cost

Mengganti estimasi token via `tiktoken` dengan **actual usage** dari response OpenAI (`response.usage_metadata`, field resmi `langchain-openai` sejak beberapa versi terakhir — berisi `input_tokens`, `output_tokens`, `total_tokens`), dan menghitung cost.

### 8.1 File: `src/generation/chain.py`

**Cari (bagian import di atas):**
```python
from __future__ import annotations

import re
from typing import Iterator

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from operator import itemgetter

from config.settings import get_settings
from src.retrieval.source_utils import detect_panduan_type

settings = get_settings()
```

**Ganti dengan:**
```python
from __future__ import annotations

import re
from typing import Iterator

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from operator import itemgetter

from config.settings import get_settings
from src.retrieval.source_utils import detect_panduan_type
from src.monitoring.context import set_field
from src.monitoring.pricing import calculate_llm_cost
from src.monitoring.openai_client import build_instrumented_http_client

settings = get_settings()
```

**Cari (constructor `RAGChain.__init__`):**
```python
    def __init__(self):
        self._chain = build_rag_chain(streaming=False)
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.open_api_key,
            temperature=0,
        )
```

**Ganti dengan:**
```python
    def __init__(self):
        self._chain = build_rag_chain(streaming=False)
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.open_api_key,
            temperature=0,
            http_client=build_instrumented_http_client(),
        )
```

> Field `http_client=` di `ChatOpenAI` diteruskan ke `openai.OpenAI(...)` di baliknya — ini yang memungkinkan hitung retry di Fase 1 (5.7) bekerja tanpa perlu monkey-patch apapun.

**Cari (bagian akhir `invoke_with_history`, dari `response = self._llm.invoke(messages)` sampai `return result`):**
```python
        response = self._llm.invoke(messages)
        answer = _postprocess_answer(response.content)
        
        output_tokens = count_tokens(answer)
        total_input_tokens = system_tokens + history_tokens + context_tokens + query_tokens
        
        profile_log = (
            f"\n========== PROMPT PROFILE ==========\n"
            f"System Prompt     : {system_tokens} tokens\n"
            f"History           : {history_tokens} tokens\n"
            f"Retrieved Context : {context_tokens} tokens\n"
            f"User Query        : {query_tokens} tokens\n"
            f"------------------------------------\n"
            f"Total Input       : {total_input_tokens} tokens (approx)\n"
            f"Output            : {output_tokens} tokens\n"
            f"===================================="
        )
        logger.info(profile_log)

        result: dict[str, str | list] = {"answer": answer}

        if return_sources:
            result["sources"] = _build_sources(context_documents)

        logger.success(f"Generation complete: {len(answer)} chars")
        return result
```

**Ganti dengan:**
```python
        response = self._llm.invoke(messages)
        answer = _postprocess_answer(response.content)

        # Token usage AKTUAL dari OpenAI (bukan estimasi tiktoken lagi).
        # `usage_metadata` adalah field resmi langchain-openai berisi
        # {"input_tokens": int, "output_tokens": int, "total_tokens": int}.
        # Fallback ke estimasi tiktoken kalau field ini tidak tersedia
        # (mis. versi langchain-openai lama, atau provider non-OpenAI).
        usage = getattr(response, "usage_metadata", None)
        if usage:
            actual_input_tokens = usage.get("input_tokens")
            actual_output_tokens = usage.get("output_tokens")
        else:
            logger.warning("response.usage_metadata tidak tersedia, fallback ke estimasi tiktoken.")
            actual_input_tokens = system_tokens + history_tokens + context_tokens + query_tokens
            actual_output_tokens = count_tokens(answer)

        llm_cost = calculate_llm_cost(settings.llm_model, actual_input_tokens, actual_output_tokens)
        set_field(
            input_tokens=actual_input_tokens,
            output_tokens=actual_output_tokens,
            llm_cost_usd=llm_cost,
        )

        profile_log = (
            f"\n========== PROMPT PROFILE ==========\n"
            f"System Prompt     : {system_tokens} tokens (estimasi)\n"
            f"History           : {history_tokens} tokens (estimasi)\n"
            f"Retrieved Context : {context_tokens} tokens (estimasi)\n"
            f"User Query        : {query_tokens} tokens (estimasi)\n"
            f"------------------------------------\n"
            f"Input Aktual (API): {actual_input_tokens} tokens\n"
            f"Output Aktual (API): {actual_output_tokens} tokens\n"
            f"Cost              : ${llm_cost:.6f}\n"
            f"===================================="
        )
        logger.info(profile_log)

        result: dict[str, str | list] = {"answer": answer}

        if return_sources:
            result["sources"] = _build_sources(context_documents)

        logger.success(f"Generation complete: {len(answer)} chars")
        return result
```

### 8.2 Embedding token & cost

File: `src/retrieval/hybrid_search.py`. `OpenAIEmbeddings` dari `langchain-openai` **tidak selalu** mengembalikan usage metadata dengan mudah lewat method `.embed_query()` (method ini return `list[float]` polos, bukan objek dengan metadata). Daripada memaksakan cara yang fragile, pakai estimasi `tiktoken` yang sederhana khusus untuk token embedding (cukup akurat untuk keperluan cost tracking, tidak perlu presisi sampai token terakhir).

**Cari (constructor `HybridSearcher.__init__`):**
```python
    def __init__(self, supabase_client: Client | None = None):
        self._supabase = supabase_client or create_client(
            settings.supabase_url, settings.supabase_service_key
        )
        self._embedder = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
        )
```

**Ganti dengan:**
```python
    def __init__(self, supabase_client: Client | None = None):
        self._supabase = supabase_client or create_client(
            settings.supabase_url, settings.supabase_service_key
        )
        self._embedder = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
        )
```
*(tidak ada perubahan di constructor ini — biarkan seperti semula, `http_client` untuk retry counter di embedder ditambahkan terpisah di Fase 6 supaya Fase 4 fokus hanya ke token/cost)*

**Cari:**
```python
        start_stage("embedding")
        t0 = time.time()
        query_embedding = self._embedder.embed_query(query)
        t_embed = time.time() - t0
        end_stage()
        logger.info(f"  [Profile] Query Embedding: {t_embed:.2f}s")
```
*(ini hasil edit Fase 3 — pastikan Fase 3 sudah dikerjakan duluan)*

**Ganti dengan:**
```python
        import tiktoken
        from src.monitoring.pricing import calculate_embedding_cost

        start_stage("embedding")
        t0 = time.time()
        query_embedding = self._embedder.embed_query(query)
        t_embed = time.time() - t0
        end_stage()
        logger.info(f"  [Profile] Query Embedding: {t_embed:.2f}s")

        try:
            _enc = tiktoken.encoding_for_model("text-embedding-3-large")
        except Exception:
            _enc = tiktoken.get_encoding("cl100k_base")
        embed_tokens = len(_enc.encode(query))
        embed_cost = calculate_embedding_cost(settings.embedding_model, embed_tokens)
        set_field(embedding_tokens=embed_tokens, embedding_cost_usd=embed_cost)
```

Tambahkan import `set_field` di bagian atas file (dekat `start_stage, end_stage` yang sudah ditambahkan di Fase 3):
```python
from src.monitoring.context import start_stage, end_stage, set_field
```

### 8.3 Definition of Done — Fase 4
- [ ] Kirim satu chat, cek `request_metrics` terbaru: `input_tokens` dan `output_tokens` terisi angka masuk akal (ratusan-ribuan, BUKAN estimasi tiktoken lokal), `llm_cost_usd` > 0, `embedding_tokens` dan `embedding_cost_usd` terisi
- [ ] Cross-check manual: `llm_cost_usd` kira-kira = `(input_tokens/1_000_000 * 0.15) + (output_tokens/1_000_000 * 0.60)` kalau model = `gpt-4o-mini` (lihat `config/pricing.yaml`)

---

## 9. FASE 5 — Instrumentasi entrypoint (validation + quota rejection)

Mengisi `stage_validation_ms` dan mencatat baris `status='quota_rejected'` untuk **B4/E4**. Dikerjakan di KEDUA entrypoint (website & Telegram) karena keduanya melakukan pengecekan kuota SEBELUM memanggil `ai_services.chat()`.

### 9.1 File: `src/api/ai.py`

**Cari (bagian import di atas):**
```python
import unicodedata
import re
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from loguru import logger
from datetime import datetime

from src.services.ai_services import chat as chat_service
from src.services.quota_service import check_and_update_quota
from src.auth.jwt_utils import verify_access_token
from config.settings import get_settings
```

**Ganti dengan:**
```python
import unicodedata
import re
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from loguru import logger
from datetime import datetime

from src.services.ai_services import chat as chat_service
from src.services.quota_service import check_and_update_quota
from src.auth.jwt_utils import verify_access_token
from src.monitoring.context import new_collector, start_stage, end_stage
from src.monitoring.writer import persist_quota_rejection
from config.settings import get_settings
```

**Cari (fungsi `chat_endpoint` lengkap):**
```python
async def chat_endpoint(body: ChatRequest, request: Request):
    try:
        mahasiswa_id = None
        username = "Unknown User"
        
        # TAHAP 1: Cek Channel
        if body.channel == "telegram":
            raise HTTPException(
                status_code=403, 
                detail="Akses chat Telegram murni diproses melalui Webhook internal."
            )
            
        elif body.channel == "website":
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Token Authorization (Bearer) diperlukan")
                
            token = auth_header.split(" ")[1]
            payload = verify_access_token(token)
            
            # Forward compatibility untuk Increment 3
            if payload.get("role") != "mahasiswa":
                raise HTTPException(status_code=403, detail="Akses ditolak: role tidak sesuai")
                
            mahasiswa_id = payload.get("sub")
            username = payload.get("name", "Website User")
            
            if not mahasiswa_id:
                raise HTTPException(status_code=401, detail="Token tidak valid: sub (mahasiswa_id) tidak ditemukan")

        # TAHAP 2: Cek Kuota
        if mahasiswa_id:
            quota_allowed = check_and_update_quota(
                user_id=str(mahasiswa_id),
                daily_limit=settings.RATE_LIMIT_REQUESTS
            )
            
            if not quota_allowed:
                raise HTTPException(
                    status_code=429, 
                    detail=f"Batas harian mencapai batas. Maksimal {settings.RATE_LIMIT_REQUESTS} pertanyaan per hari."
                )

        # TAHAP 3: Teruskan ke Chat Service
        result = chat_service(
            query=body.query,
            session_id=body.session_id,
            username=username,
            channel=body.channel,
            mahasiswa_id=mahasiswa_id
        )
        
        return ChatResponse(
            answer=result["answer"],
            num_docs=result["num_docs"],
            session_id=body.session_id,
            sources=result.get("sources", []),
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            reasoning=result.get("reasoning"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Endpoint /chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Ganti dengan:**
```python
async def chat_endpoint(body: ChatRequest, request: Request):
    # G1/G4/G6: `question` diisi di sini, TITIK PALING AWAL yang mungkin —
    # supaya tetap tercatat walau request gagal di validasi/kuota/generation.
    collector = new_collector(session_id=body.session_id, channel=body.channel, question=body.query)
    start_stage("validation")
    try:
        mahasiswa_id = None
        username = "Unknown User"
        
        # TAHAP 1: Cek Channel
        if body.channel == "telegram":
            raise HTTPException(
                status_code=403, 
                detail="Akses chat Telegram murni diproses melalui Webhook internal."
            )
            
        elif body.channel == "website":
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Token Authorization (Bearer) diperlukan")
                
            token = auth_header.split(" ")[1]
            payload = verify_access_token(token)
            
            # Forward compatibility untuk Increment 3
            if payload.get("role") != "mahasiswa":
                raise HTTPException(status_code=403, detail="Akses ditolak: role tidak sesuai")
                
            mahasiswa_id = payload.get("sub")
            username = payload.get("name", "Website User")
            
            if not mahasiswa_id:
                raise HTTPException(status_code=401, detail="Token tidak valid: sub (mahasiswa_id) tidak ditemukan")

        collector.mahasiswa_id = str(mahasiswa_id) if mahasiswa_id else None
        collector.username = username  # G3: siapa yang mengalami error, kalau nanti gagal di bawah
        end_stage()  # menutup "validation" — kuota & chat_service TIDAK dihitung sebagai validation

        # TAHAP 2: Cek Kuota
        if mahasiswa_id:
            quota_allowed = check_and_update_quota(
                user_id=str(mahasiswa_id),
                daily_limit=settings.RATE_LIMIT_REQUESTS
            )
            
            if not quota_allowed:
                persist_quota_rejection(
                    session_id=body.session_id,
                    channel=body.channel,
                    mahasiswa_id=str(mahasiswa_id),
                )
                raise HTTPException(
                    status_code=429, 
                    detail=f"Batas harian mencapai batas. Maksimal {settings.RATE_LIMIT_REQUESTS} pertanyaan per hari."
                )

        # TAHAP 3: Teruskan ke Chat Service
        # (chat_service akan memakai collector yang sudah kita buat di atas
        # via get_current() — lihat Fase 2 — dan yang akan mem-persist +
        # menutup collector ini di akhir.)
        result = chat_service(
            query=body.query,
            session_id=body.session_id,
            username=username,
            channel=body.channel,
            mahasiswa_id=mahasiswa_id
        )
        
        return ChatResponse(
            answer=result["answer"],
            num_docs=result["num_docs"],
            session_id=body.session_id,
            sources=result.get("sources", []),
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            reasoning=result.get("reasoning"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Endpoint /chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

> **Catatan desain:** `end_stage()` untuk "validation" sengaja dipanggil SETELAH auth+role check tapi SEBELUM quota check, supaya waktu quota check (network round-trip ke Supabase RPC) tidak ikut kehitung sebagai "validation" murni. Kalau ingin quota check juga masuk hitungan validation, pindahkan `end_stage()` ke tepat sebelum komentar `# TAHAP 3`.

### 9.2 File: `src/bot/handlers/chat_handler.py`

**Cari (bagian import di atas):**
```python
import asyncio
import html
from datetime import datetime
from functools import lru_cache
from loguru import logger

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters

from config.settings import get_settings
from src.bot import messages
from src.retrieval.source_utils import detect_panduan_type
from src.services.ai_services import chat
from src.services.quota_service import check_and_update_quota
```

**Ganti dengan:**
```python
import asyncio
import html
from datetime import datetime
from functools import lru_cache
from loguru import logger

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters

from config.settings import get_settings
from src.bot import messages
from src.retrieval.source_utils import detect_panduan_type
from src.services.ai_services import chat
from src.services.quota_service import check_and_update_quota
from src.monitoring.context import new_collector, start_stage, end_stage
from src.monitoring.writer import persist_quota_rejection
```

**Cari:**
```python
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    settings = get_settings()

    # Cek limit harian sebelum memproses pertanyaan.
    # Supabase client adalah sync, jalankan di thread pool agar event loop tidak terblokir.
    has_quota = await asyncio.to_thread(check_and_update_quota, user_id)
    if not has_quota:
        await update.message.reply_text(
            messages.DAILY_LIMIT_REACHED.format(limit=settings.RATE_LIMIT_REQUESTS),
            parse_mode=ParseMode.HTML,
        )
        return
```

**Ganti dengan:**
```python
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    settings = get_settings()

    # G1/G4/G6: `question` (variabel `text`, sudah divalidasi non-kosong di
    # baris sebelum blok ini) diisi di sini — titik paling awal yang mungkin.
    collector = new_collector(session_id=user_id, channel="telegram", question=text)
    start_stage("validation")
    end_stage()

    # Cek limit harian sebelum memproses pertanyaan.
    # Supabase client adalah sync, jalankan di thread pool agar event loop tidak terblokir.
    has_quota = await asyncio.to_thread(check_and_update_quota, user_id)
    if not has_quota:
        await asyncio.to_thread(
            persist_quota_rejection,
            session_id=user_id,
            channel="telegram",
            mahasiswa_id=None,
        )
        await update.message.reply_text(
            messages.DAILY_LIMIT_REACHED.format(limit=settings.RATE_LIMIT_REQUESTS),
            parse_mode=ParseMode.HTML,
        )
        return
```

> **Catatan penting untuk Telegram (async):** `contextvars.ContextVar` di Python secara default **otomatis ter-copy dengan benar** ke dalam `asyncio.to_thread()` maupun task async lain SELAMA context itu di-set di coroutine yang sama sebelum `await`. Kode di atas sudah mengikuti pola itu (collector dibuat di `handle_text_chat`, dipakai lewat `asyncio.to_thread(chat, ...)` yang memanggil `ai_services.chat()` — `get_current()` di dalam `chat()` akan tetap menemukan collector yang sama). **Tidak perlu** passing collector secara manual sebagai argumen.

### 9.3 Definition of Done — Fase 5
- [ ] Set `RATE_LIMIT_REQUESTS=1` sementara di `.env` (lokal/staging saja, JANGAN di production), kirim 2 chat berturut-turut dari user yang sama → chat ke-2 harus ditolak DAN muncul baris baru di `request_metrics` dengan `status='quota_rejected'`
- [ ] Kembalikan `RATE_LIMIT_REQUESTS` ke nilai semula setelah tes
- [ ] (G1/G4/G6) Kirim chat dari website DAN dari Telegram → cek kolom `question` di `request_metrics` terisi teks pertanyaan asli di KEDUA baris

---

## 10. FASE 6 — Error taxonomy & retry counter di semua titik panggilan OpenAI

Ada **4 titik panggilan OpenAI** berbeda di codebase ini (generation, intent classification, query reformulation, embedding). Supaya B3 (retry rate) dan B2 (error by source) akurat di SEMUA titik, bukan cuma di generation (yang sudah diinstrumentasi di Fase 4), pasang `http_client=build_instrumented_http_client()` di titik-titik lain juga.

### 10.1 File: `src/generation/intent_classifier/classifier.py`

Cari konstruksi `ChatOpenAI(...)` di `IntentClassifier.__init__` (sekitar baris 49) dan tambahkan parameter `http_client`:

**Cari:**
```python
        self._llm = ChatOpenAI(
            model=settings.llm_model,
```

**Ganti dengan:**
```python
        from src.monitoring.openai_client import build_instrumented_http_client
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            http_client=build_instrumented_http_client(),
```

> Sesuaikan indentasi persis dengan parameter lain di constructor yang sama — lihat argumen-argumen lain (`api_key=...`, dst) yang sudah ada persis di bawah baris `model=settings.llm_model,` itu, jangan dihapus, cuma ditambah satu baris baru.

### 10.2 File: `src/generation/intent_classifier/reformulator.py`

Sama, cari `ChatOpenAI(` di `QueryReformulator.__init__` (sekitar baris 48) dan tambahkan `http_client=build_instrumented_http_client()` dengan pola yang sama seperti 10.1.

### 10.3 File: `src/retrieval/hybrid_search.py` (embedder)

**Cari:**
```python
        self._embedder = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
        )
```

**Ganti dengan:**
```python
        from src.monitoring.openai_client import build_instrumented_http_client
        self._embedder = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
            dimensions=EMBEDDING_DIMENSIONS,
            http_client=build_instrumented_http_client(),
        )
```

### 10.4 Verifikasi taksonomi error di titik-titik non-OpenAI

`classify_exception()` (Fase 1, 5.3) sudah otomatis mengklasifikasikan exception dari modul `openai.*`, `postgrest.*`, `supabase.*`, `httpx.*` berdasarkan nama modul exception-nya — **tidak perlu** membungkus setiap `try/except` di seluruh codebase secara manual. Titik tangkap utama tetap satu: blok `except Exception as e` di `ai_services.chat()` (Fase 2), yang memanggil `classify_exception(e)`.

Kalau di masa depan ingin klasifikasi lebih presisi di titik spesifik (mis. membedakan `RateLimitError` OpenAI dari `APIError` OpenAI biasa), raise `RateLimitServiceError` (dari `src.monitoring.errors`) secara eksplisit di titik yang relevan — polanya:
```python
from openai import RateLimitError
from src.monitoring.errors import RateLimitServiceError

try:
    ...
except RateLimitError as e:
    raise RateLimitServiceError(str(e)) from e
```

### 10.5 Definition of Done — Fase 6
- [ ] Cek dengan sengaja memasukkan `OPEN_API_KEY` yang salah/expired sementara di `.env` lokal, kirim chat → `request_metrics.error_source` harus `'openai'` (bukan `'unknown'`)
- [ ] Kembalikan API key yang benar setelah tes

---

## 11. FASE 7 — SQL views agregasi

File baru: `scripts/supabase_migration_observability_views.sql`. Jalankan SETELAH Fase 0-6 sudah berjalan dan sudah ada data asli masuk ke `request_metrics` (views ini tidak butuh data untuk dibuat, tapi lebih mudah divalidasi kalau sudah ada data).

```sql
-- ============================================================
-- Views agregasi untuk dashboard monitoring.
-- Semua view ini read-only, aman dijalankan berkali-kali (CREATE OR REPLACE).
-- ============================================================

-- A1, A3: Latency percentile + throughput per jam
CREATE OR REPLACE VIEW v_latency_stats_hourly AS
SELECT
    date_trunc('hour', created_at) AS bucket,
    channel,
    count(*)                                                       AS total_requests,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY total_ms)         AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY total_ms)         AS p95_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY total_ms)         AS p99_ms,
    round(avg(total_ms), 2)                                        AS avg_ms
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC;

-- A2: Rata-rata durasi tiap tahap pipeline per hari
CREATE OR REPLACE VIEW v_stage_breakdown_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    round(avg(stage_validation_ms), 2)      AS avg_validation_ms,
    round(avg(stage_session_load_ms), 2)    AS avg_session_load_ms,
    round(avg(stage_reformulation_ms), 2)   AS avg_reformulation_ms,
    round(avg(stage_embedding_ms), 2)       AS avg_embedding_ms,
    round(avg(stage_retrieval_ms), 2)       AS avg_retrieval_ms,
    round(avg(stage_reranking_ms), 2)       AS avg_reranking_ms,
    round(avg(stage_parent_assembly_ms), 2) AS avg_parent_assembly_ms,
    round(avg(stage_generation_ms), 2)      AS avg_generation_ms,
    round(avg(stage_db_save_ms), 2)         AS avg_db_save_ms
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- B1, B4: Error rate & quota rejection rate per hari
CREATE OR REPLACE VIEW v_error_stats_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    count(*)                                                                   AS total_requests,
    count(*) FILTER (WHERE status = 'error')                                   AS error_count,
    count(*) FILTER (WHERE status = 'quota_rejected')                          AS quota_rejected_count,
    round(100.0 * count(*) FILTER (WHERE status = 'error') / NULLIF(count(*), 0), 2)           AS error_rate_pct,
    round(100.0 * count(*) FILTER (WHERE status = 'quota_rejected') / NULLIF(count(*), 0), 2)  AS quota_rejection_rate_pct
FROM request_metrics
GROUP BY 1
ORDER BY 1 DESC;

-- B2: Breakdown error by source
CREATE OR REPLACE VIEW v_error_breakdown_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    coalesce(error_source, 'unknown') AS error_source,
    count(*) AS error_count
FROM request_metrics
WHERE status = 'error'
GROUP BY 1, 2
ORDER BY 1 DESC, error_count DESC;

-- B3: Retry rate ke OpenAI (rata-rata retry per request, dan % request yang butuh >=1 retry)
CREATE OR REPLACE VIEW v_openai_retry_stats_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    round(avg(openai_retry_count), 3)                                                 AS avg_retry_per_request,
    round(100.0 * count(*) FILTER (WHERE openai_retry_count > 0) / NULLIF(count(*), 0), 2) AS pct_requests_with_retry
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- C1, C3, C4: Kualitas retrieval per hari
CREATE OR REPLACE VIEW v_retrieval_quality_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    count(*)                                                                        AS total_queries,
    count(*) FILTER (WHERE is_no_relevant_doc)                                      AS no_relevant_doc_count,
    round(100.0 * count(*) FILTER (WHERE is_no_relevant_doc) / NULLIF(count(*), 0), 2) AS no_relevant_doc_pct,
    round(avg(num_docs_after_rerank), 2)                                             AS avg_docs_after_rerank,
    round(avg(top_cross_encoder_score), 4)                                           AS avg_top_score,
    round(avg(avg_cross_encoder_score), 4)                                           AS avg_score_all_docs
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- C2: Dokumen (parent_id) paling sering diambil
CREATE OR REPLACE VIEW v_top_retrieved_documents AS
SELECT
    parent_id,
    count(*) AS times_retrieved
FROM request_metrics, unnest(retrieved_parent_ids) AS parent_id
WHERE status = 'success'
GROUP BY 1
ORDER BY times_retrieved DESC;

-- C5: Breakdown query per domain — mana paling sering ditanya & paling sering gagal retrieval
CREATE OR REPLACE VIEW v_domain_stats_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    coalesce(domain_detected, 'UNKNOWN') AS domain,
    count(*)                                                                     AS total_queries,
    count(*) FILTER (WHERE is_no_relevant_doc)                                   AS failed_retrieval_count,
    round(100.0 * count(*) FILTER (WHERE is_no_relevant_doc) / NULLIF(count(*), 0), 2) AS failed_retrieval_pct
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC, total_queries DESC;

-- D2, D3: Cost harian, cost per request
CREATE OR REPLACE VIEW v_cost_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    round(sum(llm_cost_usd), 6)                                          AS total_llm_cost_usd,
    round(sum(embedding_cost_usd), 6)                                    AS total_embedding_cost_usd,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)), 6) AS total_cost_usd,
    count(*)                                                              AS total_requests,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)) / NULLIF(count(*), 0), 6) AS cost_per_request_usd
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- D3: Cost per user (mahasiswa)
CREATE OR REPLACE VIEW v_cost_per_user AS
SELECT
    mahasiswa_id,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)), 6) AS total_cost_usd,
    count(*)                                                                    AS total_requests
FROM request_metrics
WHERE status = 'success' AND mahasiswa_id IS NOT NULL
GROUP BY 1
ORDER BY total_cost_usd DESC;

-- D3: Cost per session
CREATE OR REPLACE VIEW v_cost_per_session AS
SELECT
    session_id,
    round(sum(coalesce(llm_cost_usd, 0) + coalesce(embedding_cost_usd, 0)), 6) AS total_cost_usd,
    count(*)                                                                    AS total_requests
FROM request_metrics
WHERE status = 'success' AND session_id IS NOT NULL
GROUP BY 1
ORDER BY total_cost_usd DESC;

-- E1, E3: Active users harian per channel (proxy: mahasiswa_id kalau ada, kalau tidak pakai session_id — berlaku untuk Telegram)
CREATE OR REPLACE VIEW v_active_users_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    channel,
    count(DISTINCT coalesce(mahasiswa_id, session_id)) AS active_users
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC;

-- E1: Active users bulanan
CREATE OR REPLACE VIEW v_active_users_monthly AS
SELECT
    date_trunc('month', created_at) AS month,
    channel,
    count(DISTINCT coalesce(mahasiswa_id, session_id)) AS active_users
FROM request_metrics
WHERE status = 'success'
GROUP BY 1, 2
ORDER BY 1 DESC;

-- E2: Sesi baru vs lanjutan per hari
CREATE OR REPLACE VIEW v_session_first_seen AS
SELECT
    session_id,
    min(created_at) AS first_seen
FROM request_metrics
WHERE status = 'success' AND session_id IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE VIEW v_new_vs_returning_daily AS
SELECT
    date_trunc('day', rm.created_at) AS day,
    count(*) FILTER (
        WHERE date_trunc('day', fs.first_seen) = date_trunc('day', rm.created_at)
    ) AS requests_from_new_sessions,
    count(*) FILTER (
        WHERE date_trunc('day', fs.first_seen) < date_trunc('day', rm.created_at)
    ) AS requests_from_returning_sessions
FROM request_metrics rm
JOIN v_session_first_seen fs ON fs.session_id = rm.session_id
WHERE rm.status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- E2: Rata-rata turn (request) per sesi per hari
CREATE OR REPLACE VIEW v_avg_turns_per_session_daily AS
SELECT
    day,
    round(avg(turns_per_session), 2) AS avg_turns_per_session
FROM (
    SELECT
        date_trunc('day', created_at) AS day,
        session_id,
        count(*) AS turns_per_session
    FROM request_metrics
    WHERE status = 'success' AND session_id IS NOT NULL
    GROUP BY 1, 2
) t
GROUP BY 1
ORDER BY 1 DESC;

-- E5: Repeat/follow-up question rate (proxy via rewrite_method — lihat catatan di bawah)
CREATE OR REPLACE VIEW v_followup_rate_daily AS
SELECT
    date_trunc('day', created_at) AS day,
    count(*) FILTER (WHERE rewrite_method IS NOT NULL AND rewrite_method <> 'None') AS followup_count,
    count(*)                                                                         AS total_requests,
    round(100.0 * count(*) FILTER (WHERE rewrite_method IS NOT NULL AND rewrite_method <> 'None') / NULLIF(count(*), 0), 2) AS followup_rate_pct
FROM request_metrics
WHERE status = 'success'
GROUP BY 1
ORDER BY 1 DESC;

-- F3: Aktivitas admin (chunk edit + re-embed) — tabel chunk_edit_logs SUDAH ADA,
-- ini cuma view agregasi di atasnya, join ke admin_users untuk nama admin.
CREATE OR REPLACE VIEW v_admin_activity_daily AS
SELECT
    date_trunc('day', cel.edited_at) AS day,
    au.username                      AS admin_username,
    count(*)                                              AS total_edits,
    count(*) FILTER (WHERE cel.status = 'success')        AS successful_reembeds,
    count(*) FILTER (WHERE cel.status = 'failed')          AS failed_reembeds,
    count(*) FILTER (WHERE cel.status IN ('pending', 'processing')) AS in_progress
FROM chunk_edit_logs cel
LEFT JOIN admin_users au ON au.admin_id = cel.admin_id
GROUP BY 1, 2
ORDER BY 1 DESC;
```

> **Catatan soal E5 (repeat/follow-up rate):** `rewrite_method` (`None`/`Rule`/`LLM`, lihat `src/generation/intent_classifier/reformulator.py`) menandai apakah sistem mendeteksi pertanyaan sebagai lanjutan dari konteks sebelumnya. ini **proxy**, bukan definisi sempurna dari "user bertanya ulang karena jawaban kurang jelas" — proxy ini menangkap "pertanyaan yang bergantung secara linguistik pada percakapan sebelumnya" (co-reference, elipsis), bukan "user tidak puas dengan jawaban". Kalau ke depan mau definisi yang lebih tajam (mis. user bertanya hal yang MIRIP dalam N menit di sesi yang sama), itu perlu logic tambahan berbasis similarity antar `question` di `chat_logs` — di luar cakupan fase ini, catat sebagai future work di bagian 14.

### 11.1 Definition of Done — Fase 7
- [ ] `select * from v_latency_stats_hourly limit 5;` mengembalikan baris dengan `p50_ms`, `p95_ms`, `p99_ms` terisi
- [ ] `select * from v_domain_stats_daily;` mengembalikan baris per domain
- [ ] `select * from v_admin_activity_daily;` berjalan tanpa error (boleh kosong kalau belum pernah ada edit chunk)

---

## 12. FASE 8 — API endpoint admin untuk membaca metrics

### 12.1 File baru: `src/api/admin_metrics.py`

Mengikuti pola auth yang sama seperti `src/api/admin.py` (dependency `get_current_admin`).

```python
"""
Endpoint admin untuk membaca hasil agregasi monitoring (views dari Fase 7).
Semua endpoint di sini read-only dan butuh autentikasi admin.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Query
from supabase import Client, create_client

from config.settings import get_settings
from src.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/metrics", tags=["Admin Metrics"])


@lru_cache(maxsize=1)
def _get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _select_view(view_name: str, days: int, order_col: str = "day") -> list[dict[str, Any]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = _get_supabase_client()
    # Semua view punya kolom "day" atau "bucket" sebagai penanda waktu.
    query = client.table(view_name).select("*")
    try:
        query = query.gte(order_col, since)
    except Exception:
        pass
    response = query.execute()
    return response.data or []


@router.get("/latency", summary="A1/A3: latency percentile & throughput per jam")
async def get_latency_stats(days: int = Query(default=7, ge=1, le=90), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_latency_stats_hourly", days, order_col="bucket")}


@router.get("/stage-breakdown", summary="A2: rata-rata durasi tiap tahap pipeline per hari")
async def get_stage_breakdown(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_stage_breakdown_daily", days)}


@router.get("/errors", summary="B1/B4: error rate & quota rejection rate per hari")
async def get_error_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_error_stats_daily", days)}


@router.get("/errors/breakdown", summary="B2: breakdown error by source")
async def get_error_breakdown(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_error_breakdown_daily", days)}


@router.get("/openai-retry", summary="B3: retry rate ke OpenAI")
async def get_openai_retry_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_openai_retry_stats_daily", days)}


@router.get("/retrieval-quality", summary="C1/C3/C4: kualitas retrieval per hari")
async def get_retrieval_quality(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_retrieval_quality_daily", days)}


@router.get("/top-documents", summary="C2: dokumen paling sering diambil")
async def get_top_documents(limit: int = Query(default=20, ge=1, le=100), admin: dict = Depends(get_current_admin)):
    client = _get_supabase_client()
    response = client.table("v_top_retrieved_documents").select("*").limit(limit).execute()
    return {"data": response.data or []}


@router.get("/domain-stats", summary="C5: breakdown query per domain")
async def get_domain_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_domain_stats_daily", days)}


@router.get("/cost", summary="D2/D3: cost harian & cost per request")
async def get_cost_stats(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_cost_daily", days)}


@router.get("/cost/per-user", summary="D3: cost per user")
async def get_cost_per_user(limit: int = Query(default=50, ge=1, le=500), admin: dict = Depends(get_current_admin)):
    client = _get_supabase_client()
    response = client.table("v_cost_per_user").select("*").limit(limit).execute()
    return {"data": response.data or []}


@router.get("/usage/active-users", summary="E1: active users harian/bulanan per channel")
async def get_active_users(
    granularity: str = Query(default="daily", pattern="^(daily|monthly)$"),
    days: int = Query(default=30, ge=1, le=365),
    admin: dict = Depends(get_current_admin),
):
    view_name = "v_active_users_daily" if granularity == "daily" else "v_active_users_monthly"
    order_col = "day" if granularity == "daily" else "month"
    return {"data": _select_view(view_name, days, order_col=order_col)}


@router.get("/usage/sessions", summary="E2: sesi baru vs lanjutan, avg turn per sesi")
async def get_session_usage(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {
        "new_vs_returning": _select_view("v_new_vs_returning_daily", days),
        "avg_turns_per_session": _select_view("v_avg_turns_per_session_daily", days),
    }


@router.get("/usage/followup-rate", summary="E5: repeat/follow-up question rate")
async def get_followup_rate(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_followup_rate_daily", days)}


@router.get("/system", summary="F1: active session vs MAX_ACTIVE_SESSIONS + cleanup stats")
async def get_system_stats(admin: dict = Depends(get_current_admin)):
    from src.services.ai_services import get_session_stats

    settings = get_settings()
    stats = get_session_stats()
    active = stats.get("active_sessions") or stats.get("total_sessions") or 0
    return {
        "session_stats": stats,
        "max_active_sessions": settings.MAX_ACTIVE_SESSIONS,
        "utilization_pct": round(100.0 * active / settings.MAX_ACTIVE_SESSIONS, 2) if settings.MAX_ACTIVE_SESSIONS else None,
    }


@router.get("/admin-activity", summary="F3: audit trail chunk edit & re-embed")
async def get_admin_activity(days: int = Query(default=30, ge=1, le=180), admin: dict = Depends(get_current_admin)):
    return {"data": _select_view("v_admin_activity_daily", days)}
```

> **Catatan:** endpoint di atas memakai `client.table(view_name).select("*")` — Supabase Python client bisa query VIEW dengan cara yang sama seperti table biasa, selama `service_role` key yang dipakai (yang memang selalu dipakai backend project ini) punya akses baca. Kalau ternyata view butuh permission tambahan, jalankan `GRANT SELECT ON <nama_view> TO service_role, anon, authenticated;` untuk tiap view yang dibuat di Fase 7.

### 12.2 Registrasi router baru

**File:** `application.py`

**Cari:**
```python
from config.settings import get_settings
from src.bot.application import create_bot, post_init
from src.api import ai
from src.api import health as health_router
from src.api import auth
from src.api import sessions
from src.api import admin
```

**Ganti dengan:**
```python
from config.settings import get_settings
from src.bot.application import create_bot, post_init
from src.api import ai
from src.api import health as health_router
from src.api import auth
from src.api import sessions
from src.api import admin
from src.api import admin_metrics
```

**Cari:**
```python
def _register_routers(app: FastAPI):
    API_PREFIX = "/api"

    app.include_router(ai.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(sessions.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    app.include_router(health_router.router)
```

**Ganti dengan:**
```python
def _register_routers(app: FastAPI):
    API_PREFIX = "/api"

    app.include_router(ai.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(sessions.router, prefix=API_PREFIX)
    app.include_router(admin.router, prefix=API_PREFIX)
    app.include_router(admin_metrics.router, prefix=API_PREFIX)
    app.include_router(health_router.router)
```

### 12.3 Definition of Done — Fase 8
- [ ] Login sebagai admin (dapatkan JWT dari `/api/admin/login` yang sudah ada), lalu `GET /api/admin/metrics/latency` dengan header `Authorization: Bearer <token>` → response 200 dengan JSON berisi data
- [ ] `GET /api/admin/metrics/system` mengembalikan `active_sessions`, `max_active_sessions`, `utilization_pct`
- [ ] Endpoint tanpa token → 401

---

## 13. FASE 9 (opsional, di luar cakupan detail dokumen ini) — Dashboard frontend

Setelah Fase 0-8 selesai, semua data sudah bisa diakses lewat REST API (`/api/admin/metrics/*`). Langkah selanjutnya (dashboard visual di admin panel Next.js — folder `frontend/src/app/admin/`) adalah pekerjaan **frontend murni**: fetch dari endpoint-endpoint di atas, render dengan chart library (mis. `recharts`, yang sudah lazim dipakai di ekosistem Next.js). Ini sengaja tidak dirinci di dokumen ini karena scope-nya besar dan lebih baik dibuatkan dokumen rencana terpisah setelah backend (Fase 0-8) terverifikasi jalan dengan data asli.

---

## 14. FASE 10 — Investigasi & drill-down (G1-G6)

**Ditambahkan setelah iterasi kedua mockup UI**, yang menunjukkan kebutuhan untuk mengklik dari angka agregat turun ke data mentah per-request (lihat tabel 2.1). Fase ini **melengkapi**, bukan menggantikan, Fase 0/1/2/3/5/8 — kalau Anda mengerjakan fase-fase itu dari dokumen versi ini, perubahan G1-G6 SUDAH menyatu di dalamnya (kolom `question`/`username`/`retrieval_detail`, pemanggilan `_record_final_retrieval_metrics` yang sudah diperbarui, dst). Bagian ini isinya cuma 2 hal yang BELUM masuk ke fase manapun di atas: (1) satu titik instrumentasi tersisa di `chat_handler.py`, dan (2) endpoint admin baru untuk drill-down-nya sendiri.

### 14.1 File: `src/bot/handlers/chat_handler.py` — lengkapi `username`

Fase 5 sudah mengisi `collector.question` di awal fungsi. Tapi variabel `username` di Telegram baru diketahui **lebih belakangan** (dalam blok `try`, setelah pesan loading dikirim) — jadi perlu di-set menyusul di titik itu.

**Cari:**
```python
        username = update.effective_user.username or update.effective_user.full_name or "Unknown"
        response = await asyncio.to_thread(
            chat,
            query=text,
            session_id=user_id,
            username=username,
            channel="telegram",
            mahasiswa_id=None
        )
```

**Ganti dengan:**
```python
        username = update.effective_user.username or update.effective_user.full_name or "Unknown"
        collector.username = username  # G3: siapa yang mengalami error, kalau nanti gagal di bawah
        response = await asyncio.to_thread(
            chat,
            query=text,
            session_id=user_id,
            username=username,
            channel="telegram",
            mahasiswa_id=None
        )
```

> **Ingat keterbatasan yang sudah disebut sebelumnya:** untuk channel Telegram, `mahasiswa_id` SELALU `None` — tidak ada penghubung ke akun mahasiswa manapun di sistem saat ini. Jadi "akun siapa" untuk error dari Telegram cuma akan menunjukkan **username Telegram**, bukan identitas mahasiswa terverifikasi. Ini bukan bug di rencana ini, tapi keterbatasan model auth yang sudah ada — kalau butuh identitas mahasiswa juga untuk Telegram, itu perlu fitur linking akun terpisah (di luar cakupan dokumen ini).

### 14.2 File: `src/api/admin_metrics.py` — endpoint investigasi baru

Tambahkan 4 endpoint baru di **akhir file** (setelah `get_admin_activity` yang sudah ada dari Fase 8). Endpoint-endpoint ini query langsung ke tabel `request_metrics` (bukan ke view agregasi) karena tujuannya menampilkan baris mentah untuk di-drill-down, bukan angka ringkasan.

Pertama, perbarui baris import paling atas file (dibutuhkan untuk endpoint `request-detail` yang bisa 404):

**Cari:**
```python
from fastapi import APIRouter, Depends, Query
```

**Ganti dengan:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

Lalu tambahkan di akhir file:

```python
# ============================================================
# G1-G6 (Fase 10): Investigasi & drill-down
# ============================================================

_VALID_STAGES_FOR_RANKING = (
    "validation", "session_load", "reformulation", "embedding",
    "retrieval", "reranking", "parent_assembly", "generation", "db_save",
)


@router.get("/stage-ranking", summary="G1: request dengan durasi tahap tertentu, tertinggi/terendah")
async def get_stage_ranking(
    stage: str = Query(..., description=f"Salah satu dari: {', '.join(_VALID_STAGES_FOR_RANKING)}"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
    admin: dict = Depends(get_current_admin),
):
    if stage not in _VALID_STAGES_FOR_RANKING:
        raise HTTPException(status_code=400, detail=f"stage tidak valid. Pilihan: {_VALID_STAGES_FOR_RANKING}")

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    col = f"stage_{stage}_ms"
    client = _get_supabase_client()
    response = (
        client.table("request_metrics")
        .select(f"request_id,created_at,session_id,username,question,channel,{col}")
        .eq("status", "success")
        .gte("created_at", since)
        .gt(col, 0)
        .order(col, desc=(order == "desc"))
        .limit(limit)
        .execute()
    )
    return {"stage": stage, "data": response.data or []}


@router.get("/request/{request_id}", summary="G2/G5: detail lengkap satu request (semua tahap, token, cost, retrieval_detail)")
async def get_request_detail(request_id: str, admin: dict = Depends(get_current_admin)):
    client = _get_supabase_client()
    response = client.table("request_metrics").select("*").eq("request_id", request_id).limit(1).execute()
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="request_id tidak ditemukan")
    # `retrieval_detail` (JSONB) sudah otomatis ikut lewat select("*") — ini
    # yang dipakai UI untuk "detail cross-encoder dengan pertanyaan" (G5).
    return {"data": rows[0]}


@router.get("/questions", summary="G4/G6: list pertanyaan, filter opsional per-domain dan/atau no-relevant-doc")
async def get_questions(
    domain: str | None = Query(default=None, description="PI | KKP | SKRIPSI | NON_SKRIPSI | UNKNOWN"),
    no_relevant_doc_only: bool = Query(default=False),
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=100, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = _get_supabase_client()
    query = (
        client.table("request_metrics")
        .select("request_id,created_at,session_id,username,domain_detected,is_no_relevant_doc,"
                 "question,num_docs_after_rerank,top_cross_encoder_score")
        .eq("status", "success")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if domain:
        query = query.eq("domain_detected", domain)
    if no_relevant_doc_only:
        query = query.eq("is_no_relevant_doc", True)
    response = query.execute()
    return {"data": response.data or []}


@router.get("/errors/list", summary="G3: list error mentah dengan session & user (bukan agregat)")
async def get_errors_list(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=500),
    admin: dict = Depends(get_current_admin),
):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = _get_supabase_client()
    response = (
        client.table("request_metrics")
        .select("request_id,created_at,session_id,username,mahasiswa_id,channel,"
                 "error_source,error_type,question,total_ms")
        .eq("status", "error")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"data": response.data or []}
```

> **Catatan implementasi:** `.gt(col, 0)` di endpoint `/stage-ranking` sengaja dipakai untuk membuang baris yang tahap itu memang tidak pernah berjalan (nilainya `NULL`/0 — mis. `stage_reranking_ms` pada request yang short-circuit karena tidak ada dokumen sama sekali). Sesuaikan nama method filter builder (`.gt`, `.eq`, `.gte`) kalau versi `supabase-py` yang terpasang berbeda dari yang diasumsikan di sini — cek dokumentasi `postgrest-py` yang sesuai versinya kalau ada error `AttributeError`.

### 14.3 Pemetaan langsung ke permintaan Anda

| Permintaan | Endpoint |
|---|---|
| G1 — klik tahap pipeline → ranking latency + session + pertanyaan | `GET /api/admin/metrics/stage-ranking?stage=reranking&order=desc` |
| G2 — klik baris histori → detail 1 request | `GET /api/admin/metrics/request/{request_id}` |
| G3 — session + akun yang kena error | `GET /api/admin/metrics/errors/list` |
| G4 — list pertanyaan per domain | `GET /api/admin/metrics/questions?domain=PI` |
| G5 — detail cross-encoder per pertanyaan | `GET /api/admin/metrics/request/{request_id}` (field `retrieval_detail`) |
| G6 — list pertanyaan no-relevant-doc | `GET /api/admin/metrics/questions?no_relevant_doc_only=true` |

### 14.4 Definition of Done — Fase 10
- [ ] `GET /api/admin/metrics/stage-ranking?stage=generation&order=desc&limit=10` mengembalikan daftar terurut dari `stage_generation_ms` tertinggi, tiap baris ada `question` dan `session_id`
- [ ] `GET /api/admin/metrics/request/{request_id}` dengan `request_id` yang valid → 200 dengan semua kolom terisi termasuk `retrieval_detail` (array, bukan `null`, untuk request yang sempat masuk tahap retrieval)
- [ ] `GET /api/admin/metrics/request/{request_id}` dengan `request_id` acak/tidak ada → 404
- [ ] `GET /api/admin/metrics/questions?domain=PI` cuma mengembalikan baris dengan `domain_detected=PI`
- [ ] `GET /api/admin/metrics/questions?no_relevant_doc_only=true` cuma mengembalikan baris dengan `is_no_relevant_doc=true`
- [ ] `GET /api/admin/metrics/errors/list` menunjukkan `session_id`, `username` (dan `mahasiswa_id` kalau dari website), `question`, dan `error_source` di tiap baris
- [ ] Kirim chat dari Telegram sampai gagal (mis. matikan sementara API key OpenAI) → baris error di `errors/list` tetap punya `question` terisi (buktikan perbaikan fondasi Fase 10 bekerja — sebelumnya data ini akan hilang total)

---

## 15. Risiko, asumsi, dan hal yang perlu diverifikasi manual

1. **Harga OpenAI di `config/pricing.yaml`** (Fase 1, 5.4) adalah nilai yang diverifikasi per **7 Juni 2026**. WAJIB dicek ulang di [openai.com/pricing](https://openai.com/pricing) sebelum angka cost dipakai untuk laporan/keputusan bisnis apapun — harga API bisa berubah tanpa pemberitahuan panjang.
2. **`response.usage_metadata`** (Fase 4, 8.1) adalah field resmi dari `langchain-openai`. Kalau versi `langchain-openai` yang terpasang di project ini cukup lama, field ini mungkin belum ada — kode sudah punya fallback otomatis ke estimasi tiktoken lama, jadi tidak akan crash, tapi cek versi dengan `pip show langchain-openai` dan upgrade kalau perlu untuk akurasi cost yang lebih baik.
3. **`http_client=` di `ChatOpenAI`/`OpenAIEmbeddings`** (Fase 6) bergantung pada `langchain-openai` meneruskan parameter ini ke `openai.OpenAI(...)` di baliknya. Ini sudah didukung di versi-versi `langchain-openai` yang umum dipakai saat ini — kalau setelah implementasi ternyata `openai_retry_count` selalu 0 padahal ada retry yang terjadi (cek log `loguru` untuk pesan retry dari `openai` library), berarti versi yang terpasang tidak meneruskan parameter ini dengan benar, dan perlu pendekatan alternatif (mis. subclass `ChatOpenAI` dan override method request).
4. **E5 (follow-up rate)** memakai proxy `rewrite_method`, bukan definisi berbasis kepuasan user — lihat catatan di bagian 11.
5. **RLS di `request_metrics`** (Fase 0) ditulis mengasumsikan pola `auth.role() = 'service_role'` seperti yang lazim di Supabase. **Cek dulu pola RLS tabel lain** (`chat_logs`, `user_quotas`) di `scripts/supabase.sql` sebelum menjalankan — kalau project ini ternyata tidak pakai RLS sama sekali di tabel-tabel itu (karena akses selalu lewat service role key dari backend, tidak pernah dari client langsung), boleh skip bagian RLS di migrasi Fase 0.
6. **Overhead performa.** Semua instrumentasi di dokumen ini dirancang ringan (timer in-memory + satu INSERT tambahan ke Supabase per request, di luar request path kritis — insert `request_metrics` dan `chat_logs` sama-sama terjadi di titik yang sama di akhir `chat()`, tidak menambah round-trip network baru selain satu INSERT). Untuk server 1 CPU/2GB RAM, dampak ini seharusnya dapat diabaikan dibanding waktu reranking (~300-800ms) dan generation LLM yang sudah jadi bottleneck utama. Kalau nanti terukur ada overhead signifikan, opsi lanjutan: buat `persist_metrics()` jalan di background thread/task alih-alih blocking di akhir `chat()`.
7. **Privasi (Fase 10).** Dengan menyimpan `question` per-request langsung di `request_metrics` dan mengeksposnya lewat endpoint investigasi (`/questions`, `/errors/list`, `/request/{id}`), admin jadi bisa membaca pertanyaan individual tiap user terhubung ke identitasnya (`session_id`/`mahasiswa_id`/`username`) dengan lebih mudah dibanding sebelumnya. Data ini sebenarnya sudah ada di `chat_logs` lama untuk request yang sukses — jadi bukan eksposur data baru — tapi sekarang jadi lebih mudah di-drill-down lewat dashboard, dan (baru) juga tersedia untuk request yang GAGAL, yang sebelumnya tidak tercatat di `chat_logs` sama sekali. Pastikan endpoint-endpoint ini tetap di belakang `get_current_admin` (sudah begitu di rencana ini) dan tidak pernah diekspos ke role non-admin.
8. **Keterbatasan identitas Telegram (Fase 10).** `mahasiswa_id` SELALU `None` untuk channel Telegram — sistem saat ini tidak punya mekanisme menghubungkan akun Telegram ke akun mahasiswa. Untuk requirement G3 ("info session + akun"), data dari Telegram akan menunjukkan username Telegram, bukan identitas mahasiswa terverifikasi. Ini keterbatasan model auth yang sudah ada, bukan sesuatu yang diperbaiki dokumen ini.

---

## 16. Lampiran: daftar lengkap file baru & file yang diubah

**File baru:**
- `scripts/supabase_migration_observability.sql`
- `scripts/supabase_migration_observability_views.sql`
- `config/pricing.yaml`
- `src/monitoring/__init__.py`
- `src/monitoring/context.py`
- `src/monitoring/errors.py`
- `src/monitoring/pricing.py`
- `src/monitoring/writer.py`
- `src/monitoring/openai_client.py`
- `src/api/admin_metrics.py`

**File yang diubah:**
- `config/settings.py` — tambah `ENABLE_REQUEST_METRICS`
- `.env.example` — tambah `ENABLE_REQUEST_METRICS`
- `src/services/ai_services.py` — wiring collector, error taxonomy, timing session_load/db_save, **+ Fase 10: `question`/`username` diisi sejak awal**
- `src/retrieval/hybrid_search.py` — timing embedding/retrieval, token & cost embedding, `http_client`
- `src/retrieval/pipeline.py` — timing reranking/parent_assembly, domain, skor, no-relevant-doc, **+ Fase 10: `retrieval_detail` per-dokumen**
- `src/generation/chain.py` — token & cost generation aktual, `http_client`
- `src/generation/intent_classifier/classifier.py` — `http_client`
- `src/generation/intent_classifier/reformulator.py` — `http_client`
- `src/api/ai.py` — timing validation, quota rejection logging, **+ Fase 10: `question`/`username` ke collector**
- `src/bot/handlers/chat_handler.py` — timing validation, quota rejection logging, **+ Fase 10: `question`/`username` ke collector**
- `src/api/admin_metrics.py` — **+ Fase 10: 4 endpoint investigasi baru** (`stage-ranking`, `request/{id}`, `questions`, `errors/list`)
- `application.py` — registrasi router `admin_metrics`

> Fase 10 **tidak menambah file baru** — murni perluasan kolom/logic di file-file yang sudah direncanakan sejak Fase 0-8.

**File yang TIDAK diubah (sengaja dipertahankan apa adanya):**
- `chat_logs` (tabel) — tetap dipakai seperti sekarang, `request_metrics` adalah tabel terpisah di sampingnya
- `chunk_edit_logs` (tabel) — sudah cukup lengkap, cuma ditambah view agregasi di atasnya
- `src/middleware/monitoring.py` — modul lama yang tidak pernah di-register; dokumen ini menggantikannya dengan pendekatan `src/monitoring/` yang baru. Boleh dihapus di akhir kalau sudah dipastikan tidak dipakai di mana pun (`grep -rn "middleware.monitoring" src/ application.py`).