# ADR-002: Strategi Retrieval Hierarkis dan Hybrid Search

## 1. Context (Mengapa keputusan ini perlu dibuat?)
Kualitas dari sistem Chatbot berbasis *Retrieval-Augmented Generation* (RAG) sangat bergantung pada kualitas dokumen (*context*) yang berhasil diambil (*retrieved*). Dokumen sumber untuk aplikasi ini adalah Buku Panduan KKP dan PI yang memiliki struktur kompleks: berbab-bab, memiliki banyak pasal, prosedur bernomor, dan lampiran tata tulis.

Jika kita hanya memotong teks menjadi ukuran tetap (misal 500 token), potongan (*chunk*) teks tersebut seringkali terlepas dari konteks awalnya. Misalnya, sebuah daftar persyaratan mungkin terpotong dari judul bab "Persyaratan KKP", sehingga LLM tidak tahu daftar tersebut berlaku untuk apa. Selain itu, *constraint* yang kita miliki adalah keharusan Chatbot untuk menjawab dengan sitasi spesifik (misal: "Berdasarkan BAB II..."), sehingga konteks asal harus tetap utuh. Di sisi lain, *context window* dari LLM dan biaya *token* membatasi jumlah teks raksasa yang bisa kita masukkan secara bersamaan.

## 2. Options (Apa saja yang dipertimbangkan?)
Berikut adalah beberapa strategi *chunking* dan *retrieval* yang dievaluasi:

1. **Standard Fixed-Size Chunking + Pencarian BM25 (Keyword)**: 
   Memotong PDF menjadi paragraf 500 token. Pencarian hanya berdasarkan kecocokan kata kunci eksak (BM25).
   *Pro*: Sangat cepat, sederhana, bagus untuk mencari akronim atau nomor form spesifik.
   *Kontra*: Mudah kehilangan makna semantik dan batasan dokumen.
2. **Semantic Chunking + Pencarian Dense Embedding (Vector)**: 
   Memotong teks berdasarkan kesamaan semantik kalimat. Pencarian menggunakan representasi vektor (Embedding).
   *Pro*: Sangat pintar dalam menangani sinonim atau pertanyaan yang diketik ulang secara implisit.
   *Kontra*: Sering gagal menemukan kata kunci eksak (seperti "Formulir PI-04").
3. **Parent-Child Chunking + Hybrid Search (Dense + BM25 + Reciprocal Rank Fusion)**: 
   Dokumen diekstrak dan dipecah secara hierarkis. *Child chunks* (potongan kecil, spesifik, 100-300 kata) dibuat khusus untuk di-*index* dan dicari. Namun, ketika *child chunk* ditemukan, sistem tidak mengembalikan *child* tersebut ke LLM, melainkan mengambil keseluruhan *Parent chunk* (misal: satu sub-bab utuh) yang memayunginya. Pencariannya pun digabung (*Hybrid*) antara Vector (Dense) dan Keyword (BM25).

## 3. Decision (Apa yang dipilih dan kenapa?)
Kami memutuskan untuk memilih **Opsi 3: Parent-Child Chunking + Hybrid Search**.

**Alasan Utama:**
Dalam konteks dokumen akademik dan regulasi (Buku Panduan), **akurasi semantik, ketersediaan kata kunci eksak, dan pelestarian konteks dokumen** jauh lebih penting dibandingkan **kompleksitas arsitektur ingestion dan waktu pemrosesan awal**.
- Opsi 3 mengombinasikan keunggulan A dan B sekaligus (*Hybrid*), memastikan sistem mampu mencari makna tersirat sekaligus nomor form eksak.
- Arsitektur *Parent-Child* memungkinkan pencarian dilakukan di tingkat granuler (mikro) melalui *Child*, namun LLM diberikan informasi di tingkat makro (*Parent*). Ini menjamin bahwa jawaban LLM tidak akan kehilangan konteks asal dan mampu memberikan sitasi bab ("Berdasarkan BAB V...") dengan presisi sempurna. 

## 4. Consequence (Apa yang harus diterima?)
Setiap keputusan desain yang canggih pasti memiliki harga/kerugian. Dengan mengadopsi pola *Parent-Child Hybrid Search*, kita harus menerima konsekuensi berikut:

1. **Kompleksitas Ingestion (Pemrosesan Data)**: Kode (skrip ekstraksi PDF di folder `extract-pdf`) menjadi jauh lebih sulit dipelihara. Kita tidak bisa lagi menggunakan *loader* dokumen standar Langchain, melainkan harus menulis ekstraktor *custom* berbasis *regex* atau struktur *markdown* untuk memetakan hubungan antara *parent_id* dan *child_ids*.
2. **Kebutuhan Storage yang Membengkak**: Kita harus menyimpan data ganda di basis data (Supabase). Satu tabel besar untuk *Parent Chunks* dan satu tabel lebih besar lagi untuk *Child Chunks* beserta *vector embedding*-nya.
3. **Peningkatan Latensi Retrieval**: Saat proses tanya jawab berlangsung, aplikasi harus melakukan beberapa lompatan (*query hop*): mencari *child* yang relevan via RPC di Supabase, mengurai *parent_id*, baru kemudian melakukan *query* sekunder untuk menarik *parent chunk*-nya. Ini menambah latensi beberapa puluh/ratus milidetik dibandingkan pencarian vektor tunggal yang sederhana.
