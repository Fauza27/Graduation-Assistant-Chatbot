# Pseudocode untuk `backend/scripts/supabase_update_search.sql`

```markdown
ALGORITMA PEMBARUAN FUNGSI PENCARIAN HYBRID DENGAN FILTER SOURCE (supabase_update_search.sql)

1. FUNGSI match_child_documents (Pencarian Vector Saja)
   - TUJUAN: Mencari teks yang mirip secara vektor sebagai fallback (atau standar) jika FTS tidak dipakai.
   - INPUT: query_embedding (vektor), threshold, match_count, filter_section, filter_source (BARU).
   - PROSES:
     - Bandingkan vektor kueri dengan vektor di database menggunakan Cosine Similarity.
     - Lakukan filter `section` (jika diberikan).
     - Lakukan filter `source` (jika diberikan) dengan membandingkan kolom `source` (Tepat/Exact match).
     - Urutkan dari yang paling mirip, batasi jumlah sesuai `match_count`.
   - OUTPUT: Baris-baris dokumen yang cocok beserta nilai kecocokannya (`similarity`).

2. FUNGSI hybrid_search (Pencarian Gabungan FTS + Vector)
   - TUJUAN: Mencari dokumen menggunakan teks biasa (FTS) dan kedekatan makna (Vector), lalu menggabungkan skornya menggunakan Reciprocal Rank Fusion (RRF).
   - INPUT: query_text, query_embedding, match_count, fts_weight, vector_weight, rrf_k, filter_section, filter_source (BARU).
   - PROSES:
     - SUB-QUERY 1 (FTS): 
       - Cari teks berbahasa Indonesia dengan `to_tsvector` dan `websearch_to_tsquery`.
       - Terapkan filter `section` dan `source` (Exact match).
       - Berikan peringkat / urutan (rank_ix).
     - SUB-QUERY 2 (Vector):
       - Cari kedekatan vektor.
       - Terapkan filter `section` dan `source` (Exact match).
       - Berikan peringkat / urutan (rank_ix).
     - PENGGABUNGAN (RRF Scores):
       - Satukan ID dokumen dari kedua hasil di atas (FULL OUTER JOIN).
       - Hitung skor akhir dengan rumus RRF: `(bobot * (1 / (k + rank)))`.
     - FINALISASI:
       - Hubungkan ID terpilih kembali ke tabel `child_documents` untuk mengambil datanya (title, content, dll).
       - Urutkan dari skor tertinggi.
   - OUTPUT: Baris dokumen lengkap beserta rincian skor fts, vector, dan kombinasi (RRF).
```
