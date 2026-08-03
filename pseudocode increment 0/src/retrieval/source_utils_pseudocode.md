# Pseudocode untuk `src/retrieval/source_utils.py`

```markdown
ALGORITMA DETEKSI SUMBER PANDUAN (source_utils.py)

1. IMPOR PUSTAKA
   - Tipe data (Literal, Mapping).
   - Tipe `PanduanType`: Harus berisi "PI" atau "KKP".

2. FUNGSI detect_panduan_type(meta)
   - Tujuan: Menentukan apakah sebuah potongan dokumen itu milik Panduan PI atau KKP secara cepat berdasarkan datanya, berguna saat memformat balasan referensi.
   - Masukan: `meta` (Dictionary / kamus dari metadata dokumen).
   - JIKA `meta` kosong/None: Secara *default* (jatuh aman), asumsikan "PI".

   - ATURAN 1 (Paling Kuat): Cek string kolom `source`.
     - Ambil isi `source` (ubah ke huruf kecil).
     - Jika ada kata "kkp" atau "kuliah kerja": KEMBALIKAN "KKP".
     - Jika ada kata "pi" atau "penulisan ilmiah" atau (typo yang diantisipasi) "penulisan imliah": KEMBALIKAN "PI".
   
   - ATURAN 2 (Pengecekan ID):
     - Ambil isi ID induk (`parent_id`) atau ID biasa (`id`), ubah huruf kecil.
     - Jika awalan-nya "parent-kkp-" atau "kkp-": KEMBALIKAN "KKP".
     - Jika awalan-nya "parent-" atau "pi-": KEMBALIKAN "PI".
   
   - JIKA semua aturan gagal, fallback (nilai akhir kembali aman) ke "KKP".
```
