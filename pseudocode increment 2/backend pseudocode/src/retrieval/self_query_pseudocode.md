# Pseudocode untuk `src/retrieval/self_query.py`

```markdown
ALGORITMA EKSTRAKSI FILTER OTOMATIS (self_query.py)

1. IMPOR PUSTAKA & STRUKTUR DATA
   - `re` (regex), YAML (untuk baca file), dataclass, loguru.
   - `ParsedQuery`: Struktur data hasil (pertanyaan bersih, filter source, filter section, tingkat keyakinan/confidence).

2. PEMUATAN FILE KATA KUNCI (saat start aplikasi)
   - Tentukan lokasi file: `config/section_keywords.yaml`.
   - `_warn_on_duplicate_keywords()`: Memeriksa kalau ada keyword yang sama muncul di lebih dari satu bab. Jika ada, munculkan warning karena memicu ambiguitas klasifikasi.
   - `_load_section_keywords()`:
     - Buka dan parse YAML menjadi Dictionary: `{"BAB I": ["latar belakang", "tujuan"], ...}`.
     - Normalisasi: buang spasi ujung, ubah huruf kecil, hapus duplikat di dalam satu Bab yang sama.
     - Panggil peringatan jika ada satu kata kunci masuk ke Bab I dan Bab II sekaligus (`_warn_on_duplicate_keywords`).
     - Simpan Dictionary ini di variabel global `SECTION_KEYWORDS`.

3. DETEKSI SUMBER PANDUAN (PI / KKP / SKRIPSI / NON_SKRIPSI)
   - Daftar kata khusus PI (`_PI_KEYWORDS`): "penulisan ilmiah", "seminar pi", dll.
   - Daftar kata khusus KKP (`_KKP_KEYWORDS`): "kuliah kerja praktik", "tempat kkp", dll.
   - Daftar kata khusus SKRIPSI (`_SKRIPSI_KEYWORDS`): "skripsi", "tugas akhir skripsi", dll.
   - Daftar kata khusus NON-SKRIPSI (`_NON_SKRIPSI_KEYWORDS`): "non skripsi", "karya ilmiah", dll.
   - Definisi string judul statis: `_SOURCE_PI`, `_SOURCE_KKP`, `_SOURCE_SKRIPSI`, dan `_SOURCE_NON_SKRIPSI`.
   - `_detect_source(query_lower)`:
     - Cek apakah teks punya kata kunci dari keempat domain.
     - JIKA HANYA ada tepat satu domain yang cocok: Kembalikan variabel statis yang sesuai.
     - JIKA LEBIH DARI SATU atau TIDAK ADA SAMA SEKALI: Kembalikan None (jangan difilter, cari di semua dokumen).

4. DETEKSI BAB / SECTION
   - `_matches_keyword(text, keyword)`: 
     - Jika keyword berupa frase (>1 kata): cek substring biasa.
     - Jika 1 kata: cek pakai batas kata regex (`\b`) agar "syarat" tidak cocok dengan "bersyarat".
   - `_detect_section(query_lower, min_matches=2)`:
     - LOOP tiap section dan daftar keyword-nya.
     - Hitung berapa keyword dari section tersebut yang muncul di teks.
     - Urutkan section yang punya kecocokan (dari jumlah terbanyak).
     - Ambil section pemenang teratas.
     - JIKA jumlah kata kunci cocok >= `min_matches` (minimal 2): Kembalikan nama section (Confidence: "high").
     - JIKA < 2: Batalkan filter, kembalikan None (Confidence: "low").

5. FUNGSI UTAMA extract_query_components(query)
   - Ubah `query` ke huruf kecil.
   - Siapkan kamus `filters` kosong.
   - Deteksi sumber (`_detect_source`). Jika ada, masukkan ke `filters["source"]`.
   - Deteksi bab (`_detect_section`). Jika ada, masukkan ke `filters["section"]`.
   - Cetak (Log) filter yang terpilih.
   - Kembalikan objek `ParsedQuery` yang utuh.

6. FUNGSI BANTUAN METADATA
   - `get_available_sections()`: Kembalikan rincian deskriptif dari setiap bab untuk UI / referensi LLM.
   - `get_metadata_statistics()`: Kembalikan angka kasar statistik sumber dokumen (untuk laporan/debug).
```
