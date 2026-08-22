# Pseudocode untuk `application.py` (Updated with Security Integration)

```markdown
ALGORITMA INISIALISASI SERVER APLIKASI (application.py) - UPDATED

1. IMPOR PUSTAKA
   - Impor FastAPI, middleware CORS, Limiter (rate limit), JSONResponse, HTTPException
   - Impor BaseHTTPMiddleware, hmac, hashlib (untuk security integration)
   - Impor framework Telegram bot, konfigurasi (settings)
   - Impor routers (`ai`, `health`, `auth`, `sessions`, `admin`)

2. CLASS SecurityHeadersMiddleware(BaseHTTPMiddleware) - NEW
   - FUNGSI dispatch(request, call_next):
     - Proses request dengan call_next(request)
     - Tambahkan security headers ke response:
       - X-Content-Type-Options: "nosniff"
       - X-Frame-Options: "DENY"
       - X-XSS-Protection: "1; mode=block"
       - Referrer-Policy: "strict-origin-when-cross-origin"
       - Strict-Transport-Security (hanya production)
     - KEMBALIKAN response dengan headers

3. FUNGSI verify_telegram_webhook_secure() - NEW
   - INPUT: request_body, signature, secret
   - Validasi signature menggunakan hmac.compare_digest()
   - Constant-time comparison untuk prevent timing attacks
   - KEMBALIKAN boolean hasil verifikasi

4. CONTEXT MANAGER lifespan(app)
   - Lifespan menangani kode yang dijalankan saat server mulai (startup) dan server mati (shutdown).
   - SAAT SERVER MULAI (STARTUP):
     - Ambil pengaturan dari konfigurasi (get_settings).
     - Panggil `preload_models()` secara asinkron/sinkronus untuk memanaskan (warm-up) model AI (Embedding dan Cross-Encoder).
     - JIKA konfigurasi URL Webhook Telegram (TELEGRAM_WEBHOOK_URL) tersedia:
       - Inisialisasi objek bot Telegram (`create_bot()`).
       - Hubungkan webhook Telegram dengan mengatur URL dan Secret Token (keamanan webhook).
       - Simpan objek bot ke dalam global state aplikasi (`app.state.bot_app`).
   - LEPASKAN KENDALI KE FASTAPI (yield) -> server berjalan menerima request.
   - SAAT SERVER MATI (SHUTDOWN):
     - Cek apakah state bot ada.
     - Jika ada, panggil fungsi untuk memberhentikan (stop) dan mematikan (shutdown) bot dengan aman.

5. FUNGSI create_app() -> Objek FastAPI
   - Ambil konfigurasi (get_settings).
   - Inisialisasi objek aplikasi `FastAPI` (tetapkan title, version, deskripsi, matikan dokumentasi di production, hubungkan lifespan).
   - Inisialisasi Rate Limiter (`Limiter`) untuk mencegah spam (batas: 100 request/menit per IP).
   - Simpan rate limiter ke dalam state aplikasi.
   - Panggil pendaftaran middleware (`_register_middleware`).
   - Panggil pendaftaran router endpoint (`_register_routers`).
   - KEMBALIKAN objek aplikasi FastAPI.

6. FUNGSI _register_middleware(app) - UPDATED
   - Tambahkan SecurityHeadersMiddleware (NEW - security headers untuk semua responses)
   - Tambahkan middleware SlowAPI (penanganan limit request).
   - Tambahkan middleware CORS (Cross-Origin Resource Sharing) untuk mengizinkan aplikasi diakses HANYA dari origin frontend secara eksplisit (seperti Vercel atau localhost).

7. FUNGSI _register_routers(app) - UPDATED
   - Daftarkan router `ai` dengan prefix `/api`.
   - Daftarkan router `auth` dengan prefix `/api`.
   - Daftarkan router `sessions` dengan prefix `/api`.
   - Daftarkan router `admin` dengan prefix `/api`.
   - Daftarkan router `admin_metrics` dengan prefix `/api` (NEW).
     Endpoint final: /api/admin/metrics/* — lihat admin_metrics_pseudocode.md
   - Daftarkan router `health` (tanpa prefix).
   
   - DEFINISI ENDPOINT POST `/api/telegram/webhook` - UPDATED:
     - Fungsi ini dipanggil otomatis oleh Telegram setiap ada chat masuk.
     - Ambil pengaturan rahasia webhook.
     - JIKA secret token aktif:
       - Verifikasi token di header HTTP "X-Telegram-Bot-Api-Secret-Token".
       - GUNAKAN hmac.compare_digest() untuk secure comparison (UPDATED)
       - Jika tidak sama, LEMPAR ERROR 403 (Unauthorized).
     - Verifikasi jika objek bot belum diinisialisasi, LEMPAR ERROR 503 (Service Unavailable).
     - Ambil payload / data JSON masuk.
     - Terjemahkan JSON tersebut menjadi objek `Update` Telegram.
     - Suruh bot untuk memproses update tersebut (`bot_app.process_update(update)`).
     - KEMBALIKAN respon `{"ok": True}`.

   - DEFINISI ENDPOINT GET `/`:
     - Endpoint root untuk mengecek sistem online.
     - KEMBALIKAN JSON pesan selamat datang, versi, dan alamat URL dokumentasi (/docs).

8. SECURITY IMPROVEMENTS IMPLEMENTED:
   - ✅ Security headers aktif untuk semua responses
   - ✅ HMAC-based webhook validation (constant-time comparison)
   - ✅ Production-ready security posture
   - ✅ Dead code eliminated (security.py removed)
```
