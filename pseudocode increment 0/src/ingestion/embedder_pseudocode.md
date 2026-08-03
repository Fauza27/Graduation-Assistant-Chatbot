# Pseudocode untuk `src/ingestion/embedder.py`

```markdown
ALGORITMA PROSES INGESTION & EMBEDDING (embedder.py)

1. IMPOR PUSTAKA
   - OpenAI, Supabase, tqdm (untuk progress bar), dan loguru.
   - Konfigurasi aplikasi (`get_settings`).

2. KONEKSI KE LAYANAN
   - `_get_supabase_client()`: Buat koneksi ke database Supabase (menggunakan URL dan kunci dari settings).
   - `_get_openai_client()`: Buat koneksi ke OpenAI API.

3. FUNGSI get_openai_embeddings(texts, model, batch_size)
   - Tujuannya adalah merubah daftar teks menjadi daftar array angka (vektor 2000 dimensi).
   - Lakukan secara bertahap (batch) agar API tidak menolak karena kelebihan beban.
   - LOOP melalui `texts` dengan langkah `batch_size`:
     - Panggil API `client.embeddings.create` untuk sekumpulan teks (batch) tersebut (menetapkan parameter `dimensions=2000` secara eksplisit).
     - Ekstrak vektor embedding-nya dan kumpulkan.
     - Tunggu (sleep) 0.5 detik antar *batch* untuk menghindari Rate Limit.
   - KEMBALIKAN daftar vektor keseluruhan.

4. FUNGSI _build_metadata_json(child)
   - Ambil data spesifik dari *chunk* (seperti parent_id, judul, bab, halaman).
   - KEMBALIKAN sebagai format dictionary/JSON untuk kolom *metadata* di database.

5. FUNGSI upsert_parent_chunks(parents)
   - Buka koneksi ke tabel `parent_chunks`.
   - Ambil daftar semua `parent_id` yang sudah ada di database.
   - Saring (Filter) `parents`: Hanya simpan dokumen yang belum ada di database.
   - JIKA semua dokumen sudah ada: Hentikan dan kembalikan 0.
   - JIKA ada yang baru: 
     - Susun datanya (ID, judul, isi, bagian, ID anak-anaknya).
     - Sisipkan (Insert) ke database sekaligus (Bulk insert).
   - KEMBALIKAN jumlah dokumen induk yang berhasil masuk.

6. FUNGSI upsert_child_chunks_with_embeddings(children, embeddings, mapping_anak_ke_induk)
   - Buka koneksi ke tabel `child_chunks`.
   - Pastikan jumlah anak teks sama dengan jumlah vektor (embeddings).
   - Cari tahu (Fetch) ID mana saja yang sudah ada di database, lewati jika sudah ada.
   - LOOP sisa anak-anak baru secara berkelompok (batch 20):
     - Untuk setiap *chunk* anak:
       - Cari siapa ID induknya (dari map).
       - Buat metadata JSON.
       - Gabungkan teks, vektor, dan metadatanya menjadi 1 baris (row).
     - Sisipkan baris-baris tersebut ke database Supabase.
   - KEMBALIKAN jumlah dokumen anak yang berhasil masuk.

7. FUNGSI build_child_to_parent_map(parents)
   - Berfungsi membuat kamus rujukan cepat: "Anak X itu miliknya Induk Y".
   - LOOP untuk tiap Induk: 
     - LOOP untuk tiap Anak-ID di dalam Induk:
       - Simpan di dictionary: `map[Anak_ID] = Induk_ID`
   - KEMBALIKAN map.

8. FUNGSI UTAMA run_ingestion(file_anak, file_induk)
   - (STEP 1) Panggil `loader.py` untuk memuat data JSON anak dan induk dari Harddisk.
   - Panggil validasi (apakah semua anak punya induk yang valid?).
   - Buat rujukan (mapping) dari fungsi ke-7.
   - (STEP 2) Ambil semua teks dari file Anak, proses menjadi Vektor lewat OpenAI (`get_openai_embeddings`).
   - (STEP 3) Masukkan data Induk ke database Supabase (`upsert_parent_chunks`).
   - (STEP 4) Masukkan data Anak beserta vektornya ke database (`upsert_child_chunks_with_embeddings`).
   - KEMBALIKAN laporan statistik berupa jumlah data yang diproses.
```
