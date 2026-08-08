# Pseudocode Backend - Increment 2 (Google OAuth & Modifikasi Chat)

Dokumen ini berisi *pseudocode* untuk penambahan dan pembaruan kode *backend* pada Increment 2, yaitu fitur Autentikasi Google OAuth untuk mahasiswa dan penyesuaian endpoint chat agar bisa membedakan *channel* (Telegram vs Website).

---

## 1. Modul Autentikasi dan JWT (Kode Baru)

### File: `backend/src/auth/jwt_utils.py`
Bertugas untuk menerbitkan (mencetak) dan memvalidasi (memeriksa) token JWT (JSON Web Token) yang akan digunakan sebagai penanda sesi login di Website.

```markdown
ALGORITMA JWT UTILS (jwt_utils.py)

1. IMPOR PUSTAKA
   - `jwt` (PyJWT)
   - `datetime`, `timedelta`
   - `FastAPI HTTPException`

2. KONFIGURASI
   - Ambil JWT_SECRET_KEY, ALGORITHM ("HS256"), dan JWT_EXPIRATION_MINUTES dari pengaturan (Settings).

3. FUNGSI create_access_token(data_payload) -> String
   - Buat salinan dari `data_payload` (biasanya berisi `sub`: mahasiswa_id (dikonversi ke string), `name`, `email`, `role`="mahasiswa").
   - Tambahkan klaim `exp` (waktu kedaluwarsa) = waktu saat ini + JWT_EXPIRATION_MINUTES.
   - Lakukan enkripsi/encode menggunakan JWT_SECRET_KEY dan ALGORITHM.
   - KEMBALIKAN token berupa string.

4. FUNGSI verify_access_token(token) -> Dictionary
   - COBA (Try):
     - Lakukan dekripsi/decode pada token menggunakan JWT_SECRET_KEY dan ALGORITHM.
     - KEMBALIKAN hasil dekripsi (payload).
   - JIKA GAGAL (Kadetaluwarsa / ExpiredSignatureError):
     - Lemparkan error HTTP 401 (Token expired).
   - JIKA GAGAL (Token tidak valid / JWTError):
     - Lemparkan error HTTP 401 (Invalid token).
```

### File: `backend/src/auth/google_oauth.py`
Menangani validasi `id_token` Google yang dikirim dari Frontend (Google Identity Services).

```markdown
ALGORITMA GOOGLE OAUTH (google_oauth.py)

1. IMPOR PUSTAKA
   - `google.oauth2.id_token`
   - `google.auth.transport.requests`
   - Konfigurasi aplikasi (GOOGLE_CLIENT_ID).

2. FUNGSI verify_google_id_token(token_string) -> Dictionary
   - COBA (Try):
     - Panggil `id_token.verify_oauth2_token(token_string, requests.Request(), GOOGLE_CLIENT_ID)`
     - KEMBALIKAN hasil balasan JSON (berisi `sub` (Google ID), `email`, `name`, `picture`).
   - JIKA GAGAL:
     - Lemparkan error otentikasi (Token tidak valid atau kedaluwarsa).
```

---

## 2. API Endpoint Autentikasi (Kode Baru)

### File: `backend/src/api/auth.py`
Menangani rute HTTP untuk verifikasi token Google dan manajemen sesi.

```markdown
ALGORITMA ROUTER OAUTH (auth.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, Request, Depends, HTTPException)
   - Modul `google_oauth`, `jwt_utils`, klien database (Supabase).

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix `/auth` dan tag "Auth".

3. ENDPOINT POST `/google/verify`
   - Terima payload JSON berisi `id_token`.
   - TAHAP 1: Verifikasi token -> Profil Google dengan menanyakan ke SDK Google (`verify_google_id_token`).
   - TAHAP 2: Simpan/Perbarui Database (`mahasiswa_accounts`):
     - Gunakan mekanisme upsert atomik (`ON CONFLICT (google_sub) DO UPDATE... RETURNING mahasiswa_id`) untuk mencegah *race condition*.
     - Update field `avatar_url`, `nama`, dan `last_login`.
     - Dapatkan `mahasiswa_id`.
   - TAHAP 3: Buat JWT:
     - Payload = `{"sub": str(mahasiswa_id), "name": profil_google.name, "email": profil_google.email, "role": "mahasiswa"}`
     - Panggil `create_access_token(payload)`.
   - KEMBALIKAN respons JSON berisi `{"access_token": token, "token_type": "bearer"}`.

4. ENDPOINT GET `/me`
   - Wajib memiliki header `Authorization: Bearer <token>`.
   - Ekstrak token.
   - Panggil `verify_access_token(token)`.
   - Ambil profil detail dari database berdasarkan `mahasiswa_id` (opsional).
   - KEMBALIKAN data profil (Nama, Email, Avatar).

5. ENDPOINT POST `/logout`
   - KEMBALIKAN respons JSON `{"message": "Logout sukses"}`. (Frontend akan menghapus token dari `sessionStorage`).
```

---

## 3. Modifikasi Endpoint dan Logika Chat (Pembaruan)

### File: `backend/src/api/ai.py`
Penambahan pengecekan *channel*, autentikasi token, dan batasan rate limit.

```markdown
ALGORITMA PEMBARUAN ROUTER CHAT (ai.py)

1. MODIFIKASI SKEMA ChatRequest
   - TAMBAH: `channel` (Tipe: String, Default: "website"). 
     *(Telegram tidak lagi diizinkan lewat endpoint publik HTTP ini demi keamanan).*

2. MODIFIKASI ENDPOINT POST `/chat`
   - TAHAP 1: Cek *Channel*
     - JIKA `request.channel == "telegram"`:
       - TOLAK request (HTTP 403 Forbidden). Alasan: Akses chat Telegram murni diproses melalui Webhook internal.
     - JIKA `request.channel == "website"`:
       - Ambil header "Authorization".
       - JIKA kosong -> Lempar Error 401 (Tidak ada token).
       - Panggil `verify_access_token(token_dari_header)`.
       - Ambil nilai `mahasiswa_id` (dari `sub`) dan `username` (dari `name`) pada payload token.

   - TAHAP 2: Cek Kuota
     - Jika `mahasiswa_id` ada, panggil fungsi database RPC `increment_quota_if_under_limit` (berdasarkan `mahasiswa_id` yang di-cast ke string dan tanggal hari ini).
     - *Catatan: Pastikan bahwa argumen user_id di fungsi RPC berupa TEXT.*
     - JIKA rpc mengembalikan false (batas harian habis) -> Lempar Error 429 (Too Many Requests).

   - TAHAP 3: Teruskan ke Chat Service
     - Panggil `chat(query=request.query, session_id=request.session_id, username=username, channel=request.channel, mahasiswa_id=mahasiswa_id)`.
```

### File: `backend/src/services/session_store.py`
Sistem kini harus merekam *channel* asal obrolan dan ID mahasiswanya (hanya butuh parameter tambahan pada `save_memory`).

```markdown
ALGORITMA PEMBARUAN PENYIMPANAN SESI (session_store.py)

1. FUNGSI load_memory(...) (Pencegahan IDOR)
   - UBAH PARAMETER DARI: `(session_id)`
   - MENJADI: `(session_id, mahasiswa_id=None)`
   - JIKA data ditemukan di tabel, cek apakah `mahasiswa_id` di baris database SAMA DENGAN `mahasiswa_id` pemohon (dari JWT token).
   - JIKA BEDA: Lemparkan error HTTP 403 Forbidden (Mencegah peretas memuat atau menimpa ID sesi orang lain).

2. FUNGSI save_memory(...) (Modifikasi Parameter)
   - UBAH PARAMETER DARI: `(session_id, memory)`
   - MENJADI: `(session_id, memory, channel="telegram", mahasiswa_id=None)`
   
3. ALGORITMA PENYIMPANAN
   - Saat menyimpan (upsert) objek `ConversationMemory` (riwayat percakapan) ke tabel `conversation_sessions`, sisipkan nilai `channel`.
   - JIKA `mahasiswa_id` tidak kosong, masukkan ke kolom `mahasiswa_id`.
   - Proses upsert tetap dilakukan 1x (secara keseluruhan) agar tidak mengubah model penyimpanannya.
```

### File: `backend/src/services/ai_services.py`
Modifikasi untuk menerima parameter baru, meneruskannya ke `session_store`, dan menangani pencatatan log `chat_logs`.

```markdown
ALGORITMA PEMBARUAN AI SERVICES (ai_services.py)

1. FUNGSI chat(...) (Modifikasi Parameter)
   - UBAH PARAMETER DARI: `(query, session_id)`
   - MENJADI: `(query, session_id, username, channel="telegram", mahasiswa_id=None)`

2. PENCATATAN CHAT LOGS (Pindah ke Sini)
   - Pindahkan pemanggilan fungsi `log_chat_to_db` yang tadinya ada di `chat_handler.py` (Telegram) ke bagian akhir fungsi ini.
   - Panggil `log_chat_to_db(user_id=(str(mahasiswa_id) jika website, chat_id jika telegram), username=username, query=query, answer=answer)`.
   - Hal ini memastikan log percakapan tercatat baik dari Telegram maupun Website dengan informasi pengguna yang sesuai.

3. PEMUATAN DAN PENYIMPANAN HISTORI SESI
   - Saat perlu memuat memori (untuk rewrite/generate): Panggil `get_or_create_memory(session_id, mahasiswa_id)` yang akan memvalidasi kepemilikan sesi.
   - Saat menyimpan memory, panggil `session_store.save_memory(session_id, memory, channel, mahasiswa_id)`.

### File: `backend/src/api/sessions.py` (Fix Token Payload)
Menangani pengambilan daftar dan detail riwayat *chat*.

```markdown
ALGORITMA RIWAYAT SESI (sessions.py)
1. FUNGSI get_current_mahasiswa(request)
   - Verifikasi Bearer token JWT.
   - Ambil identitas pengguna DARI klaim `sub` (BUKAN `mahasiswa_id`, karena payload JWT standar menggunakan `sub` sebagai ID subjek utama).
2. ENDPOINT GET `/sessions/`, GET `/sessions/{session_id}`, dan DELETE `/sessions/{session_id}`
   - Gunakan filter `.eq("mahasiswa_id", str(mahasiswa_id))` dalam query Supabase untuk memastikan pengguna hanya bisa melihat atau menghapus data miliknya sendiri.
```
```

### File: `backend/src/bot/handlers/chat_handler.py`
Bot Telegram harus memastikan bahwa dia diidentifikasi sebagai *channel* "telegram".

```markdown
ALGORITMA PEMBARUAN HANDLER TELEGRAM (chat_handler.py)

1. FUNGSI handle_text_chat (Modifikasi Pemanggilan Service)
   - Ambil `user_id` dari properti `update.effective_user.id` yang di-cast ke string.
   - Panggil fungsi `check_and_update_quota(user_id)` secara asinkron. Jika kuota habis, tolak permintaan dan beritahu user.
   - Ambil `username` dari properti `update.effective_user.username` atau `update.effective_user.full_name`.
   - Panggil fungsi chat dengan menyertakan nama dan channel eksplisit:
   - `chat(query=text, session_id=user_id, username=username, channel="telegram", mahasiswa_id=None)`
   - HAPUS pemanggilan `log_chat_to_db` dari file ini (karena sudah dipindah ke dalam fungsi `chat` di `ai_services.py`).
```
