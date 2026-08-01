# Refactor: Menghilangkan Bias Evaluasi dari Pipeline Retrieval

Dokumen ini mencatat perubahan yang dilakukan agar hasil evaluasi RAGAS
benar-benar mengukur kualitas sistem, bukan kualitas keyword yang
disusupkan ke query/reranker.

## Latar Belakang

Versi sebelumnya pada `src/retrieval/query_expansion.py` dan
`src/retrieval/reranker.py` mengandung daftar kata kunci yang memuat
**isi jawaban** dari pertanyaan-pertanyaan yang dievaluasi. Dua contoh:

- `query_expansion.py` lama: jika user bertanya yang mengandung
  "halaman" + "minimal", query otomatis ditambahkan token
  `"40", "halaman", "minimal", "laporan", "naskah", "jumlah", "tidak termasuk", "lampiran"`.
  Token `"40"` sama persis dengan jawaban yang diharapkan.
- `reranker.py` lama: `_calculate_keyword_boost` memakai daftar
  `important_phrases` berisi `"kemeja putih"`, `"almamater"`,
  `"40 halaman"`, `"3-5 kata kunci"`, `"300 kata"`, dll. Jika frasa
  ini muncul di query DAN konten, dokumen mendapat boost skor.

Akibat:
1. Skor RAGAS yang dilaporkan **tidak murni** mengukur kemampuan
   retrieval/reranking; sebagian skor berasal dari "bocoran" frasa
   jawaban yang dimasukkan ke query atau ke proses scoring.
2. Sistem terlihat lebih baik dari kondisi sebenarnya untuk
   pertanyaan-pertanyaan yang ada di benchmark, tapi tidak akan
   generalisasi ke pertanyaan baru di luar list yang ditangani aturan.
3. Reproducibility dan validitas paper dipertanyakan jika reviewer
   memeriksa kode.

## Perubahan

### `src/retrieval/query_expansion.py`
- Hapus seluruh `if`-rule berbasis topik (pakaian, abstrak, halaman,
  kata kunci, sampul, referensi, dll).
- Ganti dengan **acronym expansion** netral: hanya memperluas akronim
  akademik standar (PI ↔ Penulisan Ilmiah, KKP ↔ Kuliah Kerja Praktik,
  SKS, IPK, IP, KRS, BAAK, BAUK, BKK, EYD, APA).
- Tidak ada angka, satuan, atau frasa jawaban yang ditambahkan.
- API publik (`expand_query`, `expand_query_smart`) tidak berubah,
  jadi tidak ada breaking change untuk pemanggil.

### `src/retrieval/reranker.py`
- Hapus `_extract_keywords`, `_calculate_keyword_boost`, daftar
  `important_phrases`.
- Hapus parameter `enable_keyword_boost`, `keyword_boost_weight`,
  serta normalisasi skor ad-hoc.
- Reranker sekarang hanya memakai skor cross-encoder murni
  (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
- Field hasil tetap `cross_encoder_score`, jadi konsumen downstream
  (`chain.py`, `ai_services.py`) tetap kompatibel.

## Implikasi pada Hasil Evaluasi

- Skor metrik retrieval untuk beberapa pertanyaan **mungkin turun**
  karena tidak ada lagi keyword jawaban yang dipaksa masuk ke query.
- Skor yang muncul setelah perubahan ini adalah **skor jujur** yang
  dapat dipertanggungjawabkan.
- Disarankan menjalankan ulang evaluasi RAGAS setelah perubahan ini
  dan melaporkan angka baru di skripsi/paper, dengan catatan bahwa
  versi sebelumnya menggunakan augmentasi keyword yang bias.

## Cara Menjalankan Evaluasi Ulang

```bash
python main.py --evaluate-no-gt --dataset both
```

Hasil akan disimpan ke `evaluation_results_<timestamp>.json` dan
`manual_review_<timestamp>.json` (jika ada item yang perlu cek manual).
