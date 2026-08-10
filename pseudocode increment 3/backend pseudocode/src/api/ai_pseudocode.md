# Pseudocode untuk `src/api/ai.py`

```markdown
ALGORITMA ROUTER API CHATBOT (ai.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, HTTPException, Request, Header)
   - Pydantic (BaseModel, Field) untuk validasi skema request/response.
   - Fungsi `chat_service` dari modul `src.services.ai_services`.
   - Modul auth `verify_access_token`, konfigurasi `settings`, dan Supabase.

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix "/ai" dan tag "AI Chatbot".
   - Buat koneksi Supabase untuk pengecekan kuota.

3. DEFINISI SKEMA REQUEST (ChatRequest)
   - Kolom `query` (Teks wajib): Pertanyaan dari pengguna (minimal 1 karakter).
   - Kolom `session_id` (Teks wajib): ID unik untuk sesi chat pengguna.
   - Kolom `channel` (Teks): Asal platform percakapan (default: "website").

4. DEFINISI SKEMA RESPONSE (ChatResponse)
   - Kolom `answer` (Teks): Jawaban teks dari bot.
   - Kolom `num_docs` (Angka): Jumlah dokumen yang dijadikan referensi.
   - Kolom `session_id` (Teks): ID sesi.
   - Kolom `sources` (Daftar/Array kamus, default kosong): Rincian referensi sumber.
   - Kolom opsional `intent`, `confidence`, `reasoning`.

5. ENDPOINT POST "/chat"
   - Path tujuan: `/ai/chat`.
   - Input Payload: Objek `ChatRequest` dan HTTP Request.
   - Proses Asinkron (async):
     - COBA (Try):
       - TAHAP 1: Cek Channel
         - Jika channel "telegram", tolak akses (403) karena harus lewat webhook.
         - Jika channel "website", pastikan ada header "Authorization: Bearer <token>".
         - Ekstrak token, verifikasi via `verify_access_token`.
         - Cek role (jika bukan "mahasiswa", tolak akses).
         - Ambil `mahasiswa_id` dan `username` dari token.
       
       - TAHAP 2: Cek Kuota
         - Gunakan koneksi Supabase untuk memanggil RPC `increment_quota_if_under_limit` menggunakan `mahasiswa_id`.
         - Jika gagal/habis kuota (False), lemparkan error 429 (Terlalu Banyak Permintaan).
       
       - TAHAP 3: Teruskan ke Chat Service
         - Panggil logika utama bot: `chat_service(query, session_id, username, channel, mahasiswa_id)`.
         - KEMBALIKAN respons `ChatResponse` yang memuat jawaban, jumlah dokumen, sumber, dsb.
         
     - JIKA GAGAL (Catch/Except):
       - Jika error berasal dari HTTPException, teruskan (raise).
       - Jika error lainnya, hasilkan respon HTTP Error (status code 500: Internal Server Error).
```
