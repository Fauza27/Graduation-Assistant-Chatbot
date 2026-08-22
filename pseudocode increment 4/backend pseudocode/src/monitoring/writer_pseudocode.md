# Pseudocode untuk `src/monitoring/writer.py`

```markdown
ALGORITMA PERSISTENCE METRICS KE DATABASE (writer.py)

Menyimpan data RequestMetricsCollector ke tabel request_metrics di Supabase.
Prinsip utama: TIDAK PERNAH melempar exception ke pemanggil — kegagalan
menyimpan metrics tidak boleh mempengaruhi alur chat.

1. INISIALISASI
   - FUNGSI _get_supabase_client() -> Client:
     - Menggunakan @lru_cache(maxsize=1) — Supabase client dibuat SEKALI.
     - Buat client dari settings.supabase_url dan settings.supabase_service_key.
     - Kembalikan client.

2. FUNGSI persist_metrics(collector) -> None
   - JIKA settings.ENABLE_REQUEST_METRICS = False: return (no-op).
   
   TRY:
   - Konversi collector ke dict via collector.to_row().
   - Insert ke tabel "request_metrics" di Supabase.
   EXCEPT Exception:
   - Log error dengan request_id dan detail error.
   - TIDAK melempar exception (fail-safe).

3. FUNGSI persist_quota_rejection(session_id, channel, mahasiswa_id) -> None
   - Dipakai khusus untuk mencatat request yang ditolak KARENA KUOTA HABIS.
   - Berbeda dengan persist_metrics karena terjadi SEBELUM ai_services.chat()
     dipanggil, jadi tidak ada collector lengkap yang tersedia.
   
   - JIKA settings.ENABLE_REQUEST_METRICS = False: return (no-op).
   
   TRY:
   - Insert baris minimal ke "request_metrics":
     {session_id, channel, mahasiswa_id, status: "quota_rejected", total_ms: 0}
   EXCEPT Exception:
   - Log error.
   - TIDAK melempar exception (fail-safe).
```
