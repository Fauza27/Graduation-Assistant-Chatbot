# Pseudocode untuk `src/services/ai_services.py` (Updated with Monitoring)

```markdown
ALGORITMA LAYANAN KECERDASAN BUATAN (ai_services.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA & INISIALISASI - UPDATED
   - Memori percakapan, Klasifikasi Niat, Rantai (Chain) AI.
   - Session strategy: import session_strategy.create_session_store, SessionStore
   - MONITORING (NEW): import new_collector, start_stage, end_stage, set_field, get_current
   - MONITORING (NEW): import persist_metrics dari monitoring.writer
   - MONITORING (NEW): import ChatError, RetrievalError, classify_exception dari monitoring.errors
     (NOTE: ChatError & RetrievalError DIPINDAHKAN ke monitoring.errors — tidak lagi
      didefinisikan di ai_services.py untuk konsistensi taksonomi error)
   - Pengaturan konfigurasi, caching utilities.
   - Buat Instance (objek tunggal): RAG Chain.
   - STRATEGY INITIALIZATION: _session_store_strategy = create_session_store()

2. MANAJEMEN SESI (Memori Percakapan) — pola Strategy tidak berubah
   - get_or_create_memory, _save_memory_if_needed, clear_session, get_session_stats,
     cleanup_sessions — sama seperti sebelumnya, menggunakan Strategy pattern.

3. FUNGSI UTAMA chat(query, session_id, username, channel, mahasiswa_id) - UPDATED WITH MONITORING

   PRE-CONDITION: Cek query dan session_id tidak kosong.
   
   SETUP COLLECTOR (NEW):
   - Cek apakah sudah ada collector aktif via get_current().
   - JIKA sudah ada (dibuat oleh entrypoint di ai.py atau chat_handler.py):
     - Gunakan collector yang sudah ada.
     - Update field session_id, mahasiswa_id, channel.
     - Pastikan question dan username terisi (set jika belum ada).
   - JIKA belum ada (dipanggil langsung dari script/test):
     - Buat collector baru via new_collector(session_id, channel, mahasiswa_id,
       question=query.strip(), username=username).
   
   TAHAP 1: Normalisasi
   - Panggil normalize_query(question).
   
   TAHAP 2: Deteksi Reformulasi
   - Cek needs_rewrite(normalized_query).
   
   SLOW PATH (jika butuh rewrite):
   - start_stage("session_load") (NEW)
   - Panggil get_or_create_memory() menggunakan strategy.
   - end_stage() (NEW)
   - Tambahkan user turn ke memory.
   
   - start_stage("reformulation") (NEW)
   - Panggil reformulate_query(normalized_query, memory).
   - end_stage() (NEW)
   
   - set_field(rewrite_method=rewrite_method) (NEW)
   
   TAHAP 3: Cek Cache (LRU)
   - Buat kunci cache v1_{resolved_query}.
   - JIKA Cache Hit: Gunakan cached retrieval_docs.
     NOTE: Domain_detected dan skor retrieval TIDAK diisi saat cache hit
     (disengaja — cache hit tidak merepresentasikan retrieval baru).
   - JIKA Cache Miss:
     - Panggil run_retrieval(query, rerank_query).
     - Simpan ke cache.
     (Metrics retrieval otomatis diisi oleh run_retrieval() via set_field di pipeline.py)
   
   FAST PATH (memory belum dimuat):
   - start_stage("session_load") (NEW)
   - Panggil get_or_create_memory() menggunakan strategy.
   - end_stage() (NEW)
   - Tambahkan user turn ke memory.
   
   TAHAP 4: LLM Generation
   - start_stage("generation") (NEW)
   - Panggil _rag_chain.invoke_with_history(question, retrieval_docs, history).
   - end_stage() (NEW)
   (Token usage dan cost otomatis diisi oleh invoke_with_history() via set_field di chain.py)
   
   TAHAP 5: Simpan State
   - Tambahkan assistant turn ke memory.
   
   - start_stage("db_save") (NEW)
   - Panggil _save_memory_if_needed() menggunakan strategy.
   
   TAHAP 6: Catat Chat Log
   - TRY: Insert ke tabel chat_logs (tabel LAMA, tidak berubah).
   - EXCEPT: Log error tapi jangan fail operation.
   - end_stage() (NEW) — menutup db_save
   
   TAHAP 7: Persist Metrics & Kembalikan Hasil (NEW)
   - collector.status = "success"
   - persist_metrics(collector) — insert ke request_metrics (BARU)
   - Kembalikan {answer, num_docs, rewrite_method, sources}.
   
   EXCEPTION HANDLING (UPDATED):
   - CATCH Exception e:
     - error_source, error_type = classify_exception(e) (NEW — taksonomi otomatis)
     - collector.status = "error"
     - collector.error_source = error_source
     - collector.error_type = error_type
     - persist_metrics(collector) — tetap catat meski error (NEW)
     - Kembalikan pesan error yang sopan ke user (behavior lama TIDAK BERUBAH).

4. FUNGSI preload_models() — tidak berubah
   - Warm-up Cross-Encoder dan Embedding models saat startup.

5. PRINSIP FAIL-SAFE:
   - ✅ start_stage/end_stage/set_field aman dipanggil meski tanpa collector aktif (no-op).
   - ✅ persist_metrics dibungkus try/except di dalam writer.py.
   - ✅ Kegagalan mencatat metrics TIDAK PERNAH menggagalkan response ke user.
   - ✅ Behavior chat TIDAK BERUBAH dari perspektif user.

6. PERUBAHAN ARSITEKTUR:
   - ChatError & RetrievalError DIPINDAHKAN ke src/monitoring/errors.py.
   - Import dari monitoring.errors memastikan error taxonomy konsisten di seluruh codebase.
   - Semua file yang sebelumnya import ChatError dari ai_services harus diupdate ke monitoring.errors.
```
