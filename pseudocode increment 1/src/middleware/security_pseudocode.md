# Pseudocode untuk `src/middleware/security.py`

```markdown
ALGORITMA MIDDLEWARE KEAMANAN (security.py)

1. IMPOR PUSTAKA
   - `time`, hashing (`hashlib`, `hmac`), FastAPI Middleware, loguru.
   - Konfigurasi aplikasi.

2. KELAS RateLimitMiddleware
   - Tujuan: Membatasi jumlah *request* dari 1 klien per waktu (misal: 100 req per 60 detik) untuk cegah spam/DDoS.
   - `__init__`: Set batas limit dan jendela waktu (dari settings).
   - `_get_client_id`:
     - Tentukan identitas klien: Cek `session_id`.
     - Jika tidak ada, fallback ambil IP klien (dari header "X-Forwarded-For" atau host).
   - `_check_rate_limit`:
     - Bersihkan catatan request lama yang sudah kedaluwarsa.
     - Hitung total request dari Klien ID tersebut dalam waktu aktif.
     - JIKA total >= batas: Tolak (Kembalikan False).
     - JIKA total < batas: Catat request baru (Kembalikan True).
   - `dispatch`:
     - Abaikan URL `/health`.
     - Cek dengan `_check_rate_limit`.
     - JIKA dilarang: Lemparkan HTTPException (kode 429 Too Many Requests).
     - JIKA boleh: Lanjutkan request, dan tambahkan informasi Sisa Kuota (X-RateLimit-Remaining) ke Header Respon klien.

3. KELAS SecurityHeadersMiddleware
   - Tujuan: Menambah Header Keamanan HTTP wajib sesuai standar (untuk cegah eksploitasi peramban/browser).
   - `dispatch`:
     - Lanjutkan request. Pada saat memberikan response, tambahkan header:
       - `X-Content-Type-Options: nosniff`
       - `X-Frame-Options: DENY` (cegah Clickjacking iframe)
       - `X-XSS-Protection: 1; mode=block`
       - `Referrer-Policy`
     - Jika status Server adalah Produksi, aktifkan juga HSTS (`Strict-Transport-Security`).

4. FUNGSI verify_telegram_webhook(request_body, signature)
   - Digunakan agar orang luar tidak bisa sembarangan memalsukan *push message* seolah dari server Telegram.
   - Lakukan perhitungan HASH/HMAC SHA-256 pada body dengan Kunci Rahasia.
   - Bandingkan hasilnya (signature dari header) dengan hasil hitung kita secara konstan (pakai `hmac.compare_digest`).

5. FUNGSI sanitize_input(text, max_length)
   - Membersihkan teks masukan dari karakter berbahaya, tapi membiarkan teks natural bahasa Indonesia tetap utuh.
   - Potong panjang maksimal teks (default 1000).
   - Buang control character (seperti NULL byte atau escape character).
   - Normalisasi spasi putih ganda menjadi satu spasi saja.
   - Kembalikan teks bersih.

6. FUNGSI validate_chat_input(question, session_id)
   - Cek ID sesi (hanya boleh alfanumerik dan garis bawah/strip, minimal 3 maks 100 huruf).
   - Panggil `sanitize_input` ke pertanyaan.
   - Pastikan teks pertanyaan tidak kosong dan minimal 3 karakter.
   - Jika ada salah satu yang melanggar, lemparkan Error `InputValidationError`.

7. FUNGSI UTILITAS
   - `generate_secure_token`: Hasilkan token acak yang aman kriptografis.
   - `hash_sensitive_data`: Enkripsi/Sembunyikan teks penting agar aman ditulis ke log (hanya 16 karakter depan).
```
