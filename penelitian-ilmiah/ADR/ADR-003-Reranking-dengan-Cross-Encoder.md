# ADR-003: Strategi Reranking dengan Cross-Encoder

## 1. Context (Mengapa keputusan ini perlu dibuat?)
Pada arsitektur *Hybrid Search* dengan *Parent-Child Chunking* (ADR-002), basis data (Supabase) akan mengembalikan dokumen-dokumen *child* dengan skor kedekatan vektor dan BM25 (biasanya digabung menggunakan *Reciprocal Rank Fusion*). Ketika dokumen *child* ini dikonversi menjadi *Parent Chunks* (satu bab/sub-bab penuh), urutan peringkat yang dihasilkan oleh basis data belum tentu mencerminkan relevansi *sebenarnya* terhadap pertanyaan pengguna secara keseluruhan.

Selain itu, model bahasa besar (LLM) seperti GPT-4 memiliki fenomena *"Lost in the Middle"*, di mana mereka cenderung mengabaikan informasi yang diletakkan di tengah *prompt*. Oleh karena itu, kita harus membatasi jumlah *Parent Chunks* yang dikirimkan ke LLM (maksimal 3-5 dokumen) dan dokumen yang paling relevan **harus** berada di urutan teratas. Pertanyaannya adalah, bagaimana cara kita menyeleksi dan mengurutkan ulang (*rerank*) kandidat dokumen dari basis data secara akurat sebelum masuk ke LLM?

## 2. Options (Apa saja yang dipertimbangkan?)
Berikut alternatif opsi untuk proses seleksi akhir dokumen:

1. **No Reranking (Pass-through)**: 
   Menerima begitu saja urutan skor *Hybrid/RRF* dari Supabase.
   *Pro*: Sangat cepat (0ms latensi tambahan), tidak menambah beban CPU.
   *Kontra*: Skor dari *Bi-Encoder* (Dense Embedding standar) sering keliru dalam memahami nuansa pertanyaan, sehingga dokumen yang salah bisa menempati urutan nomor 1.
2. **LLM as a Judge (LLM Reranking)**: 
   Menggunakan API LLM (seperti OpenAI) dan meminta (via prompt) untuk memberi skor pada setiap dokumen dari 1-10 berdasarkan relevansinya dengan pertanyaan.
   *Pro*: Paling cerdas dan akurat dalam mengevaluasi relevansi dokumen.
   *Kontra*: Sangat mahal, memakan banyak kuota API, dan menambahkan latensi sangat besar (bisa 2-5 detik hanya untuk proses *reranking*).
3. **Cross-Encoder Model**: 
   Menggunakan model Transformer berukuran kecil khusus (*Cross-Encoder*, misalnya `ms-marco-MiniLM-L-6-v2`) yang dijalankan secara lokal di *server* untuk mengklasifikasi pasangan *Query* dan *Document* sekaligus.
   *Pro*: Akurasi mendekati LLM (karena mengevaluasi *attention* antar kata dalam *query* dan dokumen secara silang), namun jauh lebih ringan dan gratis (open-source).
   *Kontra*: Menambah beban komputasi/memori pada *server application*.

## 3. Decision (Apa yang dipilih dan kenapa?)
Kami memutuskan untuk memilih **Opsi 3: Cross-Encoder Model**.

**Alasan Utama:**
Dalam kasus ini, **mendapatkan urutan Top-3 yang sempurna** tanpa menghancurkan anggaran (API cost) atau menyebabkan waktu tunggu berlebihan (*latency*) adalah prioritas utama. 
- Opsi 3 memberikan kualitas penalaran (*reasoning*) dokumen yang jauh melampaui sekadar mengandalkan hasil Supabase (Opsi 1), sekaligus menjaga biaya tetap Rp0 dan menghindari latensi tinggi yang dihasilkan API pihak ketiga (Opsi 2).
- Proses komputasi *Cross-Encoder* ini cukup efisien dan masih sanggup dijalankan di atas infrastruktur CPU server standar tanpa memerlukan GPU khusus, karena modelnya ringan (MiniLM).

## 4. Consequence (Apa yang harus diterima?)
Menggunakan *Cross-Encoder* lokal sebagai penengah dalam arsitektur RAG membawa beberapa *trade-off*:

1. **Peningkatan Beban Komputasi dan Memori**: *Container* FastAPI sekarang tidak hanya sekadar menjadi penyalur data, melainkan juga harus menjalankan *inference* Machine Learning secara lokal. Ini memakan lebih banyak RAM (sekitar 300-500MB ekstra) dan *cycle* CPU.
2. **Latensi Operasional**: Mengeksekusi *inference* pada CPU menambah jeda operasi sekitar ~200-500ms pada *pipeline* sebelum pertanyaan dikirimkan ke LLM.
3. **Pembengkakan Ukuran Container / Waktu Inisialisasi**: Model pembobotan (*weights*) HuggingFace harus di-*download*. Jika diunduh saat *runtime* (inisialisasi aplikasi), akan memperparah masalah *cold start latency*. Jika *di-bake* ke dalam *Docker image*, ukuran *image* akan bertambah beberapa ratus megabyte.
