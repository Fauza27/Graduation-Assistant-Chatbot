# Pseudocode untuk `src/services/ai_services.py`

```markdown
ALGORITMA LAYANAN KECERDASAN BUATAN (ai_services.py)

1. IMPOR PUSTAKA & INISIALISASI
   - Memori percakapan, Klasifikasi Niat, Rantai (Chain) AI.
   - Session store (database/penyimpanan di memori).
   - Pengaturan konfigurasi.
   - Buat Instance (objek tunggal): Classifier dan RAG Chain.
   - Tentukan penyimpanan: Coba sambungkan ke database (Supabase JSONB). Jika gagal, jatuh (fallback) gunakan kamus RAM biasa (`_legacy_session_store`).

2. MANAJEMEN SESI (Memori Percakapan)
   - `get_or_create_memory(session_id)`:
     - Cari memori sesi ini di Database (jika pakai DB) atau RAM.
     - Jika belum ada, buat objek `ConversationMemory` baru dengan maksimal 5 turn (10 pesan).
     - Kembalikan memori.
   
   - `_save_memory_if_needed(session_id, memory, channel, mahasiswa_id)`:
     - (Hanya jika pakai DB): Simpan ulang memori yang ter-update ke Database dengan menyertakan asal `channel` (telegram/website) dan UUID pengguna (`mahasiswa_id`).
     - Tangkap error secara diam-diam agar chat tidak gagal hanya karena gagal menyimpan riwayat.
   
   - `clear_session(session_id)`:
     - Hapus data memori user tersebut dari penyimpanan.

   - Pembersihan Sesi Tua (Cleanup):
     - Membuang memori obrolan dari user yang sudah terlalu lama tidak aktif agar RAM / Database tidak penuh.

3. FUNGSI UTAMA chat(query, session_id, username, channel, mahasiswa_id)
   - Fungsi utama yang dipanggil oleh Bot Telegram atau API eksternal saat user bertanya.
   - JIKA `query` atau `session_id` kosong: Kembalikan pesan error seketika.
   
   - TAHAP 1: Normalisasi
     - Panggil `normalize_query(question)`.
   
   - TAHAP 2: Deteksi Reformulasi (Regex)
     - Cek apakah butuh ditulis ulang dengan `needs_rewrite(normalized_query)`.
     - *Slow Path* (Jika butuh di-rewrite): Panggil `get_or_create_memory` (karena LLM butuh riwayat), lalu panggil `reformulate_query(normalized_query, memory)`.
     - *Fast Path* (Jika mandiri): Pakai kueri hasil normalisasi langsung.
   
   - TAHAP 3: Cek Cache (LRU)
     - Buat kunci cache `v1_{resolved_query}`.
     - JIKA hasil sudah ada di `retrieval_cache`: Gunakan data itu langsung (*Cache Hit*).
     - JIKA BELUM (*Cache Miss*): Panggil `run_retrieval(query, rerank_query)`. Simpan hasilnya ke cache.
   
   - TAHAP 4: Muat Memori (Jika belum dimuat)
     - Jika masuk *Fast Path* tadi, muat memori di sini dan tambahkan giliran pertanyaan user.
   
   - TAHAP 5: LLM Generation
     - Panggil RAG Chain (`_rag_chain.invoke_with_history`) dengan memasukkan histori percakapan dan dokumen hasil cari (bisa kosong jika gagal Rerank/Threshold).
     - Simpan jawaban AI (berserta teks isi dokumen referensi) ke memori.
     - Simpan memori ke Database dengan channel dan mahasiswa_id.
     
   - TAHAP 6: Catat Log
     - Catat chat ke tabel `chat_logs` di database. Masukkan `user_id`, `username`, `query`, dan `answer`.
   
   - TAHAP 7: Kembalikan Jawaban
     - Siapkan dictionary hasil yang berisi: Teks Jawaban, Metode Rewrite, Jumlah Dokumen, dan Maksimal 3 Dokumen Sumber Referensi terbaik.
     - JIKA ada error: Tangkap dan kembalikan pesan error *fallback*.

4. FUNGSI preload_models()
   - Dieksekusi secara asinkronus/synchronous saat server baru menyala.
   - Fungsi: Memanaskan (*warm-up*) model AI agar tidak terjadi jeda dingin (*cold-start*) saat request pertama.
   - TAHAP 1: *Preload Cross-Encoder* -> Memaksa model lokal termuat ke RAM.
   - TAHAP 2: *Preload Embedding Model* -> Mengirim string dummy "warmup" ke API OpenAI untuk membangun koneksi HTTP *Keep-Alive* dan memuat *tiktoken* ke RAM.
```
