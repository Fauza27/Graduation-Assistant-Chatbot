# Pseudocode untuk `src/middleware/monitoring.py`

```markdown
ALGORITMA MIDDLEWARE PEMANTAUAN KINERJA (monitoring.py)

1. IMPOR PUSTAKA
   - `time`, `asyncio`, struktur data (`dataclass`), FastAPI/Starlette Middleware, loguru.

2. STRUKTUR DATA
   - `RequestMetrics`: Rekaman 1 request (waktu, metode HTTP, path, kode status HTTP, durasi ms, session ID, error).
   - `SystemMetrics`: Rekaman agregat (total requests, sukses, gagal, rata-rata durasi, sesi aktif). Menyimpan maksimal 1000 request terakhir di memori.
     - Punya fungsi `add_request` untuk mencatat request baru.
     - Punya fungsi `get_stats` untuk menarik ringkasan statistik berdasar jendela waktu tertentu (misal: 60 menit terakhir).

3. INSTANSI GLOBAL
   - `_system_metrics`: Variabel global (Single source of truth) untuk menyimpan metrik selama server berjalan.

4. KELAS MetricsMiddleware
   - Bertugas mencegat (intercept) setiap request yang masuk ke server FastAPI.
   - ALGORITMA `dispatch`:
     - Catat waktu mulai (`start_time`).
     - Jika request menuju API `/chat` (metode POST):
       - Coba bongkar (parse) JSON body-nya untuk mencari nilai `session_id`.
       - Susun ulang body agar bisa dibaca lagi oleh fungsi tujuan (karena body aslinya sekali baca hilang).
     - Lanjutkan eksekusi request ke fungsi utamanya (`call_next`).
     - Setelah selesai, catat waktu akhir dan hitung `duration_ms`.
     - Buat objek `RequestMetrics` dan simpan ke `_system_metrics`.
     - JIKA durasi > 5 detik: Tulis Peringatan (Warning) di log konsol (Request terlalu lambat).
     - Sisipkan *Header HTTP* "X-Response-Time" ke respon balik klien.

5. KELAS PerformanceTracker & AsyncPerformanceTracker
   - Digunakan dengan blok `with` (Context Manager) untuk menghitung lama waktu eksekusi sepotong fungsi tertentu (seperti Timer stopwatch).
   - Saat masuk blok (Enter): Mulai timer.
   - Saat keluar blok (Exit): Hentikan timer, hitung durasi.
   - Jika > 1 detik, tulis Warning. Jika di bawah 1 detik, cukup tulis Debug.
   - Jika ada error (exception), tulis Error log.

6. FUNGSI DEKORATOR track_performance
   - Membungkus (wrap) suatu fungsi (baik sinkron maupun asinkron).
   - Akan otomatis mengaplikasikan `PerformanceTracker` pada fungsi yang dipasangi penanda `@track_performance`.

7. FUNGSI UTILITAS SISTEM (Cek RAM & CPU)
   - `get_memory_usage()`: Gunakan modul `psutil` untuk mendapat total RAM yang dipakai aplikasi (dalam MB dan Persentase).
   - `get_cpu_usage()`: Mendapat angka persentase pemakaian CPU.
```
