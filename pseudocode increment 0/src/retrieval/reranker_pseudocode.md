# Pseudocode untuk `src/retrieval/reranker.py`

```markdown
ALGORITMA PENGURUTAN ULANG CERDAS (reranker.py)

1. IMPOR PUSTAKA & SETUP
   - Konfigurasi aplikasi.
   - Jika ada token HuggingFace di pengaturan, pasang sebagai *Environment Variable* (HF_TOKEN) agar library bisa unduh model privat jika perlu.
   - Impor `CrossEncoder` dari *sentence_transformers*, loguru.

2. KELAS CrossEncoderReranker
   - Variabel Kelas Statis (Shared): `_shared_model` dan `_shared_model_name`. Bertujuan agar model AI (yang ukurannya besar/ratusan MB) hanya di-*load* (dimuat ke RAM) SATU KALI saja selama server hidup, lalu dipakai bersama-sama.
   
   - `__init__(model_name)`:
     - Ambil nama model cross encoder dari settings (misal: "ms-marco-MiniLM-L-6-v2").
     - Ambil limit top-N (berapa dokumen teratas yang dipertahankan).
   
   - `_get_model()`:
     - Cek variabel statis kelas.
     - JIKA model belum diload ATAU nama model yang mau dipakai berbeda dengan yang ada di memori:
       - Tulis log: "Memuat model..."
       - Load model ke RAM: `CrossEncoder(model_name)`.
       - Simpan di variabel statis.
     - KEMBALIKAN model yang sudah di RAM.

   - `rerank(query, documents, top_n, content_key)`:
     - JIKA daftar dokumen kosong: langsung kembalikan kosong.
     - Minta model dari `_get_model()`.
     - Siapkan array `pairs` kosong untuk menyimpan pasangan `[Pertanyaan, Dokumen]`.
     - LOOP melalui tiap dokumen:
       - Ambil teks isi dokumen. Potong batas karakternya (Truncate) maksimal 2000 karakter depan saja, agar AI pembaca skor tidak kepenuhan memori.
       - Tambahkan `[query, teks_terpotong]` ke `pairs`.
     
     - Minta AI memprediksi skor kedekatan: `scores = model.predict(pairs)`.
     
     - LOOP untuk menggabungkan skor kembali ke masing-masing dokumen:
       - Simpan skor asli float ke properti `doc["cross_encoder_score"]`.
     
     - Urutkan dokumen (Sort) dari skor tertinggi ke terendah.
     - Potong daftar (Slice) hanya mengambil juara 1 sampai `top_n`.
     - Tulis log hasil pengurutan (skor top dan bottom).
     - Kembalikan daftar dokumen yang telah dirangking ulang.
```
