# Pseudocode untuk `scripts/supabase.sql`

```markdown
ALGORITMA SKEMA DATABASE SUPABASE UNTUK RAG (supabase.sql)

1. AKTIVASI EKTENSI DATABASE
   - Aktifkan ekstensi `vector` (pgvector) untuk menyimpan dan mencari embedding dokumen.
   - Aktifkan ekstensi `pg_trgm` (trigram) untuk mendukung pencarian teks berbasis fuzzy (FTS).

2. PEMBUATAN TABEL PARENT DOCUMENTS
   - Hapus tabel jika sudah ada.
   - Buat tabel `parent_documents` dengan kolom:
     - parent_id (TEXT, Primary Key)
     - title (TEXT)
     - content (TEXT) - Konten utuh dokumen
     - section (TEXT)
     - child_ids (Array of TEXT) - Daftar ID potongan dokumen anak
     - created_at (Timestamp)

3. PEMBUATAN TABEL CHILD DOCUMENTS
   - Hapus tabel jika sudah ada.
   - Buat tabel `child_documents` dengan kolom:
     - id (TEXT, Primary Key)
     - parent_id (TEXT, Foreign Key ke parent_documents)
     - title (TEXT)
     - content (TEXT) - Potongan teks dokumen
     - section (TEXT)
     - pages (Array of TEXT)
     - source (TEXT)
     - metadata (JSONB) - Data ekstra untuk filter dari Langchain
     - embedding (VECTOR ukuran 2000) - Menyimpan representasi vektor teks
     - created_at (Timestamp)

4. PEMBUATAN INDEX UNTUK PERFORMA PENCARIAN
   - Buat index `ivfflat` menggunakan `vector_cosine_ops` untuk kolom embedding (pencarian kemiripan vektor).
   - Buat index `GIN` untuk fitur Full-Text Search (FTS) menggunakan `to_tsvector('indonesian')` pada konten.
   - Buat index `GIN` pada kolom metadata (untuk filter metadata JSON).
   - Buat index `B-tree` pada kolom parent_id dan section.

5. FUNGSI match_documents
   - INPUT: query_embedding (vektor), match_count (jumlah hasil, default 10).
   - OUTPUT: Tabel (id, content, metadata, similarity).
   - PROSES: 
     - Lakukan pencarian cosinus kesamaan vektor (1 - jarak cosinus).
     - Ambil baris dari tabel `child_documents`.
     - Urutkan dari kesamaan paling tinggi (jarak cosinus terdekat).
     - Batasi jumlah hasil dengan `match_count`.

6. FUNGSI match_child_documents
   - Sama seperti match_documents, tapi ini ditambahkan:
     - threshold (batas minimal kemiripan).
     - filter bagian / section dokumen tertentu secara case-insensitive (ILIKE).
   - Mengembalikan data yang lebih lengkap termasuk parent_id, source, dll.

7. FUNGSI hybrid_search (Gabungan FTS + Vektor menggunakan RRF)
   - INPUT: Teks (query), Vektor (embedding), jumlah hasil, bobot_fts, bobot_vektor, konstanta RRF, filter section.
   - PROSES:
     - Sub-Query 1 (FTS): Cari dokumen berdasarkan teks `to_tsvector` berbahasa Indonesia, lalu berikan peringkat (ranking).
     - Sub-Query 2 (Vector): Cari dokumen berdasarkan kedekatan vektor, lalu berikan peringkat (ranking).
     - RRF (Reciprocal Rank Fusion): Gabungkan ID dari kedua hasil di atas, dan hitung skor akhirnya dengan rumus bobot * (1 / (Konstanta RRF + Ranking)).
     - Gabungkan kembali hasil akhir (Skor RRF) dengan data dokumen di `child_documents`.
     - Urutkan berdasarkan Skor RRF tertinggi dan kembalikan tabel datanya.

8. KONFIGURASI KEAMANAN (Row Level Security - RLS)
   - Aktifkan RLS di `parent_documents` dan `child_documents`.
   - Buat aturan (policy): Hanya pengguna dengan peran `service_role` (backend aplikasi dengan kunci service role) yang boleh membaca (SELECT) dan menambah data (INSERT) ke tabel ini.
   - Buat tabel tambahan:
     - `user_quotas` (Batas request user harian).
     - `chat_logs` (Penyimpanan log percakapan historis).
   - Aktifkan RLS untuk tabel-tabel tambahan ini.
   - Aturan kebijakannya juga sama: hanya bisa dibaca dan ditulis oleh `service_role`.
```
