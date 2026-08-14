# Pseudocode untuk `src/bot/handlers/chat_handler.py` (Updated with Quota Service)

```markdown
ALGORITMA PENANGANAN CHAT BOT (chat_handler.py) - UPDATED

1. IMPOR PUSTAKA - UPDATED
   - asyncio, html, datetime, functools (lru_cache)
   - telegram.ext (Update, MessageHandler, ContextTypes, filters)
   - Konfigurasi, pesan-pesan teks, modul AI chat, alat pendeteksi sumber.
   - quota_service.check_and_update_quota untuk shared quota logic (NEW)

2. REMOVED: Direct Supabase Client & Quota Functions
   - ELIMINATED: _get_supabase_client() function (now handled by quota service)
   - ELIMINATED: check_and_update_quota() local implementation
   - BENEFIT: Code deduplication dengan api/ai.py

3. FUNGSI cmd_start(update, context)
   - Eksekusi ketika user mengetik `/start`.
   - Balas pesan dengan `messages.WELCOME` dan format dengan nama depan pengguna.

4. FUNGSI _format_source_line(source) -> Teks
   - Konversi dan format rincian referensi dokumen menjadi teks yang aman (menghindari error HTML Parse di Telegram).
   - Jika dokumen punya Judul dan Bab berbeda, gabungkan.
   - Gunakan fungsi `html.escape` untuk mengamankan tanda-tanda baca unik (<, >, &).
   - KEMBALIKAN teks string "* [Nama Bagian] (Buku Panduan [PI/KKP])\n".

5. FUNGSI handle_text_chat(update, context) - UPDATED
   - Dieksekusi otomatis ketika ada pesan teks biasa (bukan perintah garis miring /).
   - Pastikan teksnya tidak kosong.
   
   - TAHAP 1: Cek Limit Kuota - UPDATED (Menggunakan Shared Service)
     - has_quota = await asyncio.to_thread(check_and_update_quota, user_id)
     - MENGGUNAKAN: Shared quota_service.check_and_update_quota()
     - CONSISTENT: Same logic dan error handling dengan api/ai.py
     - JIKA habis (False), balas dengan pesan `DAILY_LIMIT_REACHED` dan HENTIKAN proses.
     
   - TAHAP 2: Animasi Loading
     - Berikan aksi "TYPING..." di header Telegram.
     - Kirim pesan teks sementara (loading message) dari `messages.LOADING`.
     
   - TAHAP 3: AI Proses & Database
     - Ambil username (atau nama depan jika tidak ada).
     - Panggil AI Service (`chat(query, session_id, username, channel="telegram", mahasiswa_id=None)`) secara asinkron di thread terpisah.
     - Ambil teks jawaban. Jika jawaban LLM kosong, isi dengan `messages.EMPTY_ANSWER_FALLBACK`.
     - Gunakan `html.escape` pada teks jawaban agar tidak bikin error saat dikirim via Telegram (karena parse_mode=HTML).
     
   - TAHAP 4: Format Sumber Referensi
     - Jika ada sources dari AI response, format menggunakan _format_source_line()
     - Escape HTML characters untuk safe Telegram rendering
     - Tambahkan ke reply text dengan proper formatting
     
   - TAHAP 5: Kirim Response
     - Update loading message dengan jawaban final menggunakan edit_text
     - Handle exceptions dengan graceful error messages
     - Log successful responses dengan document count

6. FUNGSI build_text_chat_handler() -> MessageHandler
   - Factory function untuk create MessageHandler instance
   - Filter: TEXT & ~COMMAND (text messages yang bukan slash commands)
   - Handler: handle_text_chat function

7. ARCHITECTURE IMPROVEMENTS:
   - ✅ SHARED QUOTA LOGIC: Eliminasi code duplication dengan api/ai.py
   - ✅ CONSISTENT BEHAVIOR: Same quota checking logic across platforms  
   - ✅ FAIL-OPEN PATTERN: Quota service handles DB errors gracefully
   - ✅ CLEANER CODE: Removed duplicate Supabase client management
   - ✅ MAINTAINABILITY: Single source of truth untuk quota logic
```
     - JIKA bot memberikan list dokumen sumber (sources):
       - Tambahkan teks "📚 Sumber:\n"
       - Ulangi untuk setiap dokumen sumber dan panggil `_format_source_line`, gabungkan ke dalam balasan.
       
   - TAHAP 4: Kirim Balasan Akhir
     - Ubah (edit_text) pesan loading tadi dengan teks jawaban final AI.
     - Catat jumlah dokumen referensi yang dipakai di log (jika lebih dari 0).
     
   - PENANGANAN KESALAHAN UMUM (Except):
     - JIKA di proses atas terjadi exception apa pun:
       - Tulis log error.
       - Coba ubah pesan loading dengan pesan ERROR UMUM.
       - Jika tidak ada pesan loading, langsung reply dengan pesan ERROR UMUM.

7. FUNGSI build_text_chat_handler()
   - KEMBALIKAN objek filter bawaan Telegram yang akan memanggil fungsi `handle_text_chat` setiap kali mendeteksi pesan masuk berupa TEKS dan BUKAN PERINTAH (`~filters.COMMAND`).
```
