# Pseudocode untuk `src/api/ai.py`

```markdown
ALGORITMA ROUTER API CHATBOT (ai.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, HTTPException)
   - Pydantic (BaseModel, Field) untuk validasi skema request/response.
   - Fungsi `chat_service` dari modul `src.services.ai_services`.

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix "/ai" dan tag "AI Chatbot".

3. DEFINISI SKEMA REQUEST (ChatRequest)
   - Kolom `query` (Teks wajib): Pertanyaan dari pengguna (minimal 1 karakter).
   - Kolom `session_id` (Teks wajib): ID unik untuk sesi chat pengguna.

4. DEFINISI SKEMA RESPONSE (ChatResponse)
   - Kolom `answer` (Teks): Jawaban teks dari bot.
   - Kolom `num_docs` (Angka): Jumlah dokumen yang dijadikan referensi.
   - Kolom `session_id` (Teks): ID sesi.
   - Kolom `sources` (Daftar/Array kamus, default kosong): Rincian referensi sumber.
   - Kolom opsional `intent`, `confidence`, `reasoning`: Data analitik terkait maksud pertanyaan dari LLM (pengklasifikasi niat).

5. ENDPOINT POST "/chat"
   - Path tujuan: `/ai/chat`.
   - Input Payload: Objek `ChatRequest`.
   - Proses Asinkron (async):
     - COBA (Try):
       - Panggil logika utama bot: `chat_service(query, session_id)`.
       - Ambil hasil keluaran (result) dari fungsi tersebut.
       - KEMBALIKAN respons dengan format `ChatResponse` yang memuat jawaban, jumlah dokumen, sumber, intent, dan reasoning.
     - JIKA GAGAL (Catch/Except):
       - Hasilkan respon HTTP Error (status code 500: Internal Server Error) dengan pesan error dari pengecualian yang ditangkap.
```
