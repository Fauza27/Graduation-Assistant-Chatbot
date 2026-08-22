# Pseudocode untuk `src/retrieval/pipeline.py` (Updated with Monitoring)

```markdown
ALGORITMA JALUR PENCARIAN UTAMA (pipeline.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA - UPDATED
   - dataclass, loguru (logger), pengaturan (settings).
   - MONITORING (NEW): import start_stage, end_stage, set_field dari monitoring.context
   - Lazy Import di dalam fungsi: extract_query_components, HybridSearcher,
     ParentChildFetcher, CrossEncoderReranker (untuk hindari circular import).
   - MONITORING LAZY IMPORT (NEW): detect_panduan_type dari source_utils.

2. STRUKTUR DATA RetrievalResult — tidak berubah
   - parent_documents: list dokumen siap disuap ke LLM.
   - is_empty: boolean.
   - Properti num_docs.

3. FUNGSI UTAMA run_retrieval(query, rerank_query) - UPDATED WITH MONITORING

   TAHAP 1: Ekstrak Filter (Self-Query)
   - Panggil extract_query_components(query).
   
   DOMAIN DETECTION (NEW) — setelah self-query:
   - Hitung domain_detected dari parsed.detected_source via detect_panduan_type.
   - set_field(domain_detected=domain_detected)
   - PENTING: Domain dideteksi dari self-query classifier, BUKAN dari dokumen
     yang berhasil diambil — supaya tetap ada atribusi domain walaupun retrieval
     gagal total (untuk analisis "domain mana paling sering gagal retrieval").

   TAHAP 2: Pencarian Awal (Hybrid Search)
   - Panggil HybridSearcher.search() — timing embedding & retrieval serta
     num_docs_retrieved diisi di dalam hybrid_search.py via set_field.
   - JIKA hasil kosong:
     - set_field(is_no_relevant_doc=True, num_docs_after_rerank=0, retrieved_parent_ids=[]) (NEW)
     - Kembalikan RetrievalResult kosong.

   TAHAP 3: Tarik Dokumen Utuh (Parent Fetching) - UPDATED
   - start_stage("parent_assembly") (NEW)
   - Panggil ParentChildFetcher.fetch_parents().
   - end_stage() (NEW)
   - JIKA hasil kosong:
     - set_field(is_no_relevant_doc=True, num_docs_after_rerank=0, retrieved_parent_ids=[]) (NEW)
     - Kembalikan RetrievalResult kosong.

   TAHAP 4: Adaptive Reranking - UPDATED
   - Batasi kandidat ke max_parent_for_rerank.
   
   JIKA skip reranking (kandidat <= min_parent_for_rerank):
   - Set cross_encoder_score = best_child_score untuk konsistensi format.
   - _record_final_retrieval_metrics(final_results, all_scored_candidates=candidate_parents) (NEW)
   - Kembalikan RetrievalResult.
   
   JIKA reranking penuh:
   - start_stage("reranking") (NEW)
   - TRY: CrossEncoderReranker.rerank() → reranked results.
   - EXCEPT: Fallback ke top-N unranked.
   - end_stage() (NEW)
   
   TAHAP 5: Evaluasi Skor — Zero-Doc Shortcircuit
   - JIKA top_score < rerank_min_top_score: final_results = []
   - LAIN: filter dengan relative_gap, potong ke rerank_top_n.
   
   - _record_final_retrieval_metrics(final_results, all_scored_candidates=reranked) (NEW)
   - Kembalikan RetrievalResult.

4. FUNGSI HELPER _record_final_retrieval_metrics(final_results, all_scored_candidates) (NEW)
   - Dipanggil di KEDUA jalur (reranking penuh & adaptive-skip).
   - Mengisi metrics di collector via set_field:
   
   JIKA final_results kosong:
   - set_field(is_no_relevant_doc=True, num_docs_after_rerank=0,
               retrieved_parent_ids=[], retrieval_detail=[...])
   
   JIKA ada hasil:
   - Hitung scores = [p.cross_encoder_score for p in final_results].
   - set_field(
       is_no_relevant_doc=False,
       num_docs_after_rerank=len(final_results),
       top_cross_encoder_score=max(scores),
       avg_cross_encoder_score=avg(scores),
       retrieved_parent_ids=[p.parent_id for p in final_results],
       retrieval_detail=_build_retrieval_detail(all_scored_candidates, accepted_ids)
     )

5. FUNGSI HELPER _build_retrieval_detail(candidates, accepted_ids) (NEW)
   - Bangun struktur untuk kolom JSONB retrieval_detail.
   - Untuk setiap kandidat (SEMUA, bukan hanya yang lolos):
     - Ambil skor: cross_encoder_score jika ada, fallback ke best_child_score.
     - Return: [{"parent_id":"...", "title":"...", "score":0.82, "accepted":true/false}, ...]
   - "accepted" = True jika parent_id ada di accepted_ids (parent yang lolos threshold).
   - Berguna untuk analisis "kenapa dokumen X tidak lolos — skornya berapa" (G5).

6. CATATAN SOAL C2 (top retrieved documents):
   - Kolom retrieved_parent_ids menyimpan array parent_id per request.
   - Query agregasi di view menggunakan unnest(retrieved_parent_ids).
   - Lihat v_top_retrieved_documents di migration views.
```
