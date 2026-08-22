# Pseudocode untuk `src/api/ai.py` (Updated with Monitoring)

```markdown
ALGORITMA ROUTER API CHATBOT (ai.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA - UPDATED
   - FastAPI (APIRouter, HTTPException, Request, Header)
   - Pydantic (BaseModel, Field, validator) untuk validasi skema request/response.
   - unicodedata, re untuk input sanitization
   - Fungsi chat_service dari modul src.services.ai_services.
   - quota_service.check_and_update_quota untuk shared quota logic
   - Modul auth verify_access_token, konfigurasi settings.
   - MONITORING (NEW): import new_collector, start_stage, end_stage dari monitoring.context
   - MONITORING (NEW): import persist_quota_rejection dari monitoring.writer

2. INPUT VALIDATION FUNCTIONS — tidak berubah
   - sanitize_input(text, max_length=1000)
   - validate_session_id(session_id)

3. INISIALISASI ROUTER
   - APIRouter prefix="/ai", tags=["AI Chatbot"].

4. SKEMA REQUEST (ChatRequest) — tidak berubah
   - query: min_length=3, max_length=500
   - session_id dengan format validation
   - channel (default "website")

5. SKEMA RESPONSE (ChatResponse) — tidak berubah
   - answer, num_docs, session_id, sources, intent, confidence, reasoning

6. ENDPOINT POST "/chat" - UPDATED WITH MONITORING

   LANGKAH AWAL — SEBELUM try/except (NEW):
   - Buat collector via new_collector(session_id=body.session_id, channel=body.channel, question=body.query)
     NOTE: question diisi SEDINI MUNGKIN agar tetap tercatat meski request gagal di validasi.
   - start_stage("validation") — mulai mengukur waktu validasi
   
   TRY:
   - TAHAP 1: Cek Channel
     - Jika telegram: raise HTTPException 403.
     - Jika website: ekstrak dan verifikasi Bearer token.
     - Ambil mahasiswa_id dan username dari JWT payload.
   
   - Set collector.mahasiswa_id dan collector.username (NEW — untuk drill-down G3)
   - end_stage() — menutup "validation" SETELAH auth check, SEBELUM quota check
     (Waktu quota check [network round-trip ke Supabase RPC] tidak masuk
      hitungan validation murni)
   
   - TAHAP 2: Cek Kuota — UPDATED
     - JIKA mahasiswa_id ada:
       - quota_allowed = check_and_update_quota(str(mahasiswa_id), daily_limit)
       - JIKA tidak allowed:
         - persist_quota_rejection(session_id, channel, mahasiswa_id) (NEW)
           — catat penolakan kuota ke request_metrics dengan status='quota_rejected'
         - raise HTTPException 429
   
   - TAHAP 3: Teruskan ke Chat Service
     - chat_service akan MEMAKAI collector yang sudah dibuat di atas via get_current()
       (lihat ai_services.py) dan yang akan mem-persist + menutup collector di akhir.
     - Kembalikan ChatResponse.
   
   EXCEPT HTTPException: raise (teruskan)
   EXCEPT Exception: raise HTTPException 500

7. CATATAN TEKNIS:
   - Karena collector dibuat di sini (SEBELUM try), maka request yang
     gagal di tahap validasi TETAP bisa tercatat di request_metrics.
   - Chat service (ai_services.chat) bertanggung jawab menutup dan
     mempersist collector — tidak dilakukan di endpoint ini.
   - contextvars.ContextVar otomatis ter-copy ke asyncio tasks secara benar.

8. IMPROVEMENTS ARSITEKTUR:
   - ✅ Early question capture untuk error cases
   - ✅ Validation timing tracking
   - ✅ Quota rejection tracking
   - ✅ Consistent behavior dengan Telegram channel
   - ✅ Fail-safe: kegagalan monitoring tidak mempengaruhi user
```
