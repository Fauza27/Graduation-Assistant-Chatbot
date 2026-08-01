# Retrieval Module

Modul ini bertanggung jawab untuk mencari dan mengambil dokumen relevan dari database (Supabase) berdasarkan pertanyaan pengguna. Modul ini menggunakan pendekatan **Hybrid Search** (BM25 + Dense Vector) dipadukan dengan teknik **Parent-Child Chunking**.

## Arsitektur & Alur Kerja (Pipeline)

Semua proses retrieval dikoordinasikan secara terpusat melalui `pipeline.py`. Saat pengguna bertanya, alur berikut akan dijalankan:

1. **Self-Querying (`self_query.py`)**  
   Mengekstrak filter terstruktur (seperti `source` dan `section`) dari pertanyaan natural pengguna menggunakan keyword matching (dari `config/section_keywords.yaml`).
2. **Query Expansion (`query_expansion.py`)**  
   Melakukan ekspansi query secara netral (misal: "PI" → "Penulisan Ilmiah") tanpa menambahkan konteks luar (bebas halusinasi/bias).
3. **Hybrid Search (`hybrid_search.py`)**  
   Menjalankan pencarian gabungan (FTS/BM25 + Vector Search) di Supabase. Pencarian dilakukan pada **Child Chunks** (potongan teks kecil agar semantic matching lebih akurat).
4. **Parent Fetching (`parent_child.py`)**  
   Setelah mendapatkan potongan kecil (Child Chunks) yang relevan, sistem akan mengambil keseluruhan bab/halaman aslinya (**Parent Documents**) agar LLM mendapat konteks yang utuh.
5. **Reranking (`reranker.py`)**  
   Menggunakan model ML lokal (Cross-Encoder) murni di CPU untuk menghitung ulang skor relevansi antara pertanyaan asli dengan tiap Parent Document, memastikan urutan terbaik disajikan ke LLM.

## Catatan Penting
- Fungsi `run_retrieval` di `pipeline.py` adalah *single source of truth*. Jangan panggil komponen individual di atas secara langsung dari luar modul ini.
- **Batasan**: Filter `source` saat ini dideteksi tetapi *belum* diteruskan ke RPC Supabase karena limitasi pada schema fungsi SQL saat ini (hanya mendukung filter `section`).
