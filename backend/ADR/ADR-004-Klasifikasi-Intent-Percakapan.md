# ADR-004: Klasifikasi Intent Percakapan (Intent Classification)

## 1. Context (Mengapa keputusan ini perlu dibuat?)
Sebagai sebuah "Chatbot", pengguna tidak selalu mengirimkan kueri spesifik berisi kata kunci dokumen (seperti gaya pencarian di Google). Seringkali pengguna mengirimkan pesan basa-basi ("Halo", "Terima kasih banyak", "Pagi min"), atau pertanyaan lanjutan yang tidak bermakna tanpa riwayat percakapan ("Lalu bagaimana syaratnya?", "Berapa lama proses itu?").

Masalah timbul karena *pipeline* RAG secara bawaan (*default*) sangat "berat". Sebuah pertanyaan akan di-*embed*, dicari di Supabase (*Hybrid*), di-*fetch parent*-nya, di-*rerank*, dan dikirim ke LLM. Jika sistem menjalankan seluruh proses panjang ini hanya untuk menjawab pesan "Halo", kita akan membuang-buang uang (API LLM), waktu proses (CPU untuk *embedding* & *reranker*), dan menghasilkan respons yang aneh. Sebaliknya, jika pengguna bertanya *follow-up*, sistem tidak akan bisa mencarinya di basis data tanpa merumuskan ulang pertanyaannya. Batasan utama di sini adalah biaya API OpenAI, *latency* (*waktu tunggu pengguna*), dan kualitas percakapan dinamis (UX).

## 2. Options (Apa saja yang dipertimbangkan?)
Berikut alternatif opsi penanganan *multi-turn chat* pada *pipeline* RAG:

1. **Jalankan Full RAG untuk Setiap Pesan**: 
   Memaksa setiap input pengguna masuk ke dalam *pipeline* pencarian dokumen.
   *Pro*: Arsitektur sangat sederhana, tidak ada kode tambahan.
   *Kontra*: Sangat mahal (API LLM & CPU usage), lambat, dan tidak intuitif untuk percakapan sosial. RAG akan gagal mengambil dokumen untuk *follow-up question*.
2. **Rule-based/Regex Gateway**: 
   Membangun daftar kata kunci (misal: "halo", "hai", "makasih") dengan `if-else` untuk mencegat (*intercept*) pertanyaan sebelum masuk ke RAG.
   *Pro*: Cepat (0ms latensi) dan gratis.
   *Kontra*: Kaku, rentan gagal terhadap nuansa bahasa manusia yang tidak terprediksi. Tidak bisa menyelesaikan masalah *follow-up question*.
3. **LLM Intent Classifier Pre-processing**: 
   Menggunakan panggilan LLM murah dan cepat sebelum *pipeline* berjalan, untuk mengklasifikasikan *Intent* (niat) pengguna menjadi:
   - `CONVERSATIONAL` (basa-basi) -> Langsung dijawab tanpa mencari dokumen.
   - `CLARIFICATION` (follow-up) -> Dijawab menggunakan konteks dokumen dari pesan sebelumnya.
   - `NEEDS_RETRIEVAL` (pertanyaan baru) -> Pertanyaan dirumuskan ulang (*reformulate*) dan diteruskan ke *Full RAG Pipeline*.

## 3. Decision (Apa yang dipilih dan kenapa?)
Kami memutuskan untuk memilih **Opsi 3: LLM Intent Classifier Pre-processing**.

**Alasan Utama:**
Meskipun kita menambah kompleksitas di awal, **Pengalaman Pengguna (User Experience) dan Efisiensi API secara keseluruhan** jauh lebih krusial. 
- Opsi 3 mengorbankan sedikit latensi di awal untuk secara cerdas menghentikan *pipeline* berat secara prematur jika memang tidak dibutuhkan.
- Menggunakan LLM (gpt-4o-mini) sebagai juri pengklasifikasi jauh lebih adaptif terhadap tata bahasa mahasiswa (bahasa *slang* atau ketikan salah/typo) dibanding pendekatan berbasis aturan/regex statis (Opsi 2).
- Secara signifikan memperbaiki kualitas pencarian RAG karena pertanyaan lanjutan yang ambigu akan dirumuskan ulang (*Query Reformulation*) terlebih dahulu sebelum dicari di basis data.

## 4. Consequence (Apa yang harus diterima?)
Mengimplementasikan *routing* berbasis *Intent* ini mengharuskan kita menerima kompromi berikut:

1. **Pertanyaan RAG Menjadi Lebih Lambat**: Untuk pertanyaan riil yang memang butuh dokumen akademik (`NEEDS_RETRIEVAL`), sistem kini harus melakukan *dua kali* pemanggilan LLM ke OpenAI (satu untuk klasifikasi/reformulasi, satu lagi untuk generasi jawaban). Ini memperpanjang waktu tunggu agregat.
2. **Ketergantungan Absolut pada Akurasi Classifier**: Jika *prompt* klasifikasi gagal dan LLM keliru menganggap sebuah pertanyaan akademis penting sebagai `CONVERSATIONAL` (basa-basi), sistem akan mem-*bypass* proses *retrieval* dan justru mendorong LLM utama untuk *berhalusinasi* karena ia tidak diberikan dokumen pedoman yang dibutuhkan.
3. **Pengelolaan State Memory**: Sistem kini wajib menyimpan riwayat pesan pengguna dan bot ke dalam memori (*ConversationMemory*) dengan benar agar *Intent Classifier* punya acuan untuk mendeteksi konteks *follow-up*.
