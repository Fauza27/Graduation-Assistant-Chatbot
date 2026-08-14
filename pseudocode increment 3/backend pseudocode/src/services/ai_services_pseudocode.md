# Pseudocode untuk `src/services/ai_services.py` (Updated with Strategy Pattern)

```markdown
ALGORITMA LAYANAN KECERDASAN BUATAN (ai_services.py) - UPDATED

1. IMPOR PUSTAKA & INISIALISASI - UPDATED
   - Memori percakapan, Klasifikasi Niat, Rantai (Chain) AI.
   - Session strategy (NEW): import session_strategy.create_session_store, SessionStore
   - Pengaturan konfigurasi, caching utilities.
   - Buat Instance (objek tunggal): RAG Chain.
   - STRATEGY INITIALIZATION: _session_store_strategy = create_session_store()
     - Strategy dipilih SEKALI saat startup (bukan per function call)
     - Eliminasi repeated if/else branching patterns

2. MANAJEMEN SESI (Memori Percakapan) - UPDATED dengan Strategy Pattern
   - `get_or_create_memory(session_id, mahasiswa_id=None)`:
     - GUNAKAN: _session_store_strategy.load_memory(session_id, mahasiswa_id)
     - Strategy pattern menangani DB vs in-memory logic internally
     - Kembalikan memori conversation yang ready to use
   
   - `_save_memory_if_needed(session_id, memory, channel, mahasiswa_id)`:
     - TRY: _session_store_strategy.save_memory(session_id, memory, channel, mahasiswa_id)
     - EXCEPT: Log error tapi jangan fail operation
     - Strategy menangani DB vs in-memory persistence internally
   
   - `clear_session(session_id)`:
     - RETURN: _session_store_strategy.delete_session(session_id)
     - Strategy menangani cleanup logic per implementation

   - `get_session_stats()`:
     - RETURN: _session_store_strategy.get_session_stats()
     - Strategy menangani statistics aggregation per storage type

   - `cleanup_sessions()`:
     - RETURN: _session_store_strategy.cleanup_idle_sessions()
     - Strategy menangani TTL cleanup per implementation

3. FUNGSI UTAMA chat(query, session_id, username, channel, mahasiswa_id) - UPDATED
   - Fungsi utama yang dipanggil oleh Bot Telegram atau API eksternal saat user bertanya.
   - JIKA `query` atau `session_id` kosong: Kembalikan pesan error seketika.
   
   - TAHAP 1: Normalisasi
     - Panggil `normalize_query(question)`.
   
   - TAHAP 2: Deteksi Reformulasi (Regex)
     - Cek apakah butuh ditulis ulang dengan `needs_rewrite(normalized_query)`.
     - *Slow Path* (Jika butuh di-rewrite): Panggil `get_or_create_memory` (menggunakan strategy), lalu panggil `reformulate_query(normalized_query, memory)`.
     - *Fast Path* (Jika mandiri): Pakai kueri hasil normalisasi langsung.
   
   - TAHAP 3: Cek Cache (LRU)
     - Buat kunci cache `v1_{resolved_query}`.
     - JIKA hasil sudah ada di `retrieval_cache`: Gunakan data itu langsung (*Cache Hit*).
     - JIKA BELUM (*Cache Miss*): Panggil `run_retrieval(query, rerank_query)`. Simpan hasilnya ke cache.
   
   - TAHAP 4: Muat Memori (Jika belum dimuat) - UPDATED
     - Jika masuk *Fast Path* tadi, muat memori menggunakan strategy dan tambahkan giliran pertanyaan user.
   
   - TAHAP 5: LLM Generation
     - Panggil RAG Chain (`_rag_chain.invoke_with_history`) dengan memasukkan histori percakapan dan dokumen hasil cari.
   
   - TAHAP 6: Simpan State - UPDATED
     - Tambahkan assistant turn ke memory
     - Panggil _save_memory_if_needed() menggunakan strategy
   
   - TAHAP 7: Chat Logging - UPDATED
     - TRY: Access database via strategy._store._supabase jika database strategy
     - Insert ke chat_logs table untuk audit trail
     - EXCEPT: Log error tapi jangan fail operation

4. PRELOAD MODELS
   - Warm-up Cross-Encoder dan Embedding models saat startup
   - Avoid cold-start delays pada first request
   - Pre-load PyTorch weights dan tiktoken caches

5. ARCHITECTURE IMPROVEMENTS:
   - ✅ ELIMINASI 6+ repeated if/else branching patterns
   - ✅ STRATEGY PATTERN untuk clean separation of concerns  
   - ✅ SINGLE STRATEGY SELECTION saat startup (performance)
   - ✅ EXTENSIBLE design untuk future storage types (Redis, etc)
   - ✅ TESTABLE architecture dengan mockable strategy interface
   - ✅ CONSISTENT behavior across database dan in-memory modes
```
     - Simpan jawaban AI (berserta teks isi dokumen referensi) ke memori.
     - Simpan memori ke Database dengan channel dan mahasiswa_id.
     
   - TAHAP 6: Catat Log
     - Catat chat ke tabel `chat_logs` di database. Masukkan `user_id`, `username`, `query`, dan `answer`.
     
   - TAHAP 7: Kembalikan Jawaban
     - Siapkan dictionary hasil yang berisi: Teks Jawaban, Metode Rewrite, Jumlah Dokumen, dan Maksimal 3 Dokumen Sumber Referensi terbaik (masing-masing berisi `section`, `title`, `parent_id`, `score`, dan `pages` — array nomor halaman dari child yang cocok, untuk navigasi PDF `#page=N` di frontend).
     - JIKA ada error: Tangkap dan kembalikan pesan error *fallback*.

4. FUNGSI preload_models()
   - Dieksekusi secara asinkronus/synchronous saat server baru menyala.
   - Fungsi: Memanaskan (*warm-up*) model AI agar tidak terjadi jeda dingin (*cold-start*) saat request pertama.
   - TAHAP 1: *Preload Cross-Encoder* -> Memaksa model lokal termuat ke RAM.
   - TAHAP 2: *Preload Embedding Model* -> Mengirim string dummy "warmup" ke API OpenAI untuk membangun koneksi HTTP *Keep-Alive* dan memuat *tiktoken* ke RAM.
```
