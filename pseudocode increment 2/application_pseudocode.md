# Pseudocode untuk `application.py`

```markdown
ALGORITMA INISIALISASI SERVER APLIKASI (application.py)

1. IMPOR PUSTAKA
   - Impor FastAPI, middleware CORS, Limiter (rate limit), JSONResponse, HTTPException
   - Impor framework Telegram bot, konfigurasi (settings)
   - Impor routers (`ai`, `health`, `auth`, `sessions`)

2. CONTEXT MANAGER lifespan(app)
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

3. FUNGSI create_app() -> Objek FastAPI
   - Ambil konfigurasi (get_settings).
   - Inisialisasi objek aplikasi `FastAPI` (tetapkan title, version, deskripsi, matikan dokumentasi di production, hubungkan lifespan).
   - Inisialisasi Rate Limiter (`Limiter`) untuk mencegah spam (batas: 100 request/menit per IP).
   - Simpan rate limiter ke dalam state aplikasi.
   - Panggil pendaftaran middleware (`_register_middleware`).
   - Panggil pendaftaran router endpoint (`_register_routers`).
   - KEMBALIKAN objek aplikasi FastAPI.

4. FUNGSI _register_middleware(app)
   - Tambahkan middleware SlowAPI (penanganan limit request).
   - Tambahkan middleware CORS (Cross-Origin Resource Sharing) untuk mengizinkan aplikasi diakses dari berbagai origin (*).

5. FUNGSI _register_routers(app)
   - Daftarkan router `/api` (untuk endpoint sistem AI dan chat).
   - Daftarkan router `/auth` (untuk endpoint otentikasi login).
   - Daftarkan router `/sessions` (untuk endpoint riwayat chat).
   - Daftarkan router `/health` (untuk mengecek kesehatan server).
   
   - DEFINISI ENDPOINT POST `/api/telegram/webhook`:
     - Fungsi ini dipanggil otomatis oleh Telegram setiap ada chat masuk.
     - Ambil pengaturan rahasia webhook.
     - JIKA secret token aktif:
       - Verifikasi token di header HTTP "X-Telegram-Bot-Api-Secret-Token".
       - Jika tidak sama, LEMPAR ERROR 403 (Unauthorized).
     - Verifikasi jika objek bot belum diinisialisasi, LEMPAR ERROR 503 (Service Unavailable).
     - Ambil payload / data JSON masuk.
     - Terjemahkan JSON tersebut menjadi objek `Update` Telegram.
     - Suruh bot untuk memproses update tersebut (`bot_app.process_update(update)`).
     - KEMBALIKAN respon `{"ok": True}`.

   - DEFINISI ENDPOINT GET `/`:
     - Endpoint root untuk mengecek sistem online.
     - KEMBALIKAN JSON pesan selamat datang, versi, dan alamat URL dokumentasi (/docs).
```
