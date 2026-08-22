# Pseudocode untuk `src/monitoring/context.py`

```markdown
ALGORITMA CONTEXT-BASED METRICS COLLECTOR (context.py)

Modul ini adalah INTI dari sistem monitoring. Berfungsi sebagai "tempat titip data"
metrics yang bisa diakses dari fungsi manapun sepanjang satu request, tanpa mengubah
signature fungsi-fungsi yang sudah ada di pipeline.

Prinsip utama: FAIL-SAFE — kegagalan mencatat metrics TIDAK BOLEH mengganggu alur
chat utama. Semua fungsi aman dipanggil meski belum ada collector aktif (no-op).

1. KONSTANTA VALID_STAGES
   - Daftar nama tahap pipeline yang valid dan sinkron dengan kolom stage_*_ms
     di tabel request_metrics:
     ("validation", "session_load", "reformulation", "embedding",
      "retrieval", "reranking", "parent_assembly", "generation", "db_save")

2. CONTEXT VARIABLE _current
   - Menggunakan `contextvars.ContextVar` untuk menyimpan collector aktif.
   - Thread-safe dan async-safe secara bawaan di Python.
   - Default value: None (tidak ada collector aktif).

3. DATACLASS RequestMetricsCollector
   - Menyimpan semua data metrics untuk SATU request.
   
   FIELD IDENTITAS:
   - request_id (str): UUID unik per request (auto-generate)
   - session_id (str|None): ID sesi percakapan
   - mahasiswa_id (str|None): ID mahasiswa (website) atau None (Telegram)
   - channel (str): 'website' | 'telegram' | 'unknown'
   
   FIELD STATUS:
   - status (str): 'success' | 'error' | 'quota_rejected'
   - error_type (str|None): nama class exception Python
   - error_source (str|None): 'openai' | 'supabase' | 'validation' | 'rate_limit' | 'unknown'
   - http_status (int|None): HTTP status code jika relevan
   
   FIELD TIMING (diisi via start_stage/end_stage):
   - _stage_ms (dict): mapping stage_name -> elapsed_ms
   - _stage_name (str|None): stage yang sedang berjalan
   - _stage_start (float|None): timestamp mulai stage
   - _t_start (float): timestamp mulai request (auto-set saat inisialisasi)
   
   FIELD RETRIEVAL QUALITY:
   - num_docs_retrieved (int|None): hasil hybrid search sebelum rerank
   - num_docs_after_rerank (int|None): hasil akhir setelah threshold
   - top_cross_encoder_score (float|None): skor tertinggi cross-encoder
   - avg_cross_encoder_score (float|None): rata-rata skor cross-encoder
   - domain_detected (str|None): 'PI'|'KKP'|'SKRIPSI'|'NON_SKRIPSI'|'UNKNOWN'
   - is_no_relevant_doc (bool): True jika tidak ada dokumen relevan
   - retrieved_parent_ids (list[str]|None): parent_id yang masuk context LLM
   - rewrite_method (str|None): 'None'|'Rule'|'LLM'
   
   FIELD TOKEN & COST:
   - input_tokens (int|None): actual input tokens dari OpenAI response
   - output_tokens (int|None): actual output tokens dari OpenAI response
   - embedding_tokens (int|None): estimasi token untuk embedding query
   - llm_cost_usd (float|None): biaya generation LLM dalam USD
   - embedding_cost_usd (float|None): biaya embedding dalam USD
   - openai_retry_count (int): jumlah retry ke OpenAI (default 0)
   
   FIELD INVESTIGASI (G1-G6):
   - question (str|None): teks pertanyaan asli user — WAJIB diisi SEDINI MUNGKIN
   - username (str|None): nama tampilan user (bukan ID)
   - retrieval_detail (list[dict]|None): SEMUA kandidat dokumen beserta skor
     Format: [{"parent_id":"...", "title":"...", "score":0.82, "accepted":true}, ...]

   METODE start_stage(name):
   - Validasi nama stage (warning jika tidak dikenal).
   - Jika ada stage sebelumnya yang belum ditutup, tutup dulu (defensif).
   - Set _stage_name dan _stage_start = time.time().

   METODE end_stage():
   - Hitung elapsed_ms = (time.time() - _stage_start) * 1000.
   - Akumulasikan ke _stage_ms[_stage_name] (bukan timpa, untuk stage yang mungkin dipanggil >1x).
   - Reset _stage_name dan _stage_start ke None.

   METODE add_retry():
   - Increment openai_retry_count += 1.

   METODE total_ms():
   - Hitung (time.time() - _t_start) * 1000.
   - Kembalikan float milidetik sejak request dimulai.

   METODE to_row():
   - Tutup stage yang masih terbuka (defensif).
   - Bangun dict dengan SEMUA field untuk insert ke tabel request_metrics.
   - Expand _stage_ms menjadi kolom stage_<name>_ms untuk setiap VALID_STAGES.
   - Kembalikan dict siap insert.

4. FUNGSI new_collector(session_id, channel, mahasiswa_id, question, username)
   - Buat instance RequestMetricsCollector baru.
   - Set ke context variable _current.
   - KEMBALIKAN collector.
   - NOTE: `question` dan `username` sengaja jadi parameter agar bisa diisi
     di titik paling awal sebelum ada kemungkinan error.

5. FUNGSI get_current()
   - Kembalikan collector aktif dari context variable, atau None.

6. FUNGSI clear_current()
   - Reset context variable ke None.

7. HELPER FUNCTIONS (module-level, mengurangi boilerplate di call site):
   
   FUNGSI start_stage(name):
   - Dapatkan collector via get_current().
   - Jika ada: panggil collector.start_stage(name).
   - Jika tidak ada: no-op (safe untuk script/test tanpa collector).

   FUNGSI end_stage():
   - Dapatkan collector via get_current().
   - Jika ada: panggil collector.end_stage().

   FUNGSI add_retry():
   - Dapatkan collector via get_current().
   - Jika ada: panggil collector.add_retry().

   FUNGSI set_field(**kwargs):
   - Dapatkan collector via get_current().
   - Jika tidak ada: no-op.
   - Untuk setiap key-value di kwargs:
     - Jika field ada di collector: setattr(collector, key, value).
     - Jika tidak ada: log warning field tidak dikenal.
```
