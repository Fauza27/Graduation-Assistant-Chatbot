# Pseudocode untuk `src/retrieval/hybrid_search.py` (Updated with Monitoring)

```markdown
ALGORITMA PENCARIAN HYBRID (hybrid_search.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA - UPDATED
   - dataclass, tipe data, objek Document Langchain.
   - OpenAIEmbeddings, loguru (logger), Supabase.
   - Modul pengaturan (settings) dan ekspansi query.
   - Konstanta: EMBEDDING_DIMENSIONS=2000, RRF_K_DEFAULT=60.
   - MONITORING (NEW): import build_instrumented_http_client dari monitoring.openai_client

2. STRUKTUR DATA HybridSearchResult — tidak berubah
   - document, hybrid_score, child_id, parent_id.

3. KELAS HybridSearcher

   __init__ - UPDATED:
   - Buka koneksi Supabase.
   - Siapkan OpenAIEmbeddings dengan INSTRUMENTED HTTP CLIENT (NEW):
     ```
     self._embedder = OpenAIEmbeddings(
         model=..., api_key=..., dimensions=2000,
         http_client=build_instrumented_http_client()  ← NEW
     )
     ```
   - http_client ini memungkinkan penghitungan retry OpenAI via event hook.

   search(query, filters, top_k, enable_query_expansion) - UPDATED:
   
   TAHAP 1: EKSPANSI QUERY — tidak berubah
   - expand_query_smart jika diaktifkan.
   
   TAHAP 2: EMBEDDING - UPDATED WITH MONITORING
   - Local import start_stage, end_stage dari monitoring.context (NEW)
   - start_stage("embedding") (NEW)
   - Ubah query menjadi vektor 2000d via OpenAI embeddings.
   - end_stage() (NEW)
   - Log profil waktu embedding.
   
   ESTIMASI TOKEN & COST EMBEDDING (NEW):
   - Import tiktoken — gunakan encoding "text-embedding-3-large" atau fallback "cl100k_base".
   - embed_tokens = len(encoder.encode(query))
   - embed_cost = calculate_embedding_cost(settings.embedding_model, embed_tokens)
   - Local import set_field dari monitoring.context (NEW)
   - set_field(embedding_tokens=embed_tokens, embedding_cost_usd=embed_cost) (NEW)
   
   TAHAP 3: EKSEKUSI PENCARIAN DATABASE (HYBRID RPC) - UPDATED WITH MONITORING
   - start_stage("retrieval") (NEW)
   - Panggil RPC hybrid_search di Supabase.
   - end_stage() (NEW)
   - Log profil waktu RPC.
   
   TAHAP 4: PENANGANAN KEGAGALAN (FALLBACK) — tidak berubah
   - JIKA hasil kosong: fallback ke dense-only via match_child_documents.
   - Normalisasi similarity ke rrf_score untuk konsistensi format.
   
   TAHAP 5: FORMAT HASIL — tidak berubah
   - Build HybridSearchResult dari setiap baris hasil database.
   
   MENCATAT NUM_DOCS (NEW):
   - set_field(num_docs_retrieved=len(results)) (NEW)
   - Ini mengisi kolom num_docs_retrieved di request_metrics.
   
   - Kembalikan list results.

4. CATATAN TIMING:
   - Tahap "embedding" mengukur waktu embed_query() ke OpenAI API.
   - Tahap "retrieval" mengukur waktu RPC hybrid_search ke Supabase.
   - Fallback ke dense-only TIDAK diukur terpisah — masuk ke "retrieval" jika
     fallback path yang dieksekusi.
   - Kedua timing ini akan muncul di kolom stage_embedding_ms dan stage_retrieval_ms
     di tabel request_metrics.

5. CATATAN RETRY COUNTER:
   - build_instrumented_http_client() memasang event hook pada httpx.Client.
   - Setiap response 429/5xx menambah openai_retry_count di collector aktif.
   - Ini berlaku untuk EMBEDDING calls — bukan hanya LLM generation.
```
