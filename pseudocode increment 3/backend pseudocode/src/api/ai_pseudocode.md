# Pseudocode untuk `src/api/ai.py` (Updated with Enhanced Validation & Quota Service)

```markdown
ALGORITMA ROUTER API CHATBOT (ai.py) - UPDATED

1. IMPOR PUSTAKA - UPDATED
   - FastAPI (APIRouter, HTTPException, Request, Header)
   - Pydantic (BaseModel, Field, validator) untuk validasi skema request/response.
   - unicodedata, re untuk input sanitization (NEW)
   - Fungsi `chat_service` dari modul `src.services.ai_services`.
   - quota_service.check_and_update_quota untuk shared quota logic (NEW)
   - Modul auth `verify_access_token`, konfigurasi `settings`.

2. INPUT VALIDATION FUNCTIONS - NEW
   - FUNGSI sanitize_input(text, max_length=1000):
     - Buang Unicode control characters (kategori "Cc") kecuali \t, \n, \r
     - Whitespace normalization dengan " ".join(text.split())
     - Truncate ke max_length untuk prevent DoS attacks
     - Support international/Indonesian characters
     - KEMBALIKAN sanitized string

   - FUNGSI validate_session_id(session_id):
     - Check length: 3-100 characters (reasonable bounds)
     - Regex validation: ^[a-zA-Z0-9_-]+$ (prevent injection)
     - KEMBALIKAN boolean valid/invalid

3. INISIALISASI ROUTER - UPDATED
   - Buat `APIRouter` dengan prefix "/ai" dan tag "AI Chatbot".
   - REMOVED: Direct Supabase connection (now handled by quota service)

4. DEFINISI SKEMA REQUEST (ChatRequest) - ENHANCED
   - Kolom `query` (Teks wajib): min_length=3, max_length=500 (UPDATED from min_length=1)
   - Kolom `session_id` (Teks wajib): ID unik untuk sesi chat pengguna.
   - Kolom `channel` (Teks): Asal platform percakapan (default: "website").
   
   - @validator('query') sanitize_query: (NEW)
     - Validasi not empty after strip
     - Call sanitize_input() untuk clean control chars
     - Check length >= 3 after sanitization
     - RAISE ValueError dengan descriptive messages untuk invalid input
   
   - @validator('session_id') validate_session_id_field: (NEW)
     - Call validate_session_id() untuk format validation
     - RAISE ValueError jika format tidak valid

5. DEFINISI SKEMA RESPONSE (ChatResponse)
   - Kolom `answer` (Teks): Jawaban teks dari bot.
   - Kolom `num_docs` (Angka): Jumlah dokumen yang dijadikan referensi.
   - Kolom `session_id` (Teks): ID sesi.
   - Kolom `sources` (Daftar/Array kamus, default kosong): Rincian referensi sumber.
   - Kolom opsional `intent`, `confidence`, `reasoning`.

6. ENDPOINT POST "/chat" - UPDATED
   - Path tujuan: `/ai/chat`.
   - Input Payload: Objek `ChatRequest` (with enhanced validation) dan HTTP Request.
   - Proses Asinkron (async):
     - COBA (Try):
       - TAHAP 1: Cek Channel
         - Jika channel "telegram", tolak akses (403) karena harus lewat webhook.
         - Jika channel "website", pastikan ada header "Authorization: Bearer <token>".
         - Ekstrak token, verifikasi via `verify_access_token`.
         - Cek role (jika bukan "mahasiswa", tolak akses).
         - Ambil `mahasiswa_id` dan `username` dari token.
       
       - TAHAP 2: Cek Kuota - UPDATED (Menggunakan Shared Service)
         - JIKA mahasiswa_id ada:
           - quota_allowed = check_and_update_quota(user_id=str(mahasiswa_id), daily_limit=settings.RATE_LIMIT_REQUESTS)
           - JIKA tidak allowed: RAISE HTTPException 429 dengan descriptive message
         - ELIMINASI: Direct RPC calls dan duplicate error handling logic
       
       - TAHAP 3: Teruskan ke Chat Service
         - Panggil logika utama bot: `chat_service(query, session_id, username, channel, mahasiswa_id)`.
         - KEMBALIKAN respons `ChatResponse` yang memuat jawaban, jumlah dokumen, sumber, dsb.
         
     - JIKA GAGAL (Catch/Except):
       - Jika error berasal dari HTTPException, teruskan (raise).
       - Jika error lainnya, hasilkan respon HTTP Error (status code 500: Internal Server Error).

7. SECURITY & VALIDATION IMPROVEMENTS:
   - ✅ COMPREHENSIVE INPUT VALIDATION: Length limits, character filtering, format validation
   - ✅ DOS PROTECTION: Max length limits prevent large payload attacks  
   - ✅ INJECTION PREVENTION: Regex validation untuk session IDs
   - ✅ UNICODE SUPPORT: International characters preserved, control chars removed
   - ✅ SHARED QUOTA SERVICE: Eliminasi code duplication dengan consistent behavior
   - ✅ FAIL-OPEN QUOTA: Service handles DB errors gracefully tanpa block users
```
