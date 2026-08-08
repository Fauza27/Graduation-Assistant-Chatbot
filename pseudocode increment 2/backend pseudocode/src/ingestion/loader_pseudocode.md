# Pseudocode untuk `src/ingestion/loader.py`

```markdown
ALGORITMA PEMUATAN DATA (loader.py)

1. IMPOR PUSTAKA
   - JSON, Path (untuk urusan file system), loguru.

2. FUNGSI load_child_chunks(path)
   - Cek apakah file JSON di `path` ada. Jika tidak, Error (File Not Found).
   - Buka file dan Parse (Bongkar) format JSON-nya.
   - Pastikan hasilnya berupa Daftar (List/Array).
   - LOOP setiap chunk anak:
     - Cek apakah chunk ini punya struktur kolom yang wajib: `id`, `title`, `content`, `section`.
     - Jika kurang satu saja, lemparkan Error gagal struktur.
   - Cek apakah ada nilai ID anak yang sama (Duplikat). Jika ada, lemparkan Error duplikat.
   - KEMBALIKAN seluruh data chunk anak.

3. FUNGSI load_parent_chunks(path)
   - Cek keberadaan file induk di `path`.
   - Parse JSON. Pastikan bentuknya Daftar.
   - LOOP setiap chunk induk:
     - Cek struktur kolom wajib: `parent_id`, `title`, `content`, `section`, `child_ids`.
     - Jika kurang, lemparkan Error.
   - Cek adakah ID induk ganda (Duplikat). Jika ada, Error.
   - KEMBALIKAN seluruh data chunk induk.

4. FUNGSI validate_parent_child_links(parents, children)
   - Menguji apakah relasi anak-induk sudah benar sebelum dimuat ke database.
   - Kumpulkan semua `id` anak ke dalam Himpunan Set (cepat dicari).
   - LOOP semua `parents`:
     - LOOP semua `child_ids` yang diklaim dimiliki parent:
       - JIKA ID tersebut TIDAK ADA di himpunan anak tadi: Lemparkan Error ("Parent mencari anak yang tidak ada").
   - Kumpulkan juga dari sisi sebaliknya: adakah Anak yang statusnya Yatim (Orphan/Tidak punya Parent ID).
     - Jika ada, beri Log Peringatan (Warning), karena anak ini tidak akan bisa merujuk balik ke dokumen penuh.
   - KEMBALIKAN True (artinya struktur valid).
```
