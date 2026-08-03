# Pseudocode untuk `src/retrieval/parent_child.py`

```markdown
ALGORITMA PENGAMBILAN DOKUMEN INDUK (parent_child.py)

1. IMPOR PUSTAKA
   - Supabase client, loguru.
   - Konstanta pengaturan, model hasil pencarian (`HybridSearchResult`).

2. KELAS ParentChildFetcher
   - Konsep: Data dipecah kecil-kecil (anak) untuk dicari, tapi setelah ketemu, yang dikirim ke LLM adalah dokumen besar utuh (induk) agar LLM paham konteks lengkapnya.
   - `__init__`: Inisialisasi koneksi Supabase dan nama tabel dokumen induk (`table_parent_chunks`).

   - `fetch_parents(search_results)`:
     - TAHAP 1: PENGUMPULAN & DE-DUPLIKASI ID INDUK
       - Masukan: daftar potongan kecil (anak) hasil pencarian sebelumnya.
       - Siapkan sebuah kamus (dictionary) kosong bernama `parent_scores`.
       - LOOP tiap hasil pencarian anak:
         - Ambil `parent_id` dan skor relevansinya (`score`).
         - JIKA `parent_id` sudah ada di dalam kamus `parent_scores`:
           - Perbarui (Update) skor terbaiknya (pilih yang paling besar/maksimal).
           - Tambahkan ID anak ini ke daftar `matched_children`.
         - JIKA BELUM:
           - Buat rujukan baru di kamus: catat skor terbaik dan masukkan ID anak.
       - Ambil semua `parent_id` unik dari kamus tersebut.

     - TAHAP 2: AMBIL DOKUMEN INDUK DARI DATABASE
       - Gunakan query Supabase untuk memilih (Select) dokumen yang `parent_id`-nya ada dalam daftar unik tadi (`in_`).
       - Dapatkan data dokumen lengkapnya.
       - Catat profil waktu eksekusi pengambilan ke Supabase (`time.time()`).
       - Cek (Log Warning) jika ada `parent_id` yang ditarik tidak ditemukan fisiknya di tabel database (anomali).

     - TAHAP 3: TAMBAHKAN METADATA & URUTKAN KEMBALI
       - LOOP setiap dokumen induk yang didapat:
         - Ambil skor anak terbaiknya dari kamus `parent_scores`.
         - Ambil daftar ID anak yang memicu dokumen ini.
         - Sisipkan data tersebut ke dalam dokumen induk (kolom sementara: `best_child_score` dan `matched_children`).
       - Urutkan (Sort) daftar dokumen induk dari nilai `best_child_score` paling besar (menurun/descending).
     
     - Kembalikan daftar dokumen induk yang sudah berurut tersebut.
```
