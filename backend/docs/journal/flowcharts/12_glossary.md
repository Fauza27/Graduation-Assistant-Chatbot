# Glossary Teknis — Istilah dalam Sistem RAG Chatbot

Penjelasan semua istilah teknis yang dipakai dalam proyek ini, dalam bahasa sederhana.

---

## A

### **API (Application Programming Interface)**
Cara dua program berkomunikasi. Di proyek ini:
- **REST API** = antarmuka HTTP yang bisa diakses via `POST /api/ai/chat`
- **OpenAI API** = layanan cloud untuk menggunakan model GPT
- **Supabase API** = antarmuka untuk database PostgreSQL

---

## B

### **BM25 (Best Match 25)**
Algoritma pencarian berbasis **kata kunci** (keyword matching). Cara kerjanya:
- Hitung seberapa sering kata dari pertanyaan muncul di dokumen
- Dokumen yang banyak mengandung kata-kata dari pertanyaan mendapat skor tinggi
- Diimplementasikan di PostgreSQL via `to_tsvector` + `ts_rank`
- **Kelemahannya:** Tidak memahami makna. "motor" dan "kendaraan bermotor" dianggap tidak sama.

### **Bot (Telegram Bot)**
Program yang berjalan di platform Telegram dan merespons pesan user. Di proyek ini, bot menerima pertanyaan dan mengirim jawaban melalui Telegram.

---

## C

### **Child Chunk**
Potongan **kecil** dari dokumen panduan KKP/PI (biasanya beberapa paragraf). Digunakan untuk **pencarian** karena ukurannya yang kecil membuat embedding lebih tepat sasaran.

Contoh: Satu halaman buku dibagi menjadi 3-4 child chunk.

### **Context Window**
Batas maksimum teks yang bisa diproses LLM dalam satu panggilan. Di proyek ini dijaga dengan `max_tokens=1200` untuk jawaban dan pengiriman hanya top 8 parent dokumen.

### **Cross-Encoder**
Model ML yang menilai **relevansi sepasang teks** (query + dokumen) sekaligus. Lebih akurat dari embedding karena mempertimbangkan interaksi kata antara query dan dokumen.

Model yang dipakai: `cross-encoder/ms-marco-MiniLM-L-6-v2`

```
Query: "Syarat KKP"
Dok A: "Syarat mengambil KKP adalah..." → skor 8.73 (sangat relevan)
Dok B: "Format penulisan laporan..."    → skor 2.15 (kurang relevan)
```

### **CORS (Cross-Origin Resource Sharing)**
Mekanisme keamanan browser. Di proyek ini diset `allow_origins=["*"]` artinya API bisa diakses dari domain mana saja.

---

## D

### **Dense Search / Vector Search**
Pencarian berbasis **makna semantik** menggunakan embedding vector. Berbeda dengan BM25 yang mencari kata, dense search mencari **konsep yang mirip** meski kata-katanya berbeda.

Contoh: "kendaraan roda dua" dan "motor" punya makna serupa → skor tinggi.

---

## E

### **Embedding**
Representasi teks sebagai **vektor angka** (array of float). Teks yang maknanya mirip akan menghasilkan vektor yang dekat dalam ruang multi-dimensi.

```
"Syarat KKP" → [0.023, -0.041, 0.187, ...]  ← 2000 angka
"Ketentuan KKP" → [0.021, -0.039, 0.191, ...] ← dekat dengan yang di atas!
"Resep masak" → [-0.412, 0.891, -0.234, ...] ← jauh berbeda
```

Model: `text-embedding-3-large` dari OpenAI

---

## F

### **FastAPI**
Framework Python untuk membuat REST API yang cepat dan modern. Secara otomatis menghasilkan dokumentasi di `/docs`.

### **FTS (Full-Text Search)**
Pencarian teks lengkap di database menggunakan index. Di Supabase/PostgreSQL menggunakan `tsvector` dengan stemmer bahasa Indonesia.

### **Fallback**
Strategi cadangan ketika operasi utama gagal. Contoh:
- Hybrid search kosong → fallback ke dense-only search
- Reranking gagal → fallback ke top-N tanpa rerank
- Clarification konteks tidak relevan → fallback ke retrieval baru

---

## G

### **GPT (Generative Pre-trained Transformer)**
Keluarga model bahasa dari OpenAI. Di proyek ini menggunakan `gpt-4o-mini` untuk menghasilkan jawaban.

---

## H

### **Hybrid Search**
Menggabungkan dua metode pencarian:
1. **BM25** (keyword/sparse) → bagus untuk istilah spesifik
2. **Vector** (semantic/dense) → bagus untuk pemahaman konteks

Digabung menggunakan **RRF** untuk hasil yang lebih baik dari keduanya.

---

## I

### **IVFFlat (Inverted File with Flat quantization)**
Jenis index untuk pencarian vektor di pgvector. Membagi vektor ke dalam "cluster" sehingga pencarian lebih cepat (tidak perlu bandingkan dengan semua vektor).

Parameter `lists=10` artinya ada 10 cluster untuk ~82 dokumen.

### **Intent Klasifikasi**
Proses menentukan **tujuan** pesan user:
- `NEEDS_RETRIEVAL` → butuh pencarian dokumen
- `CONVERSATIONAL` → sapaan/percakapan biasa
- `CLARIFICATION` → meminta penjelasan lebih dari jawaban sebelumnya

---

## J

### **JSONB**
Format penyimpanan JSON di PostgreSQL yang dioptimalkan untuk query. Di proyek ini kolom `metadata` di `child_documents` menggunakan JSONB agar bisa di-filter dengan GIN index.

---

## L

### **LangChain**
Library Python yang memudahkan pengembangan aplikasi berbasis LLM. Di proyek ini dipakai untuk `ChatPromptTemplate`, `StrOutputParser`, dan integrasi OpenAI.

### **LLM (Large Language Model)**
Model AI berukuran besar yang dilatih untuk memahami dan menghasilkan teks. Contoh: GPT-4o-mini, Claude, Gemini.

### **LRU (Least Recently Used)**
Strategi eviction cache: ketika penyimpanan penuh, hapus item yang paling lama tidak diakses. Di proyek ini dipakai untuk mengelola session memory.

---

## P

### **Parent Chunk**
Dokumen **lengkap** yang menjadi "induk" dari beberapa child chunk. Ukurannya lebih besar dan dikirim ke LLM sebagai konteks karena berisi informasi yang lebih lengkap.

### **pgvector**
Extension PostgreSQL yang menambahkan tipe data `VECTOR` untuk menyimpan dan mencari embedding vektor. Diaktifkan dengan `CREATE EXTENSION vector`.

### **Pipeline**
Serangkaian proses yang dijalankan berurutan. Di proyek ini ada dua pipeline utama:
1. **Ingestion Pipeline:** JSON → Embedding → Supabase
2. **Retrieval Pipeline:** Query → Self-Query → Hybrid Search → Rerank

---

## R

### **RAG (Retrieval-Augmented Generation)**
Teknik menggabungkan **pencarian dokumen** (retrieval) dengan **pembuatan jawaban** (generation) oleh LLM. Hasilnya: jawaban akurat karena berbasis dokumen nyata, bukan "halusinasi" LLM.

```
Tanpa RAG:  LLM hanya pakai pengetahuan training → bisa salah/tidak update
Dengan RAG: LLM diberi konteks dokumen spesifik → jawaban dari sumber terpercaya
```

### **Rate Limiting**
Pembatasan jumlah request dalam waktu tertentu untuk mencegah penyalahgunaan. Di proyek ini ada dua level:
1. **SlowAPI:** 100 request/menit per IP (level server)
2. **Supabase RPC:** 13 pertanyaan/hari per user Telegram (level aplikasi)

### **RLS (Row Level Security)**
Kebijakan keamanan di PostgreSQL yang mengontrol baris data mana yang bisa diakses. Di proyek ini hanya `service_role` yang bisa baca/tulis semua tabel.

### **RPC (Remote Procedure Call)**
Memanggil fungsi yang berjalan di server lain (Supabase) seolah fungsi lokal. Di proyek ini `supabase.rpc("hybrid_search", params)` memanggil fungsi SQL di PostgreSQL.

### **RRF (Reciprocal Rank Fusion)**
Formula matematika untuk menggabungkan beberapa daftar ranking menjadi satu:
```
score = Σ weight × 1/(k + rank_i)
```
- Dokumen yang muncul di peringkat atas **di banyak sistem** mendapat skor tinggi
- Parameter `k=60` mencegah dominasi berlebihan dari ranking pertama

---

## S

### **Self-Query**
Teknik menganalisis pertanyaan user untuk mengekstrak **filter** pencarian secara otomatis. Contoh: "Syarat KKP?" → otomatis filter ke buku panduan KKP.

### **Session**
"Ingatan" percakapan untuk satu user. Di proyek ini disimpan dalam memory in-process (bukan database), dengan TTL agar otomatis bersih.

### **Stemming**
Proses mereduksi kata ke bentuk dasarnya. Contoh: "mengambil", "diambil", "pengambilan" → semua menjadi "ambil". PostgreSQL menggunakan Snowball stemmer untuk bahasa Indonesia.

### **Streaming**
Teknik mengirim jawaban secara bertahap (kata per kata) alih-alih menunggu jawaban penuh. Di proyek ini `RAGChain` mendukung mode `streaming=True` tapi belum dipakai di API utama.

---

## T

### **Telegram Webhook**
Mekanisme di mana Telegram mengirim update pesan ke URL server kita (push), bukan server kita yang terus bertanya ke Telegram (poll). Lebih efisien.

### **Token**
Satuan teks untuk LLM. Kira-kira 1 token ≈ ¾ kata bahasa Inggris. LLM punya batas token per request (context window).

### **TTL (Time To Live)**
Durasi sebelum data dianggap "kadaluarsa" dan dihapus. Di proyek ini session kadaluarsa setelah `SESSION_CLEANUP_INTERVAL` detik (default 3600 detik = 1 jam).

---

## U

### **Uvicorn**
Server ASGI (Asynchronous Server Gateway Interface) yang menjalankan aplikasi FastAPI. Seperti "mesin" yang membuat API bisa diakses melalui HTTP.

### **Upsert**
Operasi database: **Insert** jika data belum ada, **Update** jika sudah ada. Dipakai di ingestion agar tidak duplikat saat menjalankan `--ingest` berkali-kali.

---

## V

### **Vector Similarity**
Mengukur kedekatan dua vektor menggunakan **cosine similarity**:
- Skor 1.0 = identik
- Skor 0.0 = tidak ada hubungan
- Diimplementasikan dengan operator `<=>` di pgvector (cosine distance)

---

## W

### **Webhook**
URL yang menerima notifikasi otomatis dari layanan eksternal. Di proyek ini `/api/telegram/webhook` menerima pesan dari server Telegram.
