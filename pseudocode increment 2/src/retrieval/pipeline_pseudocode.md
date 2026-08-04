# Pseudocode untuk `src/retrieval/pipeline.py`

```markdown
ALGORITMA JALUR PENCARIAN UTAMA (pipeline.py)

1. IMPOR PUSTAKA
   - `dataclass`, loguru (logger), pengaturan (settings).
   - *Lazy Import* (Impor di dalam fungsi) untuk: `extract_query_components` (Self-Query), `HybridSearcher`, `ParentChildFetcher`, dan `CrossEncoderReranker` agar tidak terjadi *circular import* (impor saling muter).

2. STRUKTUR DATA RetrievalResult
   - `parent_documents`: Daftar (list) dokumen induk hasil akhir pencarian yang siap disuapkan ke LLM.
   - `is_empty`: Boolean (True jika kosong, False jika ada hasil).
   - Properti `num_docs`: Menghitung jumlah dokumen induk.

3. FUNGSI UTAMA run_retrieval(query, rerank_query)
   - Fungsi ini adalah konduktor (pengatur lalu lintas) semua langkah pencarian.
   - `query`: Pertanyaan untuk pencarian awal.
   - `rerank_query`: Pertanyaan asli user untuk perhitungan ulang skor di akhir (jika tidak ada, samakan dengan `query`).
   
   - TAHAP 1: Ekstrak Filter (Self-Query)
     - Panggil `extract_query_components(query)`.
     - Hasilnya: pertanyaan yang bersih dari kata filter, dan `filters` (contoh: cari di sumber "KKP", Bab II).
   
   - TAHAP 2: Pencarian Awal (Hybrid Search)
     - Buat objek `HybridSearcher()`.
     - Cari dokumen anak yang relevan dengan pertanyaan bersih dan filternya.
     - JIKA hasil kosong: Kembalikan `RetrievalResult` kosong.
   
   - TAHAP 3: Tarik Dokumen Utuh (Parent Fetching)
     - Buat objek `ParentChildFetcher()`.
     - Tarik dokumen induk berdasarkan ID dari dokumen anak yang ketemu.
   
   - TAHAP 4: Pengurutan Ulang (Reranking)
     - **Candidate Limiting**: Batasi jumlah dokumen induk yang akan di-Rerank (hanya Top N berdasar konfigurasi `max_parent_for_rerank`).
     - **Adaptive Reranking**: JIKA jumlah kandidat `<= settings.min_parent_for_rerank`, LEWATI proses Reranking (langsung pakai skor Hybrid) untuk menghemat waktu komputasi.
     - JIKA butuh di-Rerank, coba urutkan ulang dokumen induk memakai AI pintar (Cross Encoder) dan pertanyaan asli (`rerank_query`).
     - JIKA proses rerank gagal/error:
       - Tangkap error, log warning.
       - Urutan jangan diubah, cukup ambil N dokumen teratas (berdasarkan skor Hybrid).
   
   - TAHAP 5: Evaluasi Skor Rerank (Zero-Doc Shortcircuit)
     - JIKA skor *Top 1* < `settings.rerank_min_top_score`:
       - Kosongkan hasil dokumen (icu *Minimum Evidence Triggered*). LLM akan menjawab menggunakan mode obrolan biasa.
     - JIKA lulus skor minimum, terapkan aturan filter jarak: hapus dokumen yang skornya turun terlalu jauh dari *Top 1* (berdasar `settings.rerank_relative_gap`).
     - Potong hasil akhir hanya sejumlah `settings.rerank_top_n`.
   
   - Kembalikan objek `RetrievalResult` dengan daftar dokumen akhir yang sudah diurutkan dan disaring.
```
