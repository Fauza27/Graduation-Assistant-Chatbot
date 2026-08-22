# Pseudocode untuk `src/bot/handlers/chat_handler.py` (Updated with Monitoring)

```markdown
ALGORITMA PENANGANAN CHAT BOT (chat_handler.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA - UPDATED
   - asyncio, html, datetime, functools (lru_cache)
   - telegram.ext (Update, MessageHandler, ContextTypes, filters)
   - Konfigurasi, pesan-pesan teks, modul AI chat, alat pendeteksi sumber.
   - quota_service.check_and_update_quota untuk shared quota logic
   - MONITORING (NEW): import new_collector, start_stage, end_stage dari monitoring.context
   - MONITORING (NEW): import persist_quota_rejection dari monitoring.writer

2. FUNGSI cmd_start(update, context)
   - Tidak berubah — balas /start dengan pesan WELCOME.

3. FUNGSI _format_source_line(source) -> Teks
   - Tidak berubah — format referensi dokumen menjadi teks aman HTML Telegram.

4. FUNGSI handle_text_chat(update, context) - UPDATED WITH MONITORING

   PRE-CHECK: Pastikan pesan teks tidak kosong.
   
   LANGKAH AWAL — SEBELUM quota check (NEW):
   - Dapatkan chat_id, user_id, settings.
   - Buat collector via new_collector(session_id=user_id, channel="telegram", question=text)
     NOTE: question (variabel `text`) diisi SEDINI MUNGKIN — titik paling awal yang mungkin.
   - start_stage("validation") — catat waktu validasi
   - end_stage() — Telegram tidak punya tahap auth seperti website, langsung tutup

   TAHAP 1: Cek Limit Kuota - UPDATED
   - has_quota = await asyncio.to_thread(check_and_update_quota, user_id)
   - JIKA tidak ada kuota:
     - await asyncio.to_thread(persist_quota_rejection, user_id, "telegram", None) (NEW)
       — catat penolakan ke request_metrics dengan status='quota_rejected'
     - Balas dengan pesan DAILY_LIMIT_REACHED.
     - RETURN (hentikan proses).
   
   TAHAP 2: Animasi Loading
   - Berikan aksi "TYPING..." di Telegram.
   - Kirim loading message sementara.
   
   TAHAP 3: AI Proses
   TRY:
   - Ambil username (atau nama depan jika tidak ada username Telegram).
   - Panggil chat() via asyncio.to_thread() — NON-BLOCKING.
     PENTING: contextvars.ContextVar OTOMATIS ter-copy ke asyncio.to_thread()
     secara benar — collector yang dibuat di atas akan ditemukan oleh
     get_current() di dalam ai_services.chat(). Tidak perlu passing manual.
   - Format jawaban dan sumber referensi.
   - Update loading message dengan jawaban final.
   
   EXCEPT:
   - Log error.
   - Update loading message dengan pesan error umum.

5. CATATAN TEKNIS ASYNC:
   - Python contextvars.ContextVar ter-copy dengan benar ke asyncio.to_thread().
   - Ini berarti collector yang di-set di coroutine handle_text_chat akan
     tersedia di thread yang menjalankan ai_services.chat().
   - ai_services.chat() kemudian mem-persist collector di akhir eksekusi.
   - TIDAK PERLU passing collector sebagai argumen fungsi.

6. FUNGSI build_text_chat_handler() -> MessageHandler
   - Factory function — tidak berubah.

7. IMPROVEMENTS ARSITEKTUR:
   - ✅ Early question capture sebelum quota check
   - ✅ Validation timing (0ms untuk Telegram — tidak ada auth check)
   - ✅ Quota rejection tracking yang konsisten dengan REST API
   - ✅ Fail-safe: kegagalan monitoring tidak mempengaruhi user
   - ✅ Consistent behavior dengan website channel
```
