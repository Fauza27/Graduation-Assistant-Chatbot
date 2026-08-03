# Pseudocode untuk `src/retrieval/hybrid_search.py`

```markdown
ALGORITMA PENCARIAN HYBRID (hybrid_search.py)

1. IMPOR PUSTAKA
   - `dataclass`, tipe data, objek `Document` Langchain.
   - `OpenAIEmbeddings`, `loguru` (logger), `Supabase`.
   - Modul pengaturan (settings) dan ekspansi query.
   - Konstanta: Dimensi Vektor (2000), default nilai parameter algoritma gabungan (RRF_K = 60).

2. STRUKTUR DATA HybridSearchResult
   - Menyimpan hasil pencarian yang sudah tergabung:
     - `document`: Objek teks lengkap (dari Langchain).
     - `hybrid_score`: Angka skor relevansi (gabungan vektor + kata).
     - `child_id`: ID unik potongan (chunk) anak.
     - `parent_id`: ID dokumen induk.

3. KELAS HybridSearcher
   - Bertugas mencari dokumen paling relevan menggunakan pencarian gabungan (BM25 Full Text Search + Vector Similarity). Penggabungan skor dilakukan oleh *Database PostgreSQL* memakai metode RRF (Reciprocal Rank Fusion).
   - `__init__`:
     - Buka koneksi Supabase.
     - Siapkan model pengubah kata ke vektor (Embedder) dari OpenAI.

   - `search(query, filters, top_k, enable_query_expansion)`:
     - TAHAP 1: EKSPANSI QUERY
       - Jika diaktifkan, ubah pertanyaan user menjadi bentuk yang lebih luas via LLM (fungsi `expand_query_smart`).
       - Contoh: "sks pi" -> "sks penulisan ilmiah syarat minimal".
     - TAHAP 2: EMBEDDING
       - Ubah query (pertanyaan) menjadi vektor 2000 dimensi menggunakan OpenAI.
       - Catat profil waktu eksekusi (`time.time()`) untuk proses Embedding.
     - TAHAP 3: EKSEKUSI PENCARIAN DATABASE (HYBRID RPC)
       - Siapkan parameter fungsi database (vektor, query asli, limit top K, bobot BM25, bobot Vektor, konstanta RRF, dan filter metadata (seperti section)).
       - Panggil prosedur database (RPC) bernama `hybrid_search`.
       - Catat profil waktu eksekusi RPC pencarian.
     - TAHAP 4: PENANGANAN KEGAGALAN (FALLBACK)
       - JIKA fungsi hybrid gagal atau kosong (mungkin karena query tidak cocok secara teks sama sekali):
         - Panggil pencarian Vektor saja (Dense Search) lewat prosedur `match_child_documents`.
         - Samakan skor kesamaan kosinus (similarity) dengan `rrf_score` agar formatnya tetap seragam.
     - TAHAP 5: FORMAT HASIL
       - LOOP setiap baris hasil dari database:
         - Bikin objek `Document` berisi teks utuh dan metadatanya (ID, judul, bab, sumber).
         - Masukkan ke objek `HybridSearchResult`.
     - Kembalikan daftar hasil (diurutkan berdasarkan skor `hybrid_score` dari terbesar).
```
