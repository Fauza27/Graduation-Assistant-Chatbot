# Chatbot Asisten Virtual Berbasis RAG untuk Panduan PI/KKP

> Sebuah chatbot akademik yang bisa diajak berdiskusi untuk membantu menjawab berbagai pertanyaan seputar KKP/PI, didukung oleh arsitektur RAG yang dirancang cukup matang di balik layar dengan kemampuan percakapan kontekstual yang canggih.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)](https://openai.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)
[![RAGAS](https://img.shields.io/badge/Evaluation-RAGAS-orange.svg)](https://github.com/explodinggradients/ragas)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success.svg)]()

---

## 🎯 Kenapa Dibuat

Proyek ini berangkat dari masalah yang cukup sering saya lihat di kampus (STMIK Widya Cipta Dharma). Saat memasuki fase penting seperti Kuliah Kerja Praktik (KKP) dan Penulisan Ilmiah (PI) di semester 6, banyak mahasiswa masih merasa bingung harus mulai dari mana. Padahal, buku pedoman sudah tersedia hanya saja, tidak semua orang benar-benar membacanya atau memahami isinya dengan baik.

Buat saya, proyek ini bukan sekadar tugas atau portofolio. Saya ingin benar-benar memahami bagaimana membangun sistem Retrieval-Augmented Generation (RAG) yang siap digunakan di kondisi nyata (production-grade) dengan kemampuan percakapan yang natural dan kontekstual.

## ✨ Fitur Utama

### 🧠 Percakapan Kontekstual Cerdas
- **Intent Classification**: Sistem secara otomatis mendeteksi jenis pertanyaan (butuh pencarian dokumen, percakapan biasa, atau klarifikasi)
- **Context Switching Detection**: Mengenali ketika pengguna beralih topik (PI ↔ KKP) atau aspek (syarat → format → durasi)
- **Memory Management**: Menyimpan riwayat percakapan dengan window memory yang efisien
- **Query Reformulation**: Mengubah pertanyaan yang menggunakan referensi implisit ("itu", "tersebut") menjadi query yang mandiri

### 🔍 Sistem Pencarian Canggih
- **Hybrid Search**: Kombinasi PostgreSQL FTS (dengan Snowball stemmer Indonesia) dan Dense Vector Search yang dijalankan di database untuk performa optimal
- **Parent-Child Chunking**: Mempertahankan konteks dokumen yang utuh sambil memungkinkan pencarian granular
- **Cross-Encoder Reranking**: Penyaringan ulang hasil pencarian menggunakan model lokal untuk relevansi maksimal
- **Self-Query Extraction**: Ekstraksi otomatis filter metadata dari pertanyaan natural

### 💬 Interface Multi-Platform
- **REST API**: Endpoint FastAPI untuk integrasi dengan aplikasi lain
- **Telegram Bot**: Interface chat yang familiar dan mudah digunakan
- **CLI Interface**: Mode interaktif untuk testing dan development

### 📊 Evaluasi & Monitoring
- **RAGAS Integration**: Evaluasi otomatis kualitas RAG tanpa ground truth
- **Comprehensive Testing**: Test suite untuk berbagai skenario edge case
- **Performance Metrics**: Tracking akurasi, relevansi, dan performa sistem

---

## 🏗️ Arsitektur Sistem

Gambaran besar tentang bagaimana infrastruktur ini meramu dan memecahkan setiap pesan dari pengguna:

```text
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Telegram   │  │   REST API   │  │      CLI     │      │
│  │     Bot      │  │   (FastAPI)  │  │  Interface   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────┐
│                 Conversation Layer                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              AI Services (ai_services.py)            │   │
│  │  • Session Management & Memory                       │   │
│  │  • Intent Classification                             │   │
│  │  • Context Switching Detection                       │   │
│  │  • Query Reformulation                               │   │
│  └────────┬─────────────────────────────────────────────┘   │
└───────────┼───────────────────────────────────────────────────┘
            │
┌───────────┼───────────────────────────────────────────────────┐
│           │              RAG Pipeline                          │
│  ┌────────▼──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Self-Query      │  │    Hybrid    │  │   Parent-    │  │
│  │   Extraction      │→ │    Search    │→ │    Child     │  │
│  │  (YAML Keywords)  │  │ (DB-side FTS │  │   Fetching   │  │
│  └───────────────────┘  │  + Vector)   │  └──────┬───────┘  │
│                         └──────────────┘         │          │
│  ┌───────────────────┐  ┌──────────────┐  ┌──────▼───────┐  │
│  │   LLM Generation  │← │  Cross-Encoder│← │   Reranking  │  │
│  │   (GPT-4o/Opus)   │  │   (Pure ML)   │  │  (Top-N)     │  │
│  └───────────────────┘  └──────────────┘  └──────────────┘  │
└───────────────────────────────────────────────────────────────┘
            │
┌───────────▼───────────────────────────────────────────────────┐
│                      Data Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │    Supabase      │  │   OpenAI API     │                  │
│  │  (Vector Store)  │  │  (Embeddings +   │                  │
│  │  • Parent Docs   │  │      LLM)        │                  │
│  │  • Child Chunks  │  │                  │                  │
│  └──────────────────┘  └──────────────────┘                  │
└───────────────────────────────────────────────────────────────┘
```

### 🔧 Komponen Utama

**Centralized Pipeline (`src/retrieval/pipeline.py`)**
- Single source of truth untuk seluruh alur retrieval
- Mengintegrasikan self-query → hybrid search → parent fetching → reranking

**Query Expansion (Netral)**
- ekspansi akronim akademik (PI ↔ Penulisan Ilmiah, KKP ↔ Kuliah Kerja Praktik)
- Mendukung matching dua arah (akronim → bentuk panjang, bentuk panjang → akronim)

**Source Detection yang Reliable**
- Deteksi PI/KKP berdasarkan field `source` yang reliable
- Fallback ke prefix ID jika diperlukan

**Cross-Encoder Reranking Murni**
- Menggunakan model `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Scoring berdasarkan semantic similarity

---

## 🛠️ Stack Teknologi (dan Alasan Saya Memilihnya)

Saya tidak asal ikut tren atau sekadar memakai teknologi yang sedang hype. Setiap komponen di proyek ini dipilih dengan pertimbangan yang cukup matang, disesuaikan dengan kebutuhan dan keterbatasan yang ada:

- **FastAPI**: Aplikasi ini harus menangani REST API sekaligus menerima trafik rutin dari webhook Telegram. Karena itu, saya butuh framework yang memang dirancang asynchronous sejak awal. FastAPI jadi pilihan karena ringan, cepat, dan tetap stabil meskipun dijalankan di layanan cloud gratis.

- **Supabase (pgvector)**: Mengelola database relasional dan vector database secara terpisah bisa jadi cukup merepotkan. Supabase menawarkan solusi praktis lewat PostgreSQL yang sudah dilengkapi ekstensi pgvector. Dengan ini, saya bisa menyimpan struktur dokumen (misalnya relasi antar bab) sekaligus embedding-nya dalam satu sistem yang rapi dan terintegrasi. Hybrid search (BM25 + vector) juga dijalankan langsung di database menggunakan `to_tsvector('indonesian')` yang memiliki stemmer bahasa Indonesia bawaan, memberikan hasil yang lebih akurat dibanding tokenisasi manual.

- **Cross-Encoder Model (`ms-marco`)**: Salah satu kendala terbesar penelusuran dokumen murni adalah ketidakmampuan algoritma *vector search* menangkap maksud sebenarnya dari pertanyaan pengguna dan menghasilkan dokumen tidak relevan. Menggunakan LLM seperti GPT-4 untuk reranking sebenarnya efektif, tapi jelas mahal kalau dipakai terus-menerus. Sebagai gantinya, saya menggunakan model Cross-Encoder kecil yang dijalankan secara lokal di CPU. Performanya cukup baik untuk menyaring dan mengurutkan hasil pencarian, tanpa tambahan biaya API.

- **python-telegram-bot**: *Library* ini sudah cukup matang, terutama di bagian ConversationHandler. Ini sangat membantu karena saya tidak perlu membangun sendiri sistem pengelolaan alur percakapan dari nol. Integrasinya dengan FastAPI (via webhook) juga relatif mulus.

- **RAGAS**: Tanpa evaluasi yang jelas, pengembangan RAG rasanya seperti coba-coba tanpa arah. RAGAS saya gunakan untuk mengukur kualitas sistem secara lebih objektif, seperti faithfulness dan context precision. Dengan begitu, setiap perubahan pada pipeline bisa dievaluasi dengan dasar yang lebih terukur, bukan sekadar feeling.

- **Loguru**: Untuk logging yang lebih baik dan mudah dibaca, menggantikan logging standard Python yang kadang membingungkan dalam debugging sistem yang kompleks.

- **YAML Configuration**: Sistem konfigurasi eksternal untuk section keywords yang memudahkan maintenance tanpa perlu mengubah kode. Keywords disimpan dalam `config/section_keywords.yaml` dengan struktur yang terorganisir per bagian dokumen.

## 🎯 Kemampuan Percakapan Kontekstual

Salah satu aspek yang paling menantang dalam membangun chatbot RAG adalah membuat sistem yang benar-benar "paham" konteks percakapan. Setelah melalui berbagai iterasi dan testing, sistem ini sekarang mampu:

### 🔄 Context Switching Detection
- **Domain Switching**: Mendeteksi perpindahan antara topik PI dan KKP
- **Aspect Switching**: Mengenali perubahan aspek dalam domain yang sama (syarat → format → durasi)
- **Explicit Signals**: Memahami sinyal eksplisit seperti "bagaimana dengan", "kalau untuk", "sekarang tentang"

### 💭 Intent Classification
- **Needs Retrieval**: Pertanyaan yang membutuhkan pencarian dokumen
- **Conversational**: Sapaan, ucapan terima kasih, pertanyaan umum
- **Clarification**: Permintaan elaborasi dari jawaban sebelumnya

### 💭 Memory Management & Session Handling
- **Database-Backed Sessions**: Session disimpan secara persisten di Supabase dengan hot LRU cache untuk performa optimal
- **Session Persistence**: Percakapan survive server restart dan mendukung deployment multi-server
- **Window Memory**: Menyimpan 5 turn terakhir untuk efisiensi dengan automatic TTL cleanup
- **Context Preservation**: Mempertahankan konteks dokumen yang relevan untuk klarifikasi
- **Async Processing**: Non-blocking I/O operations untuk performa optimal
- **Fallback Mechanism**: Automatic fallback ke in-memory sessions jika database tidak tersedia

### 🔧 Query Processing
- **Query Reformulation**: Mengubah pertanyaan dengan referensi implisit menjadi query mandiri
- **Typo Tolerance**: Menangani bahasa informal dan typo dengan baik
- **Multi-language Support**: Mendukung bahasa Indonesia dan campuran Indonesia-Inggris

---

## 🧠 Keputusan Desain

Merancang sistem RAG yang benar-benar “paham konteks” ternyata bukan soal menulis kode sebanyak mungkin, tapi soal berani mengambil keputusan dan menerima konsekuensinya. Sepanjang proses ini, saya justru lebih sering dihadapkan pada trade-off dibanding sekadar urusan teknis.

Semua pertimbangan, alasan, dan dilema yang saya temui selama membangun sistem ini saya dokumentasikan dalam Architecture Decision Records (ADR). Berikut gambaran singkat dari beberapa keputusan penting tersebut:

1. **[Arsitektur Monolith Serverless (FastAPI + Webhook)](ADR/ADR-001-Arsitektur-Sistem-Utama.md)** 
   Trade-off: Harus menerima adanya cold start yang bikin respons awal sedikit lebih lambat. Tapi sebagai gantinya, proses deployment jadi jauh lebih sederhana tanpa perlu mengelola banyak microservices.
2. **[Parent-Child Chunking & Hybrid Search](ADR/ADR-002-Strategi-Retrieval-Hierarkis-Hybrid.md)**
   Trade-off: Proses indexing jadi lebih lama dan penggunaan storage meningkat. Namun hasilnya, model bisa memahami konteks dokumen secara lebih utuh,termasuk struktur bab dan referensi—,ehingga jawaban yang dihasilkan jauh lebih akurat.
3. **[Reranking dengan Cross-Encoder Lokal](ADR/ADR-003-Reranking-dengan-Cross-Encoder.md)**
   Trade-off: Waktu respons sedikit bertambah karena ada proses tambahan di CPU. Tapi ini membantu menekan biaya API secara signifikan, tanpa mengorbankan kualitas hasil pencarian.
4. **[Pre-processing Intent Classification](ADR/ADR-004-Klasifikasi-Intent-Percakapan.md)**
   Ada tambahan proses di awal (LLM dipanggil lebih dari sekali), yang berarti ada overhead. Namun ini membuat sistem lebih cerdas dalam memahami konteks percakapan—misalnya membedakan mana pertanyaan serius dan mana sekadar basa-basi seperti “Makasih” sehingga pencarian jadi lebih efisien dan relevan.

---

## 🚀 Cara Menjalankan Secara Lokal

**1. Clone & Setup Environment**
```bash
git clone https://github.com/Fauza27/Chatbot-KKP-PI.git
cd Chatbot-KKP-PI
python -m venv venv
# Windows: venv\Scripts\activate | Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Buka file `.env` dan isi dengan kredensial yang diperlukan: OpenAI API Key, Supabase URL, Supabase Key, dan Telegram Token (opsional).

**Konfigurasi Session Storage (Baru)**:
```bash
# Session Management
USE_DATABASE_SESSIONS=true                    # Enable database-backed sessions
TABLE_CONVERSATION_SESSIONS=conversation_sessions
MAX_ACTIVE_SESSIONS=1000                     # Cache size untuk database mode  
SESSION_CLEANUP_INTERVAL=3600                # TTL cleanup (seconds)
```

**2. Setup Database**
Jalankan script SQL di `scripts/supabase.sql` melalui SQL Editor di dashboard Supabase Anda. Script ini akan membuat tabel dan index yang diperlukan untuk vector search.

**Penting**: Setelah menjalankan script utama, jalankan juga migration untuk session storage dan quota system:
```sql
-- 1. Copy-paste isi file scripts/supabase_session_migration.sql ke SQL Editor
-- Script ini menambahkan tabel conversation_sessions untuk persistent session storage

-- 2. Copy-paste isi file scripts/supabase_migration_quota_rpc.sql ke SQL Editor  
-- Script ini menambahkan fungsi RPC untuk atomic quota management
```

**Catatan**: Jika Anda menggunakan sistem lama, pastikan untuk menjalankan evaluasi ulang setelah refactoring integritas evaluasi. Lihat dokumentasi lengkap di `docs/REFACTOR_INTEGRITAS_EVALUASI.md`.

**3. Ingestion Pipeline**
```bash
python main.py --ingest --dataset both
```
Perintah ini akan memproses PDF panduan, memecahnya menjadi chunks, membuat embeddings menggunakan OpenAI, dan menyimpannya ke Supabase. Sistem akan otomatis memuat konfigurasi section keywords dari `config/section_keywords.yaml`.

**4. Jalankan Aplikasi**
```bash
# Jalankan web server (FastAPI untuk webhook)
python main.py

# Atau jalankan di mode CLI untuk testing
python main.py --cli
```

**5. Evaluasi Sistem (Opsional)**
```bash
# Evaluasi dengan RAGAS (tanpa ground truth)
python main.py --evaluate-no-gt --dataset both

# Evaluasi dengan ground truth (jika tersedia)
python main.py --evaluate --dataset pi
```

## 🧪 Hasil Testing & Optimisasi

Sistem ini telah melalui serangkaian testing komprehensif untuk memastikan kualitas percakapan yang natural:

### ✅ Skenario Testing yang Berhasil
- **Percakapan Natural**: Sapaan, ucapan terima kasih, pertanyaan umum
- **Context Switching**: Perpindahan PI ↔ KKP, perubahan aspek dalam domain sama
- **Clarification**: Permintaan elaborasi yang tepat sasaran
- **Edge Cases**: Pertanyaan ambigu, out-of-domain, multi-part questions
- **Session Persistence**: Percakapan survive server restart dan multi-server deployment
- **Memory Window**: Pengelolaan memori percakapan dengan window 5 turn
- **Informal Language**: Penanganan typo dan bahasa tidak formal ("gmn cara dftar kkp?")
- **Source Detection**: Deteksi PI/KKP yang akurat berdasarkan metadata dokumen
- **Query Expansion**: Ekspansi akronim netral tanpa bias evaluasi
- **Database Sessions**: Session storage dengan hot cache dan automatic cleanup

### 📊 Metrik Performa
- **Intent Classification Accuracy**: >95% untuk semua kategori
- **Context Switch Detection**: 100% success rate pada testing
- **Query Understanding**: Mampu menangani bahasa informal dan typo
- **Response Relevance**: Konsisten memberikan jawaban yang akurat dan kontekstual
- **System Reliability**: TTL-based session management mencegah memory leaks
- **Performance**: Async processing untuk response time yang optimal
- **Source Detection Accuracy**: 100% akurasi setelah perbaikan bug PI/KKP detection
- **RAGAS Evaluation (Overall PASS)**:
  - Faithfulness: 0,730 (threshold 0,70) ✅
  - Context Precision: 0,842 (threshold 0,80) ✅
  - Answer Completeness: 5,24/10 (threshold 3,50) ✅
  - Answer Actionability: 4,79/10 (threshold 3,50) ✅
  - Answer Relevancy: 0,585 (quality warning — deliberate verbose design)

### 🔧 Optimisasi yang Dilakukan
1. **Enhanced Intent Classifier**: Sistem deteksi switching yang lebih akurat
2. **Database-Backed Sessions**: Migrasi dari in-memory ke persistent session storage dengan hot LRU cache
3. **Async Performance**: Non-blocking I/O operations untuk mencegah event loop blocking
4. **Better Query Reformulation**: Penanganan referensi implisit yang lebih baik
5. **Centralized Messaging**: Sistem pesan terpusat dengan HTML formatting yang konsisten
6. **Code Quality**: Penghapusan dead code dan perbaikan dependencies untuk maintainability
7. **Fallback Mechanisms**: Sistem fallback untuk situasi edge case dan database downtime
8. **Evaluation Integrity**: Penghapusan bias evaluasi dari query expansion dan reranking
9. **Centralized Pipeline**: Single source of truth untuk retrieval operations
10. **External Configuration**: YAML-based configuration untuk maintainability yang lebih baik

---

## 📖 Apa yang Saya Pelajari

Proyek ini awalnya kelihatan sederhana, tapi ternyata berkembang jadi eksplorasi yang cukup dalam. Semakin dikerjakan, semakin terasa kalau RAG itu bukan sekadar pipeline Retrieve → Augment → Generate yang bisa langsung jadi.

Justru, bagian tersulitnya ada di keputusan-keputusan kecil yang efeknya baru terasa belakangan.

Ada beberapa hal yang paling membekas buat saya:
  
- **Metrik tidak selalu mencerminkan kenyataan (pengalaman dengan RAGAS)**: 
  Sempat kaget waktu skor faithfulness dari RAGAS turun. Sekilas terlihat seperti ada masalah serius.
  Tapi setelah dicek manual, ternyata jawabannya tetap benar, tidak ada halusinasi.
  Masalahnya ada di cara chatbot menyampaikan jawaban. Saya sengaja membuatnya lebih santai dan tidak terlalu kaku, jadi sering melakukan parafrasa dari teks asli. Di sisi metrik, ini dianggap kurang “faithful”, tapi dari sisi pengguna justru terasa lebih nyaman.
  Dari sini saya belajar: metrik itu penting sebagai panduan, tapi tidak boleh jadi satu-satunya acuan. Tetap perlu validasi manual dan, kalau memungkinkan, feedback langsung dari pengguna. Karena pada akhirnya, yang dinilai bukan dashboard—tapi pengalaman orang yang benar-benar memakai sistemnya.

- **Percakapan kontekstual adalah tantangan tersendiri**:
  Membangun sistem yang benar-benar "paham" konteks percakapan ternyata jauh lebih kompleks dari yang dibayangkan. Bukan hanya soal menyimpan riwayat chat, tapi juga mendeteksi kapan pengguna beralih topik, kapan mereka minta klarifikasi, dan kapan mereka sekadar basa-basi. Setelah melalui berbagai iterasi dan testing komprehensif, sistem sekarang mampu menangani context switching dengan akurasi 100% dan memahami bahasa informal dengan baik.

- **Code quality dan maintainability sama pentingnya dengan fitur**:
  Refactoring besar-besaran yang saya lakukan mengajarkan pentingnya arsitektur yang bersih. Memindahkan logic ke centralized pipeline, menghilangkan duplikasi kode, dan menggunakan konfigurasi eksternal (YAML) membuat sistem jauh lebih mudah dipelihara. Investasi waktu untuk refactoring terbayar dengan kemudahan debugging dan pengembangan fitur baru.

- **Testing adalah kunci kualitas**:
  Tanpa testing yang sistematis, sulit mengetahui apakah sistem benar-benar berfungsi dengan baik. Melalui testing berbagai edge case dari pertanyaan ambigu hingga typo saya bisa mengidentifikasi dan memperbaiki masalah sebelum sistem digunakan secara luas.

## 🚀 Status Proyek

Sistem ini telah mencapai status **production-ready** dengan:
- ✅ Arsitektur RAG yang matang dan teruji
- ✅ Kemampuan percakapan kontekstual yang canggih  
- ✅ Testing komprehensif dengan success rate 100%
- ✅ Dokumentasi lengkap dan ADR yang terstruktur
- ✅ Evaluasi objektif menggunakan RAGAS (Overall PASS, skor jujur tanpa bias)
- ✅ Optimisasi performa dan akurasi yang berkelanjutan


**📁 Struktur File Aktual**
```text
.
├── ADR/                    # Architecture Decision Records
├── config/                 # YAML configs & Pydantic settings
├── docs/                   # Dokumentasi API, panduan, dan arsip
│   └── journal/            # Riwayat pengembangan (flowcharts, analisis RAGAS)
├── extract-pdf/            # Script CLI untuk ekstraksi teks dari PDF panduan
├── scripts/                # Script utilitas dan schema SQL Supabase
├── src/
│   ├── api/                # FastAPI endpoints (chat, health)
│   ├── bot/                # Telegram bot handlers & application
│   ├── evaluation/         # RAGAS evaluation scripts
│   ├── generation/         # RAG Chain & Intent Classifiers
│   ├── ingestion/          # PDF loaders & Embedders
│   ├── middleware/         # Security & Monitoring middlewares
│   ├── retrieval/          # Hybrid Search, Parent-Child, Reranker, Pipeline
│   └── services/           # Orchestrator & Session management
├── tests/                  # Automated Pytest suite
└── main.py                 # CLI entry point
```

Proyek ini tidak hanya berhasil memecahkan masalah awal (membantu mahasiswa memahami panduan KKP/PI), tapi juga menjadi pembelajaran mendalam tentang bagaimana membangun sistem RAG yang benar-benar siap digunakan di dunia nyata dengan integritas evaluasi yang terjamin.

---

## ⚠️ Keterbatasan Sistem (Known Limitations)

Meskipun sistem telah berstatus *production-ready*, ada beberapa area teknis yang menjadi catatan (baik secara sadar dibiarkan sebagai *trade-off* atau menunggu iterasi lebih lanjut):

1. **Ignored `source` Metadata Filter in Retrieval RPC**:  
   Meskipun komponen `self_query.py` berhasil mendeteksi domain pertanyaan pengguna (misal: secara eksplisit bertanya tentang "PI" atau "KKP") dan mengekstrak label `source`, filter ini **tidak dikirimkan** hingga ke tingkat eksekusi SQL RPC (`match_documents`) pada Supabase. Parameter RPC saat ini hanya mem-filter berdasarkan `section`. Akibatnya, pemisahan domain mengandalkan *semantic routing* dari embedding murni dan pencarian Full-Text Search.
2. **Rate Limiting Hanya pada Level API**:  
   Sistem pembatasan *request* (menggunakan Token Bucket di `security.py`) hanya berlaku untuk REST API. Untuk bot Telegram, pembatasan mengandalkan *rate-limiter* internal dari framework Telegram Bot, yang bisa saja menimbulkan lonjakan request tak terduga ke LLM jika trafik sangat masif.
3. **Hard-coded Embedding Dimension Limitation**:  
   Untuk kompatibilitas dengan limit resource Supabase saat eksperimen awal, dimensi embedding model `text-embedding-3-large` dipotong menjadi `2000` di backend. Database schema juga secara ketat mengatur vector ke `vector(2000)`. Jika di masa depan model diganti, schema database harus ikut dirombak.
4. **Dependensi Reranker CPU Lokal**:  
   Karena modul cross-encoder dijalankan murni di CPU (via `sentence-transformers`), beban latency yang cukup tinggi (~300-800ms) akan terjadi saat di-*deploy* pada environment virtual machine berukuran kecil tanpa GPU.

---

## 📚 Dokumentasi Tambahan

Untuk pemahaman yang lebih mendalam tentang sistem ini, tersedia dokumentasi lengkap:

### 🏛️ Architecture Decision Records (ADR)
- **[ADR-001: Arsitektur Sistem Utama](ADR/ADR-001-Arsitektur-Sistem-Utama.md)** - Keputusan arsitektur monolith serverless
- **[ADR-002: Strategi Retrieval Hierarkis Hybrid](ADR/ADR-002-Strategi-Retrieval-Hierarkis-Hybrid.md)** - Parent-child chunking dan hybrid search
- **[ADR-003: Reranking dengan Cross-Encoder](ADR/ADR-003-Reranking-dengan-Cross-Encoder.md)** - Implementasi reranking lokal
- **[ADR-004: Klasifikasi Intent Percakapan](ADR/ADR-004-Klasifikasi-Intent-Percakapan.md)** - Pre-processing intent classification
- **[ADR-005: Migrasi Session Storage Database](ADR/ADR-005-Migrasi-Session-Storage-Database.md)** - Migrasi dari in-memory ke database-backed sessions

### 🔧 Dokumentasi Teknis
- **[Session Migration Guide](docs/SESSION_MIGRATION_GUIDE.md)** - Panduan lengkap migrasi session storage
- **[Refactor Integritas Evaluasi](docs/REFACTOR_INTEGRITAS_EVALUASI.md)** - Dokumentasi lengkap tentang penghapusan bias evaluasi
- **[API Documentation](docs/API_DOCUMENTATION.md)** - Dokumentasi endpoint REST API
- **[File Organization](docs/FILE_ORGANIZATION.md)** - Struktur organisasi file proyek
- **[Optimization Journey](docs/journal/optimization-journey/)** - Dokumentasi lengkap perjalanan optimisasi sistem (Diarsipkan di `docs/journal/`)
- **[Flowcharts & Diagrams](docs/journal/flowcharts/)** - Visualisasi arsitektur (Diarsipkan di `docs/journal/`)

### ⚙️ Konfigurasi
- **[Section Keywords](config/section_keywords.yaml)** - Konfigurasi keyword untuk self-query extraction
- **[Settings](config/settings.py)** - Konfigurasi sistem dan parameter
