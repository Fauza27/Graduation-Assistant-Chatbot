# Pseudocode untuk `src/api/health.py`

```markdown
ALGORITMA ENDPOINT HEALTH CHECK & MONITORING (health.py)

1. IMPOR PUSTAKA
   - FastAPI, Pydantic, tipe data (Dict, Any), datetime, time.
   - Konfigurasi settings dan fungsi statistik sesi.

2. PENYIMPANAN WAKTU STARTUP
   - Simpan waktu sistem saat aplikasi pertama kali berjalan ke variabel `_startup_time` (digunakan untuk hitung waktu aktif (uptime)).

3. MODEL DATA RESPON
   - `HealthStatus`: (status, timestamp, version, environment, uptime_seconds).
   - `DetailedHealthStatus`: (mewarisi HealthStatus) ditambah (services, system, sessions).

4. ENDPOINT GET `/health/`
   - Tujuan: Memeriksa apakah server web secara mendasar berjalan.
   - KEMBALIKAN `HealthStatus` (status="healthy", timestamp saat ini, versi app, env app, uptime = waktu saat ini - _startup_time).

5. ENDPOINT GET `/health/detailed`
   - Tujuan: Laporan kesehatan lengkap dengan konektivitas ke dependensi.
   - ALGORITMA:
     - Panggil `_check_openai_health(settings)` secara asinkron.
     - Panggil `_check_supabase_health(settings)` secara asinkron.
     - Ambil statistik sesi chat dari `get_session_stats()`.
     - Siapkan informasi sistem (versi python, max requests, dll).
     - Siapkan status layanan (OpenAI, Supabase, setelan Bot Telegram).
     - Jika ada salah satu layanan yang statusnya "error", set status keseluruhan = "degraded". Jika aman semua, set "healthy".
     - KEMBALIKAN objek `DetailedHealthStatus`.

6. FUNGSI INTERNAL `_check_openai_health(settings)`
   - Coba buat AsyncOpenAI client.
   - Catat waktu mulai.
   - Panggil API `client.models.list()` (Tes koneksi paling ringan).
   - Hitung durasi respon.
   - JIKA BERHASIL: Kembalikan status "healthy" dan durasi respon.
   - JIKA GAGAL (Error): Kembalikan status "error", jenis pesan error, dll.

7. FUNGSI INTERNAL `_check_supabase_health(settings)`
   - Coba buat Supabase client.
   - Catat waktu mulai.
   - Panggil operasi ringan ke database (Pilih (Select) jumlah baris dengan limit 1 dari tabel parent_documents).
   - Hitung durasi respon.
   - JIKA BERHASIL: Kembalikan status "healthy", durasi respon, dan jumlah dokumen.
   - JIKA GAGAL: Kembalikan status "error" dan isi pesannya.

8. ENDPOINT GET `/health/readiness`
   - Tujuan: Diperlukan oleh infrastruktur Cloud (seperti Kubernetes) untuk tahu kapan aplikasi SIAP menerima *traffic*.
   - Cek `_check_openai_health` dan `_check_supabase_health`.
   - JIKA ada yang "error": Lemparkan error HTTP 503 (Service Unavailable) dengan pesan dependensi mana yang mati.
   - KEMBALIKAN status "ready" jika semua layanan berjalan normal.

9. ENDPOINT GET `/health/liveness`
   - Tujuan: Diperlukan Kubernetes untuk tahu apakah container aplikasi *freeze/mati*.
   - KEMBALIKAN status "alive", timestamp, dan nilai uptime. (Tidak mengecek API luar agar lebih ringan).
```
