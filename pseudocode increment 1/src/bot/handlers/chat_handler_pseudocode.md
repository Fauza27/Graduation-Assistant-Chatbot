# Pseudocode untuk `src/bot/handlers/chat_handler.py`

```markdown
ALGORITMA PENANGANAN CHAT BOT (chat_handler.py)

1. IMPOR PUSTAKA
   - asyncio, html, datetime, functools (lru_cache)
   - telegram.ext (Update, MessageHandler, ContextTypes, filters)
   - Konfigurasi, pesan-pesan teks, modul AI chat, alat pendeteksi sumber.

2. FUNGSI _get_supabase_client()
   - Di-cache agar klien Supabase tidak dibuat ulang terus menerus.
   - KEMBALIKAN klien Supabase yang dikonfigurasi dengan URL dan Service Key dari `settings`.

3. FUNGSI check_and_update_quota(user_id) -> Boolean
   - Cek apakah pengguna sudah melewati batas pesan per hari.
   - Ambil limit harian dari konfigurasi (misal: 13).
   - Dapatkan klien Supabase.
   - Panggil fungsi database jarak jauh (RPC) `increment_quota_if_under_limit` dengan input ID pengguna, tanggal hari ini, dan batas kuota harian.
   - JIKA respons berhasil (kuota masih ada), kembalikan TRUE.
   - JIKA respons gagal (limit habis), kembalikan FALSE.
   - JIKA koneksi ke database error/gagal (exception), anggap saja kuota tersedia (fallback True) agar pengguna tidak terblokir karena masalah infrastruktur.

4. FUNGSI log_chat_to_db(user_id, username, question, answer)
   - Buka koneksi ke tabel `chat_logs`.
   - Masukkan ID pengguna, nama pengguna, teks pertanyaan, dan jawaban LLM.
   - Jika gagal, tulis ke log error saja (tidak mengganggu jalannya bot).

5. FUNGSI cmd_start(update, context)
   - Eksekusi ketika user mengetik `/start`.
   - Balas pesan dengan `messages.WELCOME` dan format dengan nama depan pengguna.

6. FUNGSI _format_source_line(source) -> Teks
   - Konversi dan format rincian referensi dokumen menjadi teks yang aman (menghindari error HTML Parse di Telegram).
   - Jika dokumen punya Judul dan Bab berbeda, gabungkan.
   - Gunakan fungsi `html.escape` untuk mengamankan tanda-tanda baca unik (<, >, &).
   - KEMBALIKAN teks string "* [Nama Bagian] (Buku Panduan [PI/KKP])\n".

7. FUNGSI handle_text_chat(update, context)
   - Dieksekusi otomatis ketika ada pesan teks biasa (bukan perintah garis miring /).
   - Pastikan teksnya tidak kosong.
   
   - TAHAP 1: Cek Limit Kuota
     - Panggil `check_and_update_quota` dengan `asyncio.to_thread` agar tidak memblokir event loop.
     - JIKA habis (False), balas dengan pesan `DAILY_LIMIT_REACHED` dan HENTIKAN proses.
     
   - TAHAP 2: Animasi Loading
     - Berikan aksi "TYPING..." di header Telegram.
     - Kirim pesan teks sementara (loading message) dari `messages.LOADING`.
     
   - TAHAP 3: AI Proses & Database
     - Panggil AI Service (`chat(query, session_id)`) secara asinkron di thread terpisah.
     - Ambil teks jawaban. Jika jawaban LLM kosong, isi dengan `messages.EMPTY_ANSWER_FALLBACK`.
     - Gunakan `html.escape` pada teks jawaban agar tidak bikin error saat dikirim via Telegram (karena parse_mode=HTML).
     - JIKA bot memberikan list dokumen sumber (sources):
       - Tambahkan teks "📚 Sumber:\n"
       - Ulangi untuk setiap dokumen sumber dan panggil `_format_source_line`, gabungkan ke dalam balasan.
       
   - TAHAP 4: Kirim Balasan Akhir
     - Ubah (edit_text) pesan loading tadi dengan teks jawaban final AI.
     - Catat jumlah dokumen referensi yang dipakai di log (jika lebih dari 0).
     
   - TAHAP 5: Pencatatan Log Chat
     - Buat background task non-blocking (`asyncio.create_task`) untuk memanggil `log_chat_to_db` (menyimpan chat ke database).
     - Beri callback jika tugas pencatatan tersebut gagal untuk di-*log* di konsol.
     
   - PENANGANAN KESALAHAN UMUM (Except):
     - JIKA di proses atas terjadi exception apa pun:
       - Tulis log error.
       - Coba ubah pesan loading dengan pesan ERROR UMUM.
       - Jika tidak ada pesan loading, langsung reply dengan pesan ERROR UMUM.

8. FUNGSI build_text_chat_handler()
   - KEMBALIKAN objek filter bawaan Telegram yang akan memanggil fungsi `handle_text_chat` setiap kali mendeteksi pesan masuk berupa TEKS dan BUKAN PERINTAH (`~filters.COMMAND`).
```
