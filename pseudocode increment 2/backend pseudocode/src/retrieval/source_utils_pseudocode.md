# Pseudocode untuk `src/retrieval/source_utils.py`

```markdown
4. ALGORITMA DETEKSI SUMBER PANDUAN (source_utils.py)

1. IMPOR PUSTAKA
   - Tipe data (Literal, Mapping).
   - Tipe `PanduanType`: Harus berisi "PI", "KKP", "SKRIPSI", atau "NON_SKRIPSI".

2. FUNGSI detect_panduan_type(meta)
   - Tujuan: Menentukan apakah sebuah potongan dokumen itu milik Panduan PI, KKP, Skripsi, atau Non-Skripsi secara cepat berdasarkan datanya.
   - Masukan: `meta` (Dictionary / kamus dari metadata dokumen).
   - JIKA `meta` kosong/None: Secara *default*, asumsikan "PI".

   - ATURAN 1 (Paling Kuat): Cek string kolom `source`.
     - Ambil isi `source` (ubah ke huruf kecil).
     - Jika ada kata "non" dan "skripsi": KEMBALIKAN "NON_SKRIPSI".
     - Jika ada kata "skripsi": KEMBALIKAN "SKRIPSI".
     - Jika ada kata "kkp" atau "kuliah kerja": KEMBALIKAN "KKP".
     - Jika ada kata "pi" atau "penulisan ilmiah": KEMBALIKAN "PI".
   
   - ATURAN 2 (Pengecekan ID):
     - Ambil isi ID induk (`parent_id`) atau ID biasa (`id`), ubah huruf kecil.
     - Jika awalan-nya "parent-non-skripsi-" atau "non-skripsi-": KEMBALIKAN "NON_SKRIPSI".
     - Jika awalan-nya "parent-skripsi-" atau "skripsi-": KEMBALIKAN "SKRIPSI".
     - Jika awalan-nya "parent-kkp-" atau "kkp-": KEMBALIKAN "KKP".
     - Jika awalan-nya "parent-pi-" atau "pi-": KEMBALIKAN "PI".
   
   - JIKA semua aturan gagal, fallback ke "PI".
```
