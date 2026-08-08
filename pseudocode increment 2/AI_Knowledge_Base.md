# Dokumentasi Proyek: AI Chatbot Asisten Akademik KKP dan PI

Dokumen ini adalah *knowledge base* komprehensif dari sistem AI Chatbot Asisten Akademik STMIK Widya Cipta Dharma. Dokumen ini disusun berdasarkan **Alur Data (Data Flow)** untuk memudahkan pemahaman agen AI tentang bagaimana data masuk, diproses, hingga menghasilkan *output*.

---

## 1. Ringkasan Project
Proyek ini adalah **AI Chatbot Asisten Akademik** yang dirancang untuk menjawab pertanyaan mahasiswa seputar pedoman Kuliah Kerja Praktik (KKP), Penulisan Ilmiah (PI), Skripsi, dan Non-Skripsi di STMIK Widya Cipta Dharma. Chatbot menggunakan sistem **Retrieval-Augmented Generation (RAG)** cerdas dengan hybrid search (Vector + Keyword) untuk memastikan jawaban akurat berdasarkan dokumen resmi kampus, tanpa halusinasi, dan menyimpan histori sesi obrolan.

**Tech Stack**:
- **Bahasa**: Python 3
- **Framework & Library Utama**: FastAPI (REST API), `python-telegram-bot` (Telegram Interface), Langchain (RAG Orchestration), Ragas (Evaluasi metrik).
- **Database & Storage**: Supabase (PostgreSQL dengan pgvector), RPC Functions.
- **LLM & Embedding**: OpenAI API (`gpt-4o-mini` untuk teks, `text-embedding-3-large`/2000d untuk vektor), `ms-marco-MiniLM-L-6-v2` untuk *Reranking*.

---

## 2. Database
Sistem menggunakan **PostgreSQL (via Supabase)** dengan ekstensi `pgvector` untuk pencarian kemiripan vektor.

### Skema Tabel Utama

**1. `parent_documents`** (Menyimpan teks konteks besar untuk LLM)
> **Catatan**: Dalam kode Python, tabel ini direferensikan menggunakan variabel konfigurasi `settings.table_parent_chunks`.
- `parent_id` (text, PK): ID unik induk.
- `title` (text): Judul dokumen/bab.
- `content` (text): Teks isi utuh.
- `section` (text): Kategori bagian (Misal: "BAB II").
- `domain` (text): Domain data ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI').
- `child_ids` (text[]): Daftar ID potongan anak yang merujuk ke sini.

*Contoh Data*:
```json
{"parent_id": "pi-bab2-001", "title": "Ketentuan Pembimbing", "content": "Dosen pembimbing PI wajib memiliki...", "section": "BAB II", "domain": "PI", "child_ids": ["pi-bab2-001-c1", "pi-bab2-001-c2"]}
```

**2. `child_documents`** (Menyimpan potongan kecil teks + Vektor untuk pencarian Hybrid)
> **Catatan**: Dalam kode Python, tabel ini direferensikan menggunakan variabel konfigurasi `settings.table_child_chunks`.
- `id` (text, PK): ID unik potongan anak.
- `parent_id` (text, FK ke `parent_documents`): Induk dari potongan ini.
- `title`, `content`, `section` (text): Data tekstual.
- `pages` (int[]): Nomor halaman asli di dokumen cetak.
- `source` (text): Nama dokumen sumber.
- `domain` (text): Domain data ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI').
- `metadata` (jsonb): Data pelengkap.
- `embedding` (vector(2000)): Representasi vektor numerik teks.

*Contoh Data*:
```json
{"id": "pi-bab2-001-c1", "parent_id": "pi-bab2-001", "title": "Ketentuan Pembimbing", "content": "Dosen pembimbing PI wajib minimal S2...", "section": "BAB II", "domain": "PI", "pages": [14], "source": "Panduan PI", "metadata": {"parent_id": "pi-bab2-001"}, "embedding": [0.012, -0.045, ...]}
```

**3. `mahasiswa_accounts`** (Akun Mahasiswa untuk login Website)
- `mahasiswa_id` (uuid, PK): ID unik mahasiswa.
- `google_sub` (text, UNIQUE): ID autentikasi Google.
- `email`, `nama`, `avatar_url` (text): Profil mahasiswa.
- `created_at`, `last_login` (timestamptz): Waktu pembuatan dan login.

**4. `admin_users`** (Akun Admin untuk Dashboard CMS)
- `admin_id` (uuid, PK): ID unik admin.
- `username` (text, UNIQUE): Username login.
- `password_hash`, `full_name` (text): Profil kredensial.
- `created_at`, `last_login` (timestamptz): Waktu pembuatan dan login.

**5. `conversation_sessions`** (Menyimpan riwayat obrolan user)
- `session_id` (text, PK): ID sesi / ID User Telegram.
- `mahasiswa_id` (uuid, FK ke `mahasiswa_accounts`): Nullable jika akses via Telegram anonim.
- `channel` (text): Asal platform percakapan ('telegram' atau 'website').
- `turns` (jsonb): Riwayat percakapan.
- `last_access` (timestamptz): Penanda waktu untuk pembersihan sesi yang mati (idle cleanup).

*Contoh Data*:
```json
{"session_id": "tg-123456789", "mahasiswa_id": null, "channel": "telegram", "turns": [{"role": "user", "content": "Halo"}, {"role": "assistant", "content": "Halo!"}], "last_access": "2026-07-27T10:00:00Z"}
```

**6. `chunk_edit_logs`** (Log Audit Perubahan Data dan Antrean Re-Embedding)
- `log_id` (uuid, PK): ID log unik.
- `child_id`, `parent_id` (text): ID dokumen yang diubah.
- `admin_id` (uuid, FK ke `admin_users`): Admin yang melakukan perubahan.
- `old_content`, `new_content` (text): Konten sebelum dan sesudah diedit.
- `status` (text): Status proses ('pending', 'processing', 'success', 'failed').
- `error_message` (text): Pesan error jika re-embedding gagal.
- `edited_at`, `reembedded_at` (timestamptz): Penanda waktu.

---

## 3. Struktur Folder

```text
backend/
├── docker-compose.yml          : File orkestrasi container Docker.
├── Dockerfile                  : Instruksi build image container.
├── main.py                     : Entry point REST API & Webhook Telegram.
├── application.py              : Entry point Polling Bot Telegram lokal.
├── config/
│   ├── settings.py             : Pengaturan konfigurasi & Environment Variables (Pydantic).
│   └── section_keywords.yaml   : Data pemetaan kata kunci ke filter bab/section dokumen.
├── scripts/
│   ├── supabase.sql            : Skema awal tabel dan fungsi RPC `hybrid_search`.
│   ├── supabase_migration_quota_rpc.sql : Fungsi RPC untuk mengecek kuota rate-limit chatbot.
│   ├── supabase_session_migration.sql : Skema tabel memori sesi dan fungsi RPC pembersih (cleanup).
│   ├── supabase_migration_multidomain.sql : Skema tabel untuk multi-domain, user, dan log edit.
│   └── supabase_update_search.sql : Pembaruan fungsi RPC pencarian untuk mendukung filter source.
└── src/
    ├── api/
    │   ├── ai.py               : Endpoint `/chat` untuk melayani REST API HTTP.
    │   ├── auth.py             : Endpoint otentikasi Google (`/auth/google/verify`, dll).
    │   ├── sessions.py         : Endpoint manajemen histori percakapan (CRUD sesi obrolan).
    │   └── health.py           : Endpoint `/health` status server.
    ├── auth/
    │   ├── google_oauth.py     : Logika validasi token Google (id_token).
    │   └── jwt_utils.py        : Utility pembuatan dan verifikasi internal JWT aplikasi (dengan pyjwt).
    ├── bot/
    │   ├── application.py      : Inisialisasi Bot Telegram (Command handlers).
    │   ├── messages.py         : Teks statis/template balasan bot.
    │   └── handlers/
    │       └── chat_handler.py : Pemroses logika utama ketika ada pesan teks dari Telegram.
    ├── evaluation/
    │   ├── ragas_eval.py       : Evaluasi chatbot menggunakan metrik Ragas dengan Ground Truth.
    │   └── ragas_eval_no_gt.py : Evaluasi chatbot tingkat lanjut (diagnostik kesalahan).
    ├── generation/
    │   ├── chain.py            : Menjalankan Prompt LLM (Langchain RAG) untuk menjawab soal.
    │   ├── memory.py           : Struktur data untuk menampung percakapan.
    │   └── intent_classifier/
    │       ├── classifier.py   : Mengklasifikasi niat pengguna (Retrieval/Conversational/Clarification).
    │       ├── constants.py    : Kata-kata pemicu perpindahan topik.
    │       ├── detectors.py    : Logika *rule-based* untuk mendeteksi konteks pesan.
    │       ├── models.py       : Struktur data hasil klasifikasi.
    │       └── reformulator.py : Memperjelas pesan user yang mengandung referensi ("itu", "tadi").
    ├── ingestion/
    │   ├── embedder.py         : Mengeksekusi API Embedding dan menyimpannya ke Supabase.
    │   └── loader.py           : Membaca file JSON dokumen dan memvalidasi integritas strukturnya.
    ├── middleware/
    │   ├── monitoring.py       : Menghitung waktu respons API.
    │   └── security.py         : Membersihkan teks input, Rate Limiting, & validasi Webhook Telegram.
    ├── retrieval/
    │   ├── hybrid_search.py    : Menjalankan kueri BM25 + Vector ke Database.
    │   ├── parent_child.py     : Menarik data utuh (parent) berdasarkan hasil pencarian (child).
    │   ├── pipeline.py         : Orkestrator seluruh proses pencarian (dari query hingga rerank).
    │   ├── query_expansion.py  : Memperpanjang singkatan di query (misal PI -> Penulisan Ilmiah).
    │   ├── reranker.py         : Mengurutkan hasil pencarian silang menggunakan Cross-Encoder AI.
    │   ├── self_query.py       : Mengekstrak perintah filter (Bab/Sumber) dari pertanyaan.
    │   └── source_utils.py     : Menentukan tipe dokumen (KKP / PI) secara paksa jika ambigu.
    └── services/
        ├── ai_services.py      : Penghubung utama antara Controller (Bot/API) dengan Niat, Pencarian, & LLM.
        └── session_store.py    : Melakukan operasi *Read/Write* memori obrolan ke Supabase.

frontend/
├── package.json                : Dependensi project Next.js.
└── src/
    ├── app/
    │   ├── globals.css         : Styling global dan variabel desain (termasuk styling `doc-panel`).
    │   ├── layout.tsx          : Layout utama aplikasi web.
    │   └── (site)/
    │       ├── layout.tsx      : Layout untuk halaman yang butuh otentikasi. Memuat Sidebar dan **DocPanel (Penampil Dokumen)**.
    │       ├── chat/page.tsx   : Halaman chat utama dengan fitur klik-sitasi ke dokumen sumber.
    │       └── riwayat/page.tsx: Halaman histori percakapan berdasar tanggal.
    ├── lib/
    │   ├── api.ts              : Utilitas koneksi ke backend FastAPI.
    │   ├── auth.ts             : Utilitas JWT dan session otentikasi.
    │   ├── documentSources.ts  : Pemetaan dokumen PDF dari Supabase Storage (`panduan-pi.pdf`, dll).
    │   └── store.ts            : Global state management menggunakan Zustand (Zustand store untuk chat, histori, dan state `activeDoc`).
    └── components/
        └── [Berbagai komponen UI modular]
```

> **Catatan Tambahan**: Sebelumnya terdapat file `demo_review.py` di direktori proyek yang berfungsi mengevaluasi struktur format Microsoft Word (menggunakan `python-docx`). File tersebut merupakan skrip CLI *utility* lokal dan tidak menjadi bagian dari alur RAG chatbot, sehingga *pseudocode*-nya tidak dimasukkan ke dalam dokumen ini.

---

## 4. Hubungan Antar File
Berikut adalah diagram dependensi komponen inti:

```mermaid
graph TD
    User([User Telegram / API]) --> |Kirim Pesan| ChatHandler[src/bot/handlers/chat_handler.py]
    User --> |HTTP POST| API[src/api/ai.py]
    
    ChatHandler --> |chat(query, session_id)| AIServices[src/services/ai_services.py]
    API --> |chat(query, session_id)| AIServices
    
    AIServices --> |Muat Riwayat| SessionStore[src/services/session_store.py]
    AIServices --> |Cek Niat| IntentClass[src/generation/intent_classifier/classifier.py]
    
    IntentClass --> |Needs Retrieval| Pipeline[src/retrieval/pipeline.py]
    IntentClass --> |Conversational| Chain[src/generation/chain.py]
    
    Pipeline --> |1. Ekstrak Filter| SelfQuery[src/retrieval/self_query.py]
    Pipeline --> |2. Cari Anak| HybridSearch[src/retrieval/hybrid_search.py]
    Pipeline --> |3. Tarik Induk| ParentChild[src/retrieval/parent_child.py]
    Pipeline --> |4. Rerank| Reranker[src/retrieval/reranker.py]
    
    Pipeline --> |Konteks Dokumen| Chain
    
    Chain --> |Prompt + Konteks| LLM([OpenAI GPT-4o-mini])
    Chain --> |Jawaban AI| AIServices
    
    AIServices --> |Simpan Riwayat| SessionStore
    AIServices --> |Kembalikan Teks| User
```

---

## 5. Alur Data & Pseudocode (ALUR DATA UTAMA)

### Alur 1: Data Ingestion (Penyiapan Database)

**Bentuk Data Awal:**
```json
// File JSON lokal (Parent Chunks dan Child Chunks)
{
  "parent_id": "pi-bab2-001",
  "content": "Dosen pembimbing PI wajib..."
}
```

**File Pemroses (Pseudocode):**

#### File: `src/ingestion/loader.py`

```markdown
ALGORITMA PEMUATAN DATA (loader.py)

1. IMPOR PUSTAKA
   - JSON, Path (untuk urusan file system), loguru.

2. FUNGSI load_child_documents(path)
   - Cek apakah file JSON di `path` ada. Jika tidak, Error (File Not Found).
   - Buka file dan Parse (Bongkar) format JSON-nya.
   - Pastikan hasilnya berupa Daftar (List/Array).
   - LOOP setiap chunk anak:
     - Cek apakah chunk ini punya struktur kolom yang wajib: `id`, `title`, `content`, `section`.
     - Jika kurang satu saja, lemparkan Error gagal struktur.
   - Cek apakah ada nilai ID anak yang sama (Duplikat). Jika ada, lemparkan Error duplikat.
   - KEMBALIKAN seluruh data chunk anak.

3. FUNGSI load_parent_documents(path)
   - Cek keberadaan file induk di `path`.
   - Parse JSON. Pastikan bentuknya Daftar.
   - LOOP setiap chunk induk:
     - Cek struktur kolom wajib: `parent_id`, `title`, `content`, `section`, `child_ids`.
     - Jika kurang, lemparkan Error.
   - Cek adakah ID induk ganda (Duplikat). Jika ada, Error.
   - KEMBALIKAN seluruh data chunk induk.

4. FUNGSI validate_parent_child_links(parents, children)
   - Menguji apakah relasi anak-induk sudah benar sebelum dimuat ke database.
   - Kumpulkan semua `id` anak ke dalam Himpunan Set (cepat dicari).
   - LOOP semua `parents`:
     - LOOP semua `child_ids` yang diklaim dimiliki parent:
       - JIKA ID tersebut TIDAK ADA di himpunan anak tadi: Lemparkan Error ("Parent mencari anak yang tidak ada").
   - Kumpulkan juga dari sisi sebaliknya: adakah Anak yang statusnya Yatim (Orphan/Tidak punya Parent ID).
     - Jika ada, beri Log Peringatan (Warning), karena anak ini tidak akan bisa merujuk balik ke dokumen penuh.
   - KEMBALIKAN True (artinya struktur valid).
```

#### File: `src/ingestion/embedder.py`

```markdown
ALGORITMA PROSES INGESTION & EMBEDDING (embedder.py)

1. IMPOR PUSTAKA
   - OpenAI, Supabase, tqdm (untuk progress bar), dan loguru.
   - Konfigurasi aplikasi (`get_settings`).

2. KONEKSI KE LAYANAN
   - `_get_supabase_client()`: Buat koneksi ke database Supabase (menggunakan URL dan kunci dari settings).
   - `_get_openai_client()`: Buat koneksi ke OpenAI API.

3. FUNGSI get_openai_embeddings(texts, model, batch_size)
   - Tujuannya adalah merubah daftar teks menjadi daftar array angka (vektor 2000 dimensi).
   - Lakukan secara bertahap (batch) agar API tidak menolak karena kelebihan beban.
   - LOOP melalui `texts` dengan langkah `batch_size`:
     - Panggil API `client.embeddings.create` untuk sekumpulan teks (batch) tersebut (menetapkan parameter `dimensions=2000` secara eksplisit).
     - Ekstrak vektor embedding-nya dan kumpulkan.
     - Tunggu (sleep) 0.5 detik antar *batch* untuk menghindari Rate Limit.
   - KEMBALIKAN daftar vektor keseluruhan.

4. FUNGSI _build_metadata_json(child)
   - Ambil data spesifik dari *chunk* (seperti parent_id, judul, bab, halaman).
   - KEMBALIKAN sebagai format dictionary/JSON untuk kolom *metadata* di database.

5. FUNGSI upsert_parent_documents(parents)
   - Buka koneksi ke tabel `parent_documents`.
   - Ambil daftar semua `parent_id` yang sudah ada di database.
   - Saring (Filter) `parents`: Hanya simpan dokumen yang belum ada di database.
   - JIKA semua dokumen sudah ada: Hentikan dan kembalikan 0.
   - JIKA ada yang baru: 
     - Susun datanya (ID, judul, isi, bagian, ID anak-anaknya).
     - Ekstrak nilai domain ("PI", "KKP", "SKRIPSI", "NON_SKRIPSI") berdasarkan pola teks `parent_id`.
     - Sisipkan (Insert) ke database sekaligus (Bulk insert).
   - KEMBALIKAN jumlah dokumen induk yang berhasil masuk.

6. FUNGSI upsert_child_documents_with_embeddings(children, embeddings, mapping_anak_ke_induk)
   - Buka koneksi ke tabel `child_documents`.
   - Pastikan jumlah anak teks sama dengan jumlah vektor (embeddings).
   - Cari tahu (Fetch) ID mana saja yang sudah ada di database, lewati jika sudah ada.
   - LOOP sisa anak-anak baru secara berkelompok (batch 20):
     - Untuk setiap *chunk* anak:
       - Cari siapa ID induknya (dari map).
       - Ekstrak nilai domain dari ID induk.
       - Buat metadata JSON.
       - Gabungkan teks, vektor, domain, dan metadatanya menjadi 1 baris (row).
     - Sisipkan baris-baris tersebut ke database Supabase.
   - KEMBALIKAN jumlah dokumen anak yang berhasil masuk.

7. FUNGSI build_child_to_parent_map(parents)
   - Berfungsi membuat kamus rujukan cepat: "Anak X itu miliknya Induk Y".
   - LOOP untuk tiap Induk: 
     - LOOP untuk tiap Anak-ID di dalam Induk:
       - Simpan di dictionary: `map[Anak_ID] = Induk_ID`
   - KEMBALIKAN map.

8. FUNGSI UTAMA run_ingestion(file_anak, file_induk)
   - (STEP 1) Panggil `loader.py` untuk memuat data JSON anak dan induk dari Harddisk.
   - Panggil validasi (apakah semua anak punya induk yang valid?).
   - Buat rujukan (mapping) dari fungsi ke-7.
   - (STEP 2) Ambil semua teks dari file Anak, proses menjadi Vektor lewat OpenAI (`get_openai_embeddings`).
   - (STEP 3) Masukkan data Induk ke database Supabase (`upsert_parent_documents`).
   - (STEP 4) Masukkan data Anak beserta vektornya ke database (`upsert_child_documents_with_embeddings`).
   - KEMBALIKAN laporan statistik berupa jumlah data yang diproses.
```

#### File: `scripts/supabase.sql`

```markdown
ALGORITMA SKEMA DATABASE SUPABASE UNTUK RAG (supabase.sql)

1. AKTIVASI EKTENSI DATABASE
   - Aktifkan ekstensi `vector` (pgvector) untuk menyimpan dan mencari embedding dokumen.
   - Aktifkan ekstensi `pg_trgm` (trigram) untuk mendukung pencarian teks berbasis fuzzy (FTS).

2. PEMBUATAN TABEL PARENT DOCUMENTS
   - Hapus tabel jika sudah ada.
   - Buat tabel `parent_documents` dengan kolom:
     - parent_id (TEXT, Primary Key)
     - title (TEXT)
     - content (TEXT) - Konten utuh dokumen
     - section (TEXT)
     - child_ids (Array of TEXT) - Daftar ID potongan dokumen anak
     - created_at (Timestamp)

3. PEMBUATAN TABEL CHILD DOCUMENTS
   - Hapus tabel jika sudah ada.
   - Buat tabel `child_documents` dengan kolom:
     - id (TEXT, Primary Key)
     - parent_id (TEXT, Foreign Key ke parent_documents)
     - title (TEXT)
     - content (TEXT) - Potongan teks dokumen
     - section (TEXT)
     - pages (Array of TEXT)
     - source (TEXT)
     - metadata (JSONB) - Data ekstra untuk filter dari Langchain
     - embedding (VECTOR ukuran 2000) - Menyimpan representasi vektor teks
     - created_at (Timestamp)

4. PEMBUATAN INDEX UNTUK PERFORMA PENCARIAN
   - Buat index `ivfflat` menggunakan `vector_cosine_ops` untuk kolom embedding (pencarian kemiripan vektor).
   - Buat index `GIN` untuk fitur Full-Text Search (FTS) menggunakan `to_tsvector('indonesian')` pada konten.
   - Buat index `GIN` pada kolom metadata (untuk filter metadata JSON).
   - Buat index `B-tree` pada kolom parent_id dan section.

5. FUNGSI match_documents
   - INPUT: query_embedding (vektor), match_count (jumlah hasil, default 10).
   - OUTPUT: Tabel (id, content, metadata, similarity).
   - PROSES: 
     - Lakukan pencarian cosinus kesamaan vektor (1 - jarak cosinus).
     - Ambil baris dari tabel `child_documents`.
     - Urutkan dari kesamaan paling tinggi (jarak cosinus terdekat).
     - Batasi jumlah hasil dengan `match_count`.

6. FUNGSI match_child_documents
   - Sama seperti match_documents, tapi ini ditambahkan:
     - threshold (batas minimal kemiripan).
     - filter bagian / section dokumen tertentu secara case-insensitive (ILIKE).
   - Mengembalikan data yang lebih lengkap termasuk parent_id, source, dll.

7. FUNGSI hybrid_search (Gabungan FTS + Vektor menggunakan RRF)
   - INPUT: Teks (query), Vektor (embedding), jumlah hasil, bobot_fts, bobot_vektor, konstanta RRF, filter section.
   - PROSES:
     - Sub-Query 1 (FTS): Cari dokumen berdasarkan teks `to_tsvector` berbahasa Indonesia, lalu berikan peringkat (ranking).
     - Sub-Query 2 (Vector): Cari dokumen berdasarkan kedekatan vektor, lalu berikan peringkat (ranking).
     - RRF (Reciprocal Rank Fusion): Gabungkan ID dari kedua hasil di atas, dan hitung skor akhirnya dengan rumus bobot * (1 / (Konstanta RRF + Ranking)).
     - Gabungkan kembali hasil akhir (Skor RRF) dengan data dokumen di `child_documents`.
     - Urutkan berdasarkan Skor RRF tertinggi dan kembalikan tabel datanya.

8. KONFIGURASI KEAMANAN (Row Level Security - RLS)
   - Aktifkan RLS di `parent_documents` dan `child_documents`.
   - Buat aturan (policy): Hanya pengguna dengan peran `service_role` (backend aplikasi dengan kunci service role) yang boleh membaca (SELECT) dan menambah data (INSERT) ke tabel ini.
   - Buat tabel tambahan:
     - `user_quotas` (Batas request user harian).
     - `chat_logs` (Penyimpanan log percakapan historis).
   - Aktifkan RLS untuk tabel-tabel tambahan ini.
   - Aturan kebijakannya juga sama: hanya bisa dibaca dan ditulis oleh `service_role`.
```

#### File: `scripts/supabase_migration_quota_rpc.sql`

```markdown
ALGORITMA FUNGSI PENAMBAHAN KUOTA USER (supabase_migration_quota_rpc.sql)

1. DEFINISI FUNGSI
   - Nama: `increment_quota_if_under_limit`
   - Input/Parameter: 
     - p_user_id (Teks): ID unik dari pengguna.
     - p_date (Teks): Tanggal dalam format YYYY-MM-DD.
     - p_daily_limit (Angka/Integer): Batas maksimal pesan yang diizinkan per hari.
   - Output/Kembalian:
     - Boolean (TRUE jika sukses ditambah, FALSE jika gagal karena sudah melebihi limit).
   - Bahasa: plpgsql (prosedural SQL PostgreSQL).

2. ALGORITMA UTAMA (Proses Atomik Upsert)
   - Deklarasikan variabel internal `v_new_count` untuk menyimpan jumlah pesan terbaru.
   - COBA masukkan data pengguna ke tabel `user_quotas` (user_id, date, message_count bernilai 1).
   - JIKA data sudah ada sebelumnya (Terjadi konflik/duplikasi pada user_id dan date yang sama):
     - LAKUKAN UPDATE (Tambahkan message_count dengan 1).
     - SYARAT UPDATE (WHERE): Lakukan update hanya jika `message_count` saat ini masih di bawah batas (`< p_daily_limit`).
   - KEMBALIKAN (RETURNING) nilai `message_count` terbaru ke dalam variabel `v_new_count`.

3. PENGECEKAN HASIL
   - JIKA `v_new_count` bernilai NULL:
     - Artinya, baris tidak di-update karena gagal memenuhi syarat WHERE (kuota sudah penuh atau sama dengan limit).
     - KEMBALIKAN nilai FALSE.
   - SELAIN ITU (Jika berhasil):
     - KEMBALIKAN nilai TRUE.
```

#### File: `scripts/supabase_session_migration.sql`

```markdown
ALGORITMA MIGRASI PENYIMPANAN SESI KE DATABASE (supabase_session_migration.sql)

1. PEMBUATAN TABEL SESI PERCAKAPAN
   - Buat tabel `conversation_sessions` (jika belum ada) dengan struktur:
     - session_id (TEXT, Primary Key): ID unik untuk sesi obrolan.
     - turns (JSONB): Menyimpan riwayat percakapan (array tanya-jawab) (Default: '[]').
     - last_access (Timestamp): Kapan sesi ini terakhir digunakan (untuk penghapusan idle).
     - created_at (Timestamp): Kapan sesi ini dibuat.

2. PEMBUATAN INDEKS
   - Buat indeks pada kolom `last_access` untuk mempercepat pencarian dan penghapusan sesi yang sudah kedaluwarsa (idle cleanup).
   - Buat indeks pada kolom `created_at` untuk keperluan analisis dan pelacakan umur sesi.

3. PENGATURAN KEAMANAN (Row Level Security)
   - Aktifkan fitur RLS (Row Level Security) pada tabel `conversation_sessions`.
   - Hapus aturan akses (policy) yang sudah ada agar tidak terjadi duplikasi.
   - Buat Aturan BACA:
     - Hanya user database dengan peran `service_role` (sistem internal backend) yang diizinkan untuk melihat/membaca (SELECT) data sesi.
   - Buat Aturan TULIS:
     - Hanya user dengan peran `service_role` yang diizinkan untuk menambah atau memodifikasi (INSERT/UPDATE/DELETE) data sesi.

4. FUNGSI PENGHAPUSAN SESI KEDALUWARSA (cleanup_idle_sessions)
   - INPUT: Batas waktu tunggu/TTL dalam detik (p_ttl_seconds, default 3600 detik/1 jam).
   - OUTPUT: Jumlah sesi yang berhasil dihapus (Integer).
   - ALGORITMA:
     - HAPUS baris dari tabel `conversation_sessions` DI MANA `last_access` lebih lama dari (WAKTU_SEKARANG dikurangi interval detik p_ttl_seconds) DAN (`mahasiswa_id IS NULL` ATAU `channel != 'website'`).
     - (PENTING: Jangan hapus sesi Website milik mahasiswa agar riwayat mereka tetap ada secara permanen).
     - Simpan jumlah baris yang berhasil dihapus ke dalam variabel.
     - Tampilkan log peringatan (NOTICE) ke konsol sistem.
     - KEMBALIKAN jumlah baris yang dihapus.

5. FUNGSI STATISTIK SESI (get_session_statistics)
   - OUTPUT: Tabel rekap data (total sesi, sesi aktif 1 jam, sesi aktif 24 jam, rata-rata panjang chat, sesi tertua, sesi terbaru).
   - ALGORITMA:
     - Hitung total baris sesi.
     - Hitung sesi yang aktif dalam 1 jam terakhir (berdasarkan last_access).
     - Hitung sesi yang aktif dalam 24 jam terakhir.
     - Hitung rata-rata jumlah elemen dalam array JSONB `turns` (menggunakan avg() dan jsonb_array_length()).
     - Cari waktu paling awal (MIN) di `created_at`.
     - Cari waktu paling akhir (MAX) di `created_at`.
     - KEMBALIKAN semua nilai tersebut sebagai tabel (Record).

6. PENANDA MIGRASI
   - Coba masukkan data rekam jejak migrasi ke dalam tabel `user_quotas` dengan user_id '_system_migration'.
   - Jika sudah ada, abaikan (DO NOTHING).
   - Kembalikan teks status "Session storage migration completed successfully".
```

**Bentuk Data Setelah Diproses:**
```sql
-- Baris di database PostgreSQL (Supabase)
-- Tabel: parent_documents, child_documents (beserta nilai vektor)
```

---

### Alur 2: Entry Point & Request Masuk

**Bentuk Data Awal:**
```json
// Request JSON API atau Webhook Telegram
{
  "query": "Apa saja syarat mendaftar KKP?",
  "session_id": "tg-9988776655"
}
```

**File Pemroses (Pseudocode):**

#### File: `main.py`

```markdown
ALGORITMA UTAMA SISTEM (main.py)

1. IMPOR PUSTAKA DAN MODUL LOKAL
   - Impor pustaka bawaan (os, sys, threading, itertools, time, pathlib, argparse)
   - Impor pustaka eksternal (loguru, uvicorn)
   - Impor konfigurasi (get_settings)
   - Impor komponen sistem (pipeline retrieval, generation, ingestion, bot, evaluasi)

2. KELAS Spinner
   - Berfungsi untuk menampilkan animasi loading (loading spinner) di CLI.
   - Menggunakan thread terpisah agar tidak memblokir proses utama.
   - Terdapat fungsi untuk memulai (write_next), menghentikan (remove_spinner), dan membersihkan layar.

3. FUNGSI setup_logger(debug: Boolean)
   - Hapus konfigurasi log bawaan loguru.
   - Jika debug = True:
     - Tampilkan log secara detail termasuk jam, level, nama modul, fungsi, dan baris kode.
   - Jika debug = False:
     - Tampilkan log standar (jam, level, dan pesan utama).

4. FUNGSI run_rag_pipeline(question: String, debug: Boolean) -> Dictionary
   - Tahap 1: Lakukan pencarian dokumen terkait dari database menggunakan fungsi `run_retrieval(question)`.
   - Tahap 2: Ekstrak dokumen utama (parent documents) yang telah disaring (reranked).
   - Tahap 3: Simpan metadata jumlah dokumen, judul dokumen, dan skor kecocokan (cross_encoder_score).
   - Tahap 4: Jika tidak ada dokumen yang ditemukan:
     - KEMBALIKAN pesan error "Maaf, saya tidak menemukan informasi..." dan list dokumen kosong.
   - Tahap 5: Jika dokumen ditemukan, gabungkan teks dokumen menjadi satu string konteks (`_format_context`).
   - Tahap 6: Generate jawaban dengan LLM berdasarkan pertanyaan dan dokumen konteks (`generate_answer`).
   - KEMBALIKAN jawaban, dokumen sumber, dan metadata proses.

5. FUNGSI run_ingest(dataset: String)
   - Peta letak file JSON dari chunk PDF untuk masing-masing dataset ("pi", "kkp", "skripsi", "non_skripsi").
   - FUNGSI LOKAL ingest_one(name):
     - Ambil path file child chunk dan parent chunk.
     - Jika file tidak ada, HENTIKAN program (error).
     - Jalankan `run_ingestion` untuk mengkonversi dan menyimpan teks ke database vektor (Supabase).
     - Cetak log berhasil beserta statistik baris data.
   - Jika dataset = "both" atau "all": Jalankan `ingest_one` untuk semua domain di atas.
   - Selain itu: Jalankan `ingest_one` untuk dataset yang dipilih.

6. FUNGSI run_eval(dataset) DAN run_eval_no_gt(dataset)
   - Digunakan untuk menjalankan evaluasi kualitas RAG (menggunakan library RAGAS) pada dataset (ground truth dan tanpa ground truth).
   - Mengirim pertanyaan uji coba ke pipeline dan menghitung metrik evaluasi (Faithfulness, Relevancy, dll).
   - Cetak skor akhir evaluasi.

7. FUNGSI run_interactive(debug: Boolean)
   - Mode CLI untuk berinteraksi (chat) dengan sistem di terminal.
   - MULAI LOOP INTERAKSI:
     - Minta input pertanyaan ("📝 Pertanyaan: ").
     - Jika input = "quit", "exit", atau tombol keyboard interrupt: KELUAR DARI LOOP.
     - Aktifkan animasi Spinner loading ("Sedang mencari jawaban...").
     - Panggil fungsi pemrosesan utama (`chat(question, session_id)`).
     - Matikan animasi Spinner dan cetak jawaban ke layar beserta jumlah sumber (jika ada).
     - JIKA terjadi error, cetak pesan error.
   - AKHIRI LOOP

8. FUNGSI UTAMA main()
   - Inisialisasi parser argumen CLI (`argparse`) (Contoh argumen: `--cli`, `--question`, `--ingest`, `--evaluate`).
   - Setup loguru logger.
   - Baca dan muat pengaturan dari `.env` (`get_settings`).
   - BACA ARGUMEN YANG DIPILIH:
     - JIKA `--ingest`: Panggil `run_ingest`.
     - JIKA `--evaluate`: Panggil `run_eval`.
     - JIKA `--evaluate-no-gt`: Panggil `run_eval_no_gt` (evaluasi RAGAS tanpa Ground Truth).
     - JIKA `--question`: Panggil `run_rag_pipeline` untuk satu pertanyaan dan langsung cetak jawabannya.
     - JIKA `--cli`: Panggil `run_interactive`.
     - JIKA TIDAK ADA ARGUMEN DIBERIKAN:
       - Ambil nomor port dari environment (default: 8000).
       - Jalankan server FastAPI menggunakan `uvicorn` (memanggil modul `application:create_app`).
```

#### File: `application.py`

```markdown
ALGORITMA INISIALISASI SERVER APLIKASI (application.py)

1. IMPOR PUSTAKA
   - Impor FastAPI, middleware CORS, Limiter (rate limit), JSONResponse, HTTPException
   - Impor framework Telegram bot, konfigurasi (settings)
   - Impor routers (`ai`, `health`, `auth`, `sessions`)

2. CONTEXT MANAGER lifespan(app)
   - Lifespan menangani kode yang dijalankan saat server mulai (startup) dan server mati (shutdown).
   - SAAT SERVER MULAI (STARTUP):
     - Ambil pengaturan dari konfigurasi (get_settings).
     - Panggil `preload_models()` secara asinkron/sinkronus untuk memanaskan (warm-up) model AI (Embedding dan Cross-Encoder).
     - JIKA konfigurasi URL Webhook Telegram (TELEGRAM_WEBHOOK_URL) tersedia:
       - Inisialisasi objek bot Telegram (`create_bot()`).
       - Hubungkan webhook Telegram dengan mengatur URL dan Secret Token (keamanan webhook).
       - Simpan objek bot ke dalam global state aplikasi (`app.state.bot_app`).
   - LEPASKAN KENDALI KE FASTAPI (yield) -> server berjalan menerima request.
   - SAAT SERVER MATI (SHUTDOWN):
     - Cek apakah state bot ada.
     - Jika ada, panggil fungsi untuk memberhentikan (stop) dan mematikan (shutdown) bot dengan aman.

3. FUNGSI create_app() -> Objek FastAPI
   - Ambil konfigurasi (get_settings).
   - Inisialisasi objek aplikasi `FastAPI` (tetapkan title, version, deskripsi, matikan dokumentasi di production, hubungkan lifespan).
   - Inisialisasi Rate Limiter (`Limiter`) untuk mencegah spam (batas: 100 request/menit per IP).
   - Simpan rate limiter ke dalam state aplikasi.
   - Panggil pendaftaran middleware (`_register_middleware`).
   - Panggil pendaftaran router endpoint (`_register_routers`).
   - KEMBALIKAN objek aplikasi FastAPI.

4. FUNGSI _register_middleware(app)
   - Tambahkan middleware SlowAPI (penanganan limit request).
   - Tambahkan middleware CORS (Cross-Origin Resource Sharing) untuk mengizinkan aplikasi diakses HANYA dari origin frontend secara eksplisit (seperti Vercel atau localhost).

5. FUNGSI _register_routers(app)
   - Daftarkan router `/api` (untuk endpoint sistem AI dan chat).
   - Daftarkan router `/auth` (untuk endpoint otentikasi login).
   - Daftarkan router `/sessions` (untuk endpoint riwayat chat).
   - Daftarkan router `/health` (untuk mengecek kesehatan server).
   
   - DEFINISI ENDPOINT POST `/api/telegram/webhook`:
     - Fungsi ini dipanggil otomatis oleh Telegram setiap ada chat masuk.
     - Ambil pengaturan rahasia webhook.
     - JIKA secret token aktif:
       - Verifikasi token di header HTTP "X-Telegram-Bot-Api-Secret-Token".
       - Jika tidak sama, LEMPAR ERROR 403 (Unauthorized).
     - Verifikasi jika objek bot belum diinisialisasi, LEMPAR ERROR 503 (Service Unavailable).
     - Ambil payload / data JSON masuk.
     - Terjemahkan JSON tersebut menjadi objek `Update` Telegram.
     - Suruh bot untuk memproses update tersebut (`bot_app.process_update(update)`).
     - KEMBALIKAN respon `{"ok": True}`.

   - DEFINISI ENDPOINT GET `/`:
     - Endpoint root untuk mengecek sistem online.
     - KEMBALIKAN JSON pesan selamat datang, versi, dan alamat URL dokumentasi (/docs).
```

#### File: `src/api/auth.py`

```markdown
ALGORITMA ENDPOINT AUTENTIKASI GOOGLE (auth.py)

1. IMPOR PUSTAKA
   - FastAPI, Pydantic, Supabase client.
   - Konfigurasi aplikasi.
   - Fungsi `verify_google_id_token` dan fungsi JWT util.

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix `/auth` dan tag "Auth".

3. ENDPOINT POST `/google/verify`
   - Terima payload JSON berisi `id_token`.
   - TAHAP 1: Verifikasi token -> Profil Google dengan menanyakan ke SDK Google (`verify_google_id_token`).
   - TAHAP 2: Simpan/Perbarui Database (`mahasiswa_accounts`):
     - Gunakan mekanisme upsert atomik (`ON CONFLICT (google_sub) DO UPDATE`) untuk mencegah *race condition*.
     - Update field `avatar_url`, `nama`, dan `last_login`.
   - TAHAP 3: Terbitkan JWT internal:
     - Masukkan `mahasiswa_id`, `name`, `email`, dan `role`="mahasiswa" ke dalam payload.
     - Enkripsi dengan `create_access_token`.
   - KEMBALIKAN token beserta informasi dasar.

4. ENDPOINT GET `/me`
   - Validasi Authorization Header berisi Bearer token.
   - Ekstrak token, dekripsi dengan `verify_access_token`.
   - Ambil profil spesifik (opsional dari tabel `mahasiswa_accounts` di Supabase).
   - Kembalikan data user.
```

#### File: `src/auth/google_oauth.py`

```markdown
ALGORITMA GOOGLE OAUTH (google_oauth.py)

1. IMPOR PUSTAKA
   - `google.oauth2.id_token`
   - `google.auth.transport.requests`
   - Konfigurasi aplikasi (GOOGLE_CLIENT_ID).

2. FUNGSI verify_google_id_token(token_string) -> Dictionary
   - COBA (Try):
     - Panggil `id_token.verify_oauth2_token(token_string, requests.Request(), GOOGLE_CLIENT_ID)`
     - KEMBALIKAN hasil balasan JSON (berisi `sub` (Google ID), `email`, `name`, `picture`).
   - JIKA GAGAL:
     - Lemparkan error otentikasi (Token tidak valid atau kedaluwarsa).
```

#### File: `src/auth/jwt_utils.py`

```markdown
ALGORITMA JWT UTILS (jwt_utils.py)

1. IMPOR PUSTAKA
   - `jwt` (PyJWT)
   - `datetime`, `timezone`
   - Konfigurasi rahasia dari `settings.JWT_SECRET` dan `settings.JWT_ALGORITHM`.

2. FUNGSI create_access_token(data: dict, expires_delta=None) -> str
   - Salin data asli.
   - Jika `expires_delta` diberikan, gunakan itu. Jika tidak, gunakan `JWT_EXPIRATION_MINUTES` dari konfigurasi (misalnya 4320 menit / 3 hari).
   - Tambahkan key `exp` ke dalam dictionary data yang berisi target waktu kedaluwarsa.
   - Enkripsi (Encode) menggunakan PyJWT dengan Secret Key dan Algoritma (misalnya HS256).
   - Kembalikan token *string*.

3. FUNGSI verify_access_token(token: str) -> dict
   - COBA:
     - Dekripsi (Decode) menggunakan PyJWT.
     - Jika berhasil, kembalikan isinya.
   - JIKA GAGAL (Kadaluwarsa / Signature Tidak Cocok):
     - Kembalikan `None`.
```

#### File: `src/api/health.py`

```markdown
ALGORITMA ENDPOINT HEALTH CHECK & MONITORING (health.py)

1. IMPOR PUSTAKA
   - FastAPI, Pydantic, tipe data (Dict, Any), datetime, time.
   - Konfigurasi settings dan fungsi statistik sesi.

2. PENYIMPANAN WAKTU STARTUP
   - Simpan waktu sistem saat aplikasi pertama kali berjalan ke variabel `_startup_time` (digunakan untuk hitung waktu aktif (uptime)).

3. MODEL DATA RESPON
   - `HealthStatus`: (status, timestamp, version, environment, uptime_seconds).
   - `DetailedHealthStatus`: (mewarisi HealthStatus) ditambah (services, system, sessions).

4. ENDPOINT GET `/health/`
   - Tujuan: Memeriksa apakah server web secara mendasar berjalan.
   - KEMBALIKAN `HealthStatus` (status="healthy", timestamp saat ini, versi app, env app, uptime = waktu saat ini - _startup_time).

5. ENDPOINT GET `/health/detailed`
   - Tujuan: Laporan kesehatan lengkap dengan konektivitas ke dependensi.
   - ALGORITMA:
     - Panggil `_check_openai_health(settings)` secara asinkron.
     - Panggil `_check_supabase_health(settings)` secara asinkron.
     - Ambil statistik sesi chat dari `get_session_stats()`.
     - Siapkan informasi sistem (versi python, max requests, dll).
     - Siapkan status layanan (OpenAI, Supabase, setelan Bot Telegram).
     - Jika ada salah satu layanan yang statusnya "error", set status keseluruhan = "degraded". Jika aman semua, set "healthy".
     - KEMBALIKAN objek `DetailedHealthStatus`.

6. FUNGSI INTERNAL `_check_openai_health(settings)`
   - Coba buat AsyncOpenAI client.
   - Catat waktu mulai.
   - Panggil API `client.models.list()` (Tes koneksi paling ringan).
   - Hitung durasi respon.
   - JIKA BERHASIL: Kembalikan status "healthy" dan durasi respon.
   - JIKA GAGAL (Error): Kembalikan status "error", jenis pesan error, dll.

7. FUNGSI INTERNAL `_check_supabase_health(settings)`
   - Coba buat Supabase client.
   - Catat waktu mulai.
   - Panggil operasi ringan ke database (Pilih (Select) jumlah baris dengan limit 1 dari tabel parent_documents).
   - Hitung durasi respon.
   - JIKA BERHASIL: Kembalikan status "healthy", durasi respon, dan jumlah dokumen.
   - JIKA GAGAL: Kembalikan status "error" dan isi pesannya.

8. ENDPOINT GET `/health/readiness`
   - Tujuan: Diperlukan oleh infrastruktur Cloud (seperti Kubernetes) untuk tahu kapan aplikasi SIAP menerima *traffic*.
   - Cek `_check_openai_health` dan `_check_supabase_health`.
   - JIKA ada yang "error": Lemparkan error HTTP 503 (Service Unavailable) dengan pesan dependensi mana yang mati.
   - KEMBALIKAN status "ready" jika semua layanan berjalan normal.

9. ENDPOINT GET `/health/liveness`
   - Tujuan: Diperlukan Kubernetes untuk tahu apakah container aplikasi *freeze/mati*.
   - KEMBALIKAN status "alive", timestamp, dan nilai uptime. (Tidak mengecek API luar agar lebih ringan).
```

#### File: `src/api/ai.py`

```markdown
ALGORITMA ROUTER API CHATBOT (ai.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, HTTPException, Request, Header)
   - Pydantic (BaseModel, Field) untuk validasi skema request/response.
   - Fungsi `chat_service` dari modul `src.services.ai_services`.
   - Modul auth `verify_access_token`, konfigurasi `settings`, dan Supabase.

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix "/ai" dan tag "AI Chatbot".
   - Buat koneksi Supabase untuk pengecekan kuota.

3. DEFINISI SKEMA REQUEST (ChatRequest)
   - Kolom `query` (Teks wajib): Pertanyaan dari pengguna (minimal 1 karakter).
   - Kolom `session_id` (Teks wajib): ID unik untuk sesi chat pengguna.
   - Kolom `channel` (Teks): Asal platform percakapan (default: "website").

4. DEFINISI SKEMA RESPONSE (ChatResponse)
   - Kolom `answer` (Teks): Jawaban teks dari bot.
   - Kolom `num_docs` (Angka): Jumlah dokumen yang dijadikan referensi.
   - Kolom `session_id` (Teks): ID sesi.
   - Kolom `sources` (Daftar/Array kamus, default kosong): Rincian referensi sumber.
   - Kolom opsional `intent`, `confidence`, `reasoning`.

5. ENDPOINT POST "/chat"
   - Path tujuan: `/ai/chat`.
   - Input Payload: Objek `ChatRequest` dan HTTP Request.
   - Proses Asinkron (async):
     - COBA (Try):
       - TAHAP 1: Cek Channel
         - Jika channel "telegram", tolak akses (403) karena harus lewat webhook.
         - Jika channel "website", pastikan ada header "Authorization: Bearer <token>".
         - Ekstrak token, verifikasi via `verify_access_token`.
         - Cek role (jika bukan "mahasiswa", tolak akses).
         - Ambil `mahasiswa_id` (dari klaim `sub`) dan `username` dari token.
       
       - TAHAP 2: Cek Kuota
         - Gunakan koneksi Supabase untuk memanggil RPC `increment_quota_if_under_limit` menggunakan `mahasiswa_id`.
         - Jika gagal/habis kuota (False), lemparkan error 429 (Terlalu Banyak Permintaan).
       
       - TAHAP 3: Teruskan ke Chat Service
         - Panggil logika utama bot: `chat(query=request.query, session_id=request.session_id, username=username, channel=request.channel, mahasiswa_id=mahasiswa_id)`.
         - KEMBALIKAN respons `ChatResponse` yang memuat jawaban, jumlah dokumen, sumber, dsb.
         
     - JIKA GAGAL (Catch/Except):
       - Jika error berasal dari HTTPException, teruskan (raise).
       - Jika error lainnya, hasilkan respon HTTP Error (status code 500: Internal Server Error).
```

#### File: `src/api/sessions.py`

```markdown
ALGORITMA ROUTER SESSIONS (sessions.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, Depends, HTTPException, Request)
   - Konfigurasi aplikasi dan Supabase client.
   - Modul auth `verify_access_token`.

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix "/sessions" dan tag "Sessions".
   - Buat koneksi Supabase.

3. ENDPOINT GET "/"
   - Path: `/sessions`
   - Tujuan: Mengambil riwayat percakapan pengguna (dikelompokkan berdasarkan sesi).
   - ALGORITMA:
     - TAHAP 1: Otorisasi
       - Ambil header "Authorization: Bearer <token>".
       - Ekstrak token, verifikasi via `verify_access_token`.
       - Ambil `mahasiswa_id` dari klaim `sub` pada payload token.
     - TAHAP 2: Query Database
       - Panggil Supabase: `SELECT session_id, last_access, turns FROM conversation_sessions WHERE mahasiswa_id = ? ORDER BY last_access DESC`.
     - TAHAP 3: Pemrosesan Data
       - Loop melalui data hasil kueri.
       - Ekstrak pertanyaan pertama (cari pesan dengan `role=="user"`) dari array `turns` sebagai "judul" sesi (potong max 40 karakter).
       - KEMBALIKAN daftar sesi berupa array JSON dengan format `[{session_id, title, last_access}]`.

4. ENDPOINT GET "/{session_id}"
   - Path: `/sessions/{session_id}`
   - Tujuan: Memuat seluruh isi pesan dari satu sesi spesifik.
   - ALGORITMA:
     - TAHAP 1: Otorisasi
       - Sama seperti di atas, dapatkan `mahasiswa_id` dari klaim `sub`.
     - TAHAP 2: Query Database
       - Panggil Supabase: `SELECT turns FROM conversation_sessions WHERE session_id = ? AND mahasiswa_id = ?`.
       - Jika tidak ditemukan, kembalikan HTTP 404 (Not Found).
     - TAHAP 3: Pemrosesan Data
       - Format ulang `turns` agar sesuai dengan yang diharapkan oleh frontend (ganti nama field: `content` menjadi `text`, `role: "assistant"` menjadi `role: "bot"`, dan `retrieved_doc_contents` menjadi `sources`).
       - KEMBALIKAN daftar pesan lengkap untuk ditampilkan di UI percakapan.

5. ENDPOINT DELETE "/{session_id}"
   - Path: `/sessions/{session_id}`
   - Tujuan: Menghapus sesi percakapan dari database.
   - ALGORITMA:
     - TAHAP 1: Otorisasi
       - Ambil `mahasiswa_id` dari klaim `sub` pada token.
     - TAHAP 2: Query Database
       - Panggil Supabase: `DELETE FROM conversation_sessions WHERE session_id = ? AND mahasiswa_id = ?`.
       - Cek jumlah baris yang berhasil dihapus (row count).
     - TAHAP 3: Respons
       - JIKA row count == 0: Kembalikan HTTP 404 (Not Found).
       - JIKA BERHASIL: KEMBALIKAN pesan sukses.
```

#### File: `src/bot/application.py`

```markdown
ALGORITMA INISIALISASI TELEGRAM BOT (application.py)

1. IMPOR PUSTAKA
   - Modul `telegram` dan `telegram.ext` (Application, CommandHandler, ContextTypes, dsb).
   - Modul logger dari loguru.
   - Pesan teks `messages`, handler khusus `chat_handler`, dan konfigurasi aplikasi.

2. FUNGSI error_handler(update, context)
   - Dipanggil setiap kali terjadi kesalahan/exception tak terduga saat bot beroperasi.
   - Catat pesan kesalahan lengkap dengan *stack trace* ke logger (`logger.error`).
   - JIKA `update` memiliki objek pesan (bukan event lain):
     - COBA balas pesan ke pengguna menggunakan teks `messages.GENERIC_ERROR` ("Maaf, terjadi kesalahan...").
     - HINGGA BERHASIL atau JIKA ERROR lagi saat membalas, abaikan (pass).

3. FUNGSI cmd_help(update, context)
   - Fungsi pemicu saat pengguna mengetik `/help`.
   - Balas pesan pengguna dengan teks bawaan dari `messages.HELP` dalam format HTML.

4. FUNGSI post_init(application)
   - Fungsi asinkron yang dieksekusi tepat setelah bot selesai diinisialisasi, namun sebelum mulai menerima pesan.
   - Daftarkan menu perintah bawaan bot ke Telegram server (`set_my_commands`):
     - "start": "Mulai bot"
     - "help": "Lihat bantuan"
   - Perintah ini akan muncul di tombol menu hamburger aplikasi Telegram pengguna.

5. FUNGSI create_bot() -> Objek Telegram Application
   - Ambil konfigurasi (get_settings) seperti Token Bot Telegram.
   - Gunakan pola *Builder* dari ApplicationBuilder:
     - Masukkan token bot.
     - Matikan `concurrent_updates` (opsional, atur jika ingin menangani update secara sekuensial atau paralel).
     - Bangun (Build) aplikasinya.
   - Daftarkan penanganan kesalahan (error_handler).
   - Daftarkan penanganan perintah `/start` (memanggil `chat_handler.cmd_start`).
   - Daftarkan penanganan perintah `/help` (memanggil `cmd_help`).
   - Daftarkan penanganan pesan teks bebas dari pengguna dengan memanggil `chat_handler.build_text_chat_handler()`.
   - KEMBALIKAN objek aplikasi bot.
```

#### File: `src/bot/handlers/chat_handler.py`

```markdown
ALGORITMA PENANGANAN CHAT BOT (chat_handler.py)

1. IMPOR PUSTAKA
   - asyncio, html, datetime, functools (lru_cache)
   - telegram.ext (Update, MessageHandler, ContextTypes, filters)
   - Konfigurasi, pesan-pesan teks, modul AI chat, alat pendeteksi sumber.

2. FUNGSI _get_supabase_client()
   - Di-cache agar klien Supabase tidak dibuat ulang terus menerus.
   - KEMBALIKAN klien Supabase yang dikonfigurasi dengan URL dan Service Key dari `settings`.

3. FUNGSI check_and_update_quota(user_id) -> Boolean
   - Cek apakah pengguna sudah melewati batas pesan per hari.
   - Ambil limit harian dari konfigurasi (misal: 13).
   - Dapatkan klien Supabase.
   - Panggil fungsi database jarak jauh (RPC) `increment_quota_if_under_limit` dengan input ID pengguna, tanggal hari ini, dan batas kuota harian.
   - JIKA respons berhasil (kuota masih ada), kembalikan TRUE.
   - JIKA respons gagal (limit habis), kembalikan FALSE.
   - JIKA koneksi ke database error/gagal (exception), anggap saja kuota tersedia (fallback True) agar pengguna tidak terblokir karena masalah infrastruktur.

4. FUNGSI cmd_start(update, context)
   - Eksekusi ketika user mengetik `/start`.
   - Balas pesan dengan `messages.WELCOME` dan format dengan nama depan pengguna.

5. FUNGSI _format_source_line(source) -> Teks
   - Konversi dan format rincian referensi dokumen menjadi teks yang aman (menghindari error HTML Parse di Telegram).
   - Jika dokumen punya Judul dan Bab berbeda, gabungkan.
   - Gunakan fungsi `html.escape` untuk mengamankan tanda-tanda baca unik (<, >, &).
   - KEMBALIKAN teks string "* [Nama Bagian] (Buku Panduan [PI/KKP])\n".

6. FUNGSI handle_text_chat(update, context)
   - Dieksekusi otomatis ketika ada pesan teks biasa (bukan perintah garis miring /).
   - Pastikan teksnya tidak kosong.
   
   - TAHAP 1: Cek Limit Kuota
     - Panggil `check_and_update_quota` dengan `asyncio.to_thread` agar tidak memblokir event loop.
     - JIKA habis (False), balas dengan pesan `DAILY_LIMIT_REACHED` dan HENTIKAN proses.
     
   - TAHAP 2: Animasi Loading
     - Berikan aksi "TYPING..." di header Telegram.
     - Kirim pesan teks sementara (loading message) dari `messages.LOADING`.
     
   - TAHAP 3: AI Proses & Database
     - Ambil username (atau nama depan jika tidak ada).
     - Panggil AI Service (`chat(query=text, session_id=user_id, username=username, channel="telegram", mahasiswa_id=None)`) secara asinkron di thread terpisah.
     - Ambil teks jawaban. Jika jawaban LLM kosong, isi dengan `messages.EMPTY_ANSWER_FALLBACK`.
     - Gunakan `html.escape` pada teks jawaban agar tidak bikin error saat dikirim via Telegram (karena parse_mode=HTML).
     - JIKA bot memberikan list dokumen sumber (sources):
       - Tambahkan teks "📚 Sumber:\n"
       - Ulangi untuk setiap dokumen sumber dan panggil `_format_source_line`, gabungkan ke dalam balasan.
       
   - TAHAP 4: Kirim Balasan Akhir
     - Ubah (edit_text) pesan loading tadi dengan teks jawaban final AI.
     - Catat jumlah dokumen referensi yang dipakai di log (jika lebih dari 0).
     
   - PENANGANAN KESALAHAN UMUM (Except):
     - JIKA di proses atas terjadi exception apa pun:
       - Tulis log error.
       - Coba ubah pesan loading dengan pesan ERROR UMUM.
       - Jika tidak ada pesan loading, langsung reply dengan pesan ERROR UMUM.

7. FUNGSI build_text_chat_handler()
   - KEMBALIKAN objek filter bawaan Telegram yang akan memanggil fungsi `handle_text_chat` setiap kali mendeteksi pesan masuk berupa TEKS dan BUKAN PERINTAH (`~filters.COMMAND`).
```

#### File: `src/bot/messages.py`

```markdown
ALGORITMA TEKS PESAN BOT TELEGRAM (messages.py)

1. TUJUAN
   - Menyimpan seluruh templat string / pesan balasan (reply) yang akan digunakan oleh Telegram bot.
   - Semua format teks dibuat mendukung tag HTML (contoh: <b> untuk bold).

2. KONSTANTA PESAN:
   - WELCOME
     - Berisi kalimat sapaan awal saat bot dimulai.
     - Menyapa dengan nama depan pengguna ("Halo, {first_name}!").
     - Memberi tahu fungsi bot untuk tanya jawab seputar KKP/PI.

   - HELP
     - Berisi panduan bantuan.
     - Menjelaskan topik yang didukung dan contoh pertanyaan.
     - Menjelaskan daftar perintah (/start, /help).

   - DAILY_LIMIT_REACHED
     - Pesan peringatan kuota harian habis.
     - Memiliki *placeholder* "{limit}" yang akan diisi oleh angka dari pengaturan.

   - GENERIC_ERROR
     - Teks "Maaf, terjadi kesalahan. Silakan coba lagi." (untuk pesan jika sistem error).

   - LOADING
     - Teks "⏳ Sedang mencari jawaban..." (pesan sementara yang muncul sebelum LLM membalas).

   - EMPTY_ANSWER_FALLBACK
     - Teks balasan cadangan jika bot tidak mengembalikan jawaban teks sama sekali.
```

**Bentuk Data Setelah Diproses:**
```text
(Meneruskan String 'query' dan 'session_id' ke dalam sistem)
```

---

### Alur 3: Manajemen Memori & Sesi

**Bentuk Data Awal:**
```text
// String query: "Apa saja syarat mendaftar KKP?"
// session_id: "tg-9988776655"
```

**File Pemroses (Pseudocode):**

#### File: `src/services/session_store.py`

```markdown
ALGORITMA PENYIMPANAN SESI DATABASE (session_store.py)

1. IMPOR PUSTAKA & INISIALISASI
   - `time`, Threading Lock, lru_cache, loguru, Supabase client, datetime.
   - Konfigurasi aplikasi.

2. KELAS DatabaseSessionStore
   - Tujuan: Menyimpan data percakapan user (memori) secara permanen di database Supabase, namun tetap menggunakan RAM lokal (Cache LRU) untuk sesi yang sedang aktif agar aksesnya super cepat.
   
   - `__init__(cache_size)`:
     - Buka koneksi Supabase.
     - Siapkan Cache lokal (`_cache`) dan waktu akses (`_cache_access`).
     - Jalankan `_test_connection()` (cek apakah tabel ada).
   
   - `load_memory(session_id, mahasiswa_id=None)`:
     - TAHAP 1: Cek Cache Lokal.
       - Jika data sesi ini ada di RAM, perbarui waktu aksesnya, lalu langsung kembalikan datanya (sangat cepat).
     - TAHAP 2: Jika tidak ada di RAM, Cek Database.
       - Lakukan query ke Supabase (tabel `conversation_sessions`).
       - JIKA ADA: 
         - **Keamanan (IDOR):** Jika `mahasiswa_id` diberikan dan tidak sama dengan pemilik di database, lemparkan error 403 (Akses Ditolak). Exception ini akan diteruskan langsung ke framework (FastAPI).
         - Bangun kembali objek `ConversationMemory` dari data JSON tersebut.
       - JIKA TIDAK ADA / ERROR (Selain 403): Buat `ConversationMemory` baru yang kosong.
     - TAHAP 3: Simpan ke Cache Lokal.
       - Masukkan data tadi ke Cache lokal lewat `_add_to_cache()`.
       - Perbarui kolom waktu akses terakhir (last_access) di Database secara diam-diam (*fire and forget*) menggunakan representasi waktu UTC *timezone-aware* (`datetime.now(timezone.utc).isoformat()`).
       - Kembalikan memori.

   - `save_memory(session_id, memory, channel=None, mahasiswa_id=None)`:
     - Ubah `memory` jadi bentuk JSON (dict).
     - Lakukan *Upsert* (Insert atau Update) ke database Supabase (sertakan `mahasiswa_id` dan `channel`).
     - Perbarui Cache lokal.
     - Jika gagal (koneksi terputus dll), lempar error (tapi aplikasinya dirancang untuk mengabaikan error ini agar chat tetap jalan).

   - `delete_session(session_id)`:
     - Hapus baris sesi di database.
     - Hapus sesi tersebut dari Cache lokal.

   - `cleanup_idle_sessions(ttl_seconds)`:
     - Panggil prosedur Supabase (RPC `cleanup_idle_sessions`) untuk otomatis menghapus sesi-sesi yang `last_access`-nya sudah terlalu lama.
     - Hapus juga sesi yang sudah tua (kedaluwarsa) dari Cache lokal.

   - `_add_to_cache(session_id, memory, access_time)`:
     - Masukkan sesi ke RAM.
     - JIKA Cache Penuh (kapasitas terlampaui):
       - Cari sesi yang Paling Lama Tidak Diakses (Least Recently Used / LRU).
       - Usir (Evict) sesi tersebut dari RAM (hanya dari RAM, di database tetap aman).

3. FUNGSI get_session_store()
   - Pola *Singleton*: Pastikan hanya ada satu objek `DatabaseSessionStore` di seluruh aplikasi yang dibagi-pakai oleh semua request chat.
   - Set kapasitas cache lokal ke 10% dari Maksimal Sesi Aktif.
```

#### File: `src/generation/memory.py`

```markdown
ALGORITMA PENYIMPANAN MEMORI PERCAKAPAN (memory.py)

1. DEKLARASI ENUM & STRUKTUR DATA
   - `IntentType`: Jenis percakapan (NEEDS_RETRIEVAL, CONVERSATIONAL, CLARIFICATION).
   - `Turn` (Dataclass): Objek yang merepresentasikan satu pesan, berisi:
     - `role`: "user" (pengguna) atau "assistant" (bot).
     - `content`: isi pesan (teks).
     - `intent`: tipe tujuan (opsional).
     - `retrieved_doc_contents`: daftar teks dokumen yang digunakan bot untuk menjawab (jika ada).
     - `sources`: daftar metadata terstruktur (judul, bab, skor) dari dokumen yang ditarik.
     - `timestamp`: waktu pesan dibuat.

2. KELAS ConversationMemory
   - `__init__(max_turns=5)`:
     - Inisialisasi array `_turns` kosong.
     - Set batas maksimal jumlah percakapan yang diingat secara internal (`max_turns`).

   - `add_user_turn(content, intent)`:
     - Tambahkan pesan dari user ke daftar `_turns`.

   - `add_assistant_turn(content, retrieved_doc_contents, sources)`:
     - Tambahkan pesan balasan bot beserta dokumen sumber (teks dan metadatanya) ke daftar `_turns`.
     - **PENTING**: Array `_turns` dibiarkan tumbuh tak terbatas tanpa dipotong, agar semua riwayat tersimpan utuh secara permanen di database.

   - `get_history_for_llm()`:
     - Ambil histori pesan untuk disuapkan ke LLM (format dict).
     - **Batas LLM Context**: Terapkan *sliding window* dengan batas `settings.MAX_HISTORY_TURNS` (default: 3 giliran) agar input ke LLM tidak membengkak berlebihan.

   - `get_last_retrieved_docs()`:
     - Cari dari pesan terakhir bot, apa saja isi teks dokumen yang dipakai untuk menjawab.
     - Kembalikan daftar dokumen.

   - `get_conversation_summary()`:
     - Rangkum percakapan saat ini sebagai string teks, dibatasi 200 karakter per pesan, untuk mempermudah pengecekan log.

   - `get_last_question()` & `get_last_answer()`:
     - Ambil teks pertanyaan terakhir user dan jawaban terakhir bot.

   - `has_prior_context` (Property):
     - Kembalikan True jika ada minimal satu percakapan tuntas (user -> asisten) sebelum pesan saat ini.

   - FUNGSI KONVERSI DB:
     - `to_dict()`: Konversi array `_turns` menjadi bentuk *Dictionary/JSON* agar bisa disimpan di Database (Supabase JSONB).
     - `from_dict(turns_data, max_turns)`: Bangun kembali (Rekonstruksi) objek `ConversationMemory` dari data mentah yang ditarik dari Database.
```

**Bentuk Data Setelah Diproses:**
```python
# Objek ConversationMemory dari memori/database:
[
  Turn(role="user", content="Halo"),
  Turn(role="assistant", content="Halo! Ada yang bisa dibantu?"),
  Turn(role="user", content="Apa saja syarat mendaftar KKP?")
]
```

---

### Alur 4: Klasifikasi Niat (Intent)

**Bentuk Data Awal:**
```text
// Pesan terbaru user beserta riwayat obrolan
```

**File Pemroses (Pseudocode):**

#### File: `src/services/ai_services.py`

```markdown
ALGORITMA LAYANAN KECERDASAN BUATAN (ai_services.py)

1. IMPOR PUSTAKA & INISIALISASI
   - Memori percakapan, Klasifikasi Niat, Rantai (Chain) AI.
   - Session store (database/penyimpanan di memori).
   - Pengaturan konfigurasi.
   - Buat Instance (objek tunggal): Classifier dan RAG Chain.
   - Tentukan penyimpanan: Coba sambungkan ke database (Supabase JSONB). Jika gagal, jatuh (fallback) gunakan kamus RAM biasa (`_legacy_session_store`).

2. MANAJEMEN SESI (Memori Percakapan)
   - `get_or_create_memory(session_id)`:
     - Cari memori sesi ini di Database (jika pakai DB) atau RAM.
     - Jika belum ada, buat objek `ConversationMemory` baru dengan maksimal 5 turn (10 pesan).
     - Kembalikan memori.
   
   - `_save_memory_if_needed(session_id, memory)`:
     - (Hanya jika pakai DB): Simpan ulang memori yang ter-update ke Database.
     - Tangkap error secara diam-diam agar chat tidak gagal hanya karena gagal menyimpan riwayat.
   
   - `clear_session(session_id)`:
     - Hapus data memori user tersebut dari penyimpanan.

   - Pembersihan Sesi Tua (Cleanup):
     - Membuang memori obrolan dari user yang sudah terlalu lama tidak aktif agar RAM / Database tidak penuh.

3. FUNGSI UTAMA chat(query, session_id)
   - Fungsi utama yang dipanggil oleh Bot Telegram atau API eksternal saat user bertanya.
   - JIKA `query` atau `session_id` kosong: Kembalikan pesan error seketika.
   
   - TAHAP 1: Normalisasi
     - Panggil `normalize_query(question)`.
   
   - TAHAP 2: Deteksi Reformulasi (Regex)
     - Cek apakah butuh ditulis ulang dengan `needs_rewrite(normalized_query)`.
     - *Slow Path* (Jika butuh di-rewrite): Panggil `get_or_create_memory` (karena LLM butuh riwayat), lalu panggil `reformulate_query(normalized_query, memory)`.
     - *Fast Path* (Jika mandiri): Pakai kueri hasil normalisasi langsung.
   
   - TAHAP 3: Cek Cache (LRU)
     - Buat kunci cache `v1_{resolved_query}`.
     - JIKA hasil sudah ada di `retrieval_cache`: Gunakan data itu langsung (*Cache Hit*).
     - JIKA BELUM (*Cache Miss*): Panggil `run_retrieval(query, rerank_query)`. Simpan hasilnya ke cache.
   
   - TAHAP 4: Muat Memori (Jika belum dimuat)
     - Jika masuk *Fast Path* tadi, muat memori di sini dan tambahkan giliran pertanyaan user.
   
   - TAHAP 5: LLM Generation
     - Panggil RAG Chain (`_rag_chain.invoke_with_history`) dengan memasukkan histori percakapan dan dokumen hasil cari (bisa kosong jika gagal Rerank/Threshold).
     - Simpan jawaban AI (berserta teks isi dokumen referensi) ke memori.
     - Simpan memori ke Database.
   
   - TAHAP 6: Kembalikan Jawaban
     - Siapkan dictionary hasil yang berisi: Teks Jawaban, Metode Rewrite, Jumlah Dokumen, dan Maksimal 3 Dokumen Sumber Referensi terbaik.
     - JIKA ada error: Tangkap dan kembalikan pesan error *fallback*.

4. FUNGSI preload_models()
   - Dieksekusi secara asinkronus/synchronous saat server baru menyala.
   - Fungsi: Memanaskan (*warm-up*) model AI agar tidak terjadi jeda dingin (*cold-start*) saat request pertama.
   - TAHAP 1: *Preload Cross-Encoder* -> Memaksa model lokal termuat ke RAM.
   - TAHAP 2: *Preload Embedding Model* -> Mengirim string dummy "warmup" ke API OpenAI untuk membangun koneksi HTTP *Keep-Alive* dan memuat *tiktoken* ke RAM.
```

#### File: `src/generation/intent_classifier/classifier.py`

```markdown
ALGORITMA KLASIFIKASI INTENT (classifier.py)

> **⚠️ PERINGATAN ARSITEKTUR ⚠️**
> Modul `IntentClassifier` LLM ini **telah di-*bypass* secara praktis** pada pembaruan arsitektur terbaru aplikasi (menuju arsitektur murni *Retrieval-First / Evidence-Driven*). Berkas ini masih dipertahankan untuk referensi *fallback* dan kompatibilitas, namun *core flow* AI (`ai_services.py`) tidak lagi memanggil modul ini sebagai "satpam" (Gatekeeper) perantara utama.

1. IMPOR PUSTAKA
   - JSON, Typing, Langchain (HumanMessage, SystemMessage, ChatOpenAI).
   - loguru (logger).
   - Konfigurasi, Memori percakapan.
   - Konstanta dan Detektor (SwitchDetector, ClarificationDetector, ConversationalDetector).

2. FUNGSI _build_classifier_prompt(current_message, memory)
   - Ambil riwayat pertanyaan dan jawaban terakhir dari memori (jika ada).
   - Gabungkan histori tersebut dengan pesan user saat ini.
   - Tambahkan instruksi untuk LLM: "Tentukan intent pesan user sekarang. Output hanya JSON."
   - Kembalikan teks prompt.

3. KELAS IntentClassifier
   - `__init__()`:
     - Buat LLM (ChatOpenAI) dengan suhu=0, max_tokens=200.
     - Buat dictionary (kamus) kosong untuk *Cache* hasil klasifikasi agar hemat API.
     - Inisialisasi ketiga detektor (Switch, Clarification, Conversational).
   
   - `classify(message, memory)`:
     - TAHAP 1: Jalan pintas Obrolan Biasa.
       - Cek dengan `ConversationalDetector`. Jika "conversational", kembalikan (IntentType.CONVERSATIONAL, 0.95, alasan).
     - TAHAP 2: Jika ini pesan pertama (tidak ada histori).
       - Langsung kembalikan "NEEDS_RETRIEVAL" (pasti butuh pencarian).
     - TAHAP 3: Deteksi Perpindahan Topik (Switch).
       - Cek dengan `SwitchDetector`.
       - Jika terdeteksi pindah topik/domain/aspek, kembalikan "NEEDS_RETRIEVAL" karena pasti butuh mencari info baru.
     - TAHAP 4: Deteksi Permintaan Penjelasan (Clarification).
       - Cek dengan `ClarificationDetector`.
       - Jika terdeteksi user minta kejelasan dari topik yang SAMA PERSIS, kembalikan "CLARIFICATION".
     - TAHAP 5: Jika semua aturan gagal (Rule-based gagal).
       - Lempar ke LLM untuk diproses dengan memanggil `_classify_with_llm(message, memory)`.

   - `_classify_with_llm(message, memory)`:
     - Buat kunci cache dari 50 karakter pertama pesan + jumlah riwayat percakapan.
     - JIKA kunci ada di cache: kembalikan hasil cache tersebut (hemat pemanggilan LLM).
     - Bangun prompt dari `_build_classifier_prompt`.
     - Panggil API LLM (dengan `CLASSIFIER_SYSTEM_PROMPT` dan prompt yang dibuat).
     - Bersihkan teks respon dari LLM (hilangkan tanda blok kode markdown ` ```json `).
     - *Parse* string menjadi objek JSON.
     - Ambil `intent`, `confidence`, dan `reason` dari JSON tersebut.
     - Simpan hasil ke cache.
     - KEMBALIKAN (intent, confidence, reason).
     - JIKA ERROR (JSON invalid, gagal API, dll): Jatuh ke pilihan aman (Fallback) yaitu "NEEDS_RETRIEVAL".
```

#### File: `src/generation/intent_classifier/constants.py`

```markdown
ALGORITMA KONSTANTA KLASIFIKASI INTENT (constants.py)

1. DEKLARASI DAFTAR KATA KUNCI (SIGNALS)
   - `TOPIC_SWITCH_SIGNALS`:
     - Tanda Eksplisit: "sekarang", "bagaimana dengan", "kalau untuk", "ganti topik", dll.
     - Tanda Domain: 
       - PI: ["pi", "penulisan ilmiah", "penelitian", "skripsi", "thesis"]
       - KKP: ["kkp", "kuliah kerja praktik", "magang", "internship", "praktik"]
   
   - `CLARIFICATION_SIGNALS`:
     - Tanda Minta Kejelasan: "lebih detail", "jelaskan lagi", "elaborasi", "contoh", "maksudnya", "mengapa", dll.
   
   - `CONVERSATIONAL_PATTERNS`:
     - Tanda Obrolan Biasa: "halo", "hai", "selamat pagi", "terima kasih", "oke", "sampai jumpa", dll.
   
   - `QUESTION_KEYWORDS`:
     - Tanda Pertanyaan: "apa", "bagaimana", "berapa", "kapan", "siapa", "kenapa", "mengapa", "dimana".
   
   - `ASPECT_KEYWORDS`:
     - Tanda Aspek (Sub-topik): syarat, format, durasi, prosedur, dosen, tempat, ujian, laporan.
   
   - `IMPLICIT_REFERENCE_SIGNALS`:
     - Tanda Referensi Implisit (menunjuk objek sebelumnya): "itu", "tersebut", "tadi", "hal itu", "dan untuk", dll.

2. PROMPT SISTEM (System Prompts)
   - `CLASSIFIER_SYSTEM_PROMPT`:
     - Prompt instruksi untuk LLM saat menjadi Classifier.
     - Menjelaskan aturan 3 Intent (needs_retrieval, conversational, clarification).
     - Memberikan contoh kapan harus memakai intent yang mana (terutama bedanya topic switch vs clarification).
     - Memaksa keluaran dalam bentuk JSON wajib (`{"intent": "...", "reason": "...", "confidence": 1.0}`).
   
   - `REFORMULATION_PROMPT`:
     - Prompt instruksi untuk LLM saat menjadi Reformulator (Penulis ulang pertanyaan).
     - Mengubah pertanyaan yang tidak jelas (seperti "Bagaimana dengan syaratnya?") menjadi pertanyaan lengkap ("Bagaimana dengan syarat KKP?") dengan melihat riwayat percakapan.
```

#### File: `src/generation/intent_classifier/detectors.py`

```markdown
ALGORITMA DETEKTOR PERCAKAPAN (detectors.py)

1. KELAS SwitchDetector
   - `detect_explicit_switch(message)`:
     - Cari kata dari pesan user yang cocok dengan `TOPIC_SWITCH_SIGNALS["explicit"]` (misal: "sekarang", "bagaimana dengan").
     - Kembalikan kata sinyal tersebut jika ada, jika tidak ada kembalikan None.
   
   - `detect_domain_switch(message, memory)`:
     - Deteksi apakah domain pesan saat ini (misal PI) berbeda dengan domain di pesan sebelumnya (misal KKP).
     - Kembalikan True/False dan alasan.
   
   - `detect_aspect_switch(message, memory)`:
     - Deteksi apakah aspek pesan saat ini (misal "syarat") berbeda dengan aspek sebelumnya (misal "dosen").
     - Kembalikan True/False dan alasan.
   
   - `detect_switch(message, memory)`:
     - Jalankan `detect_explicit_switch`. Jika True -> Pindah Topik (TOPIC).
     - Jalankan `detect_domain_switch`. Jika True -> Pindah Domain (DOMAIN).
     - Jalankan `detect_aspect_switch`. Jika True -> Pindah Aspek (ASPECT).
     - Kembalikan objek `SwitchDetectionResult`.

2. KELAS ClarificationDetector
   - `detect_clarification_signals(message)`:
     - Cari kata dari pesan user yang cocok dengan `CLARIFICATION_SIGNALS` (misal "jelaskan lagi", "contohnya").
   
   - `is_true_clarification(message, memory)`:
     - JIKA pesan punya sinyal klarifikasi, DAN TIDAK TERDETEKSI adanya perpindahan topik (dari `SwitchDetector`).
     - Maka itu adalah klarifikasi asli (True). Kembalikan True.

3. KELAS ConversationalDetector
   - `is_short_message(message)`:
     - Cek apakah panjang pesan kurang dari sama dengan 9 karakter.
   
   - `has_question_keywords(message)`:
     - Cek apakah ada kata tanya (apa, bagaimana, dll) di pesan.
   
   - `matches_conversational_pattern(message)`:
     - Cek apakah cocok dengan daftar pola obrolan (halo, terima kasih, dll).
   
   - `is_conversational(message)`:
     - JIKA (pesan sangat pendek DAN tidak ada kata tanya) ATAU (cocok dengan pola obrolan DAN tidak ada kata tanya).
     - Kembalikan True.
```

#### File: `src/generation/intent_classifier/models.py`

```markdown
ALGORITMA MODEL DATA (models.py)

1. IMPOR PUSTAKA
   - `dataclass`, `Enum`.
   - `IntentType` dari memori.

2. ENUMERASI SwitchType
   - Mendefinisikan tipe perpindahan konteks.
   - `NONE`: Tidak ada perpindahan.
   - `TOPIC`: Pindah topik eksplisit.
   - `DOMAIN`: Pindah domain utama (KKP/PI).
   - `ASPECT`: Pindah sub-aspek (Syarat, Dosen, Laporan, dll).

3. STRUKTUR DATA ClassificationResult
   - `intent` (Tipe `IntentType`): Hasil akhir klasifikasi (Retrieval, Conversational, Clarification).
   - `confidence` (Angka desimal): Tingkat keyakinan (0-1).
   - `reason` (Teks): Alasan kenapa memilih intent tersebut.
   - `switch_type` (Tipe `SwitchType`): Menyimpan jenis perpindahan jika ada.
   - `switch_reason` (Teks): Penjelasan alasan perpindahan.

4. STRUKTUR DATA SwitchDetectionResult
   - `has_switch` (Boolean): Bernilai Benar (True) jika detektor menemukan adanya perpindahan konteks percakapan.
   - `switch_type` (Tipe `SwitchType`): Tipe perpindahan (Topik, Domain, atau Aspek).
   - `reason` (Teks): Bukti penemuan perpindahan (misal: ada kata 'sekarang' atau 'bagaimana dengan').
```

#### File: `src/generation/intent_classifier/reformulator.py`

```markdown
ALGORITMA REFORMULASI PERTANYAAN (reformulator.py)

1. IMPOR PUSTAKA
   - Langchain (HumanMessage, ChatOpenAI).
   - Logger, Pengaturan, Memori.
   - Konstanta (`IMPLICIT_REFERENCE_SIGNALS`, `REFORMULATION_PROMPT`).

2. FUNGSI normalize_query(query)
   - Normalisasi istilah akademik via Regex secara agresif.
   - Singkatan "kp" -> "KKP", "pi" -> "Penulisan Ilmiah".
   - Jika query berupa "apa itu X", ubah paksa menjadi "Apa yang dimaksud dengan X".

3. FUNGSI needs_rewrite(query)
   - Gunakan **Regex Word Boundary** (`\b`) saat mengecek kata tunjuk implisit ("itu", "tersebut", "tadi"). Ini mencegah bug *substring match* naif yang memicu reformulasi pada kata seperti "waktu".
   - Kecualikan pemrosesan ulang jika kalimat sudah jelas mandiri (contoh: "apa itu kkp").
   - KEMBALIKAN True/False.

4. KELAS QueryReformulator
   - `__init__(llm)`:
     - Jika objek LLM tidak diberikan, buat objek LLM ChatOpenAI (suhu=0, max_token=100).
   
   - `_extract_last_topic(memory)`:
     - Baca memori percakapan secara mundur (reversed) untuk menemukan topik terakhir yang dibahas (KKP atau Penulisan Ilmiah).
   
   - `_apply_rule_rewrite(message, last_topic)`:
     - Coba lakukan penulisan ulang instan menggunakan *Rule/Regex* tanpa perlu menembak API LLM.
     - Contoh: "terus formatnya" -> "terus formatnya Penulisan Ilmiah".
   
   - `reformulate_query(message, memory)`:
     - JIKA histori percakapan (memori) kosong, langsung KEMBALIKAN tuple (pesan asli, "None").
     - JIKA `_apply_rule_rewrite` berhasil menangani kalimat, KEMBALIKAN tuple (pesan diperbaiki, "Rule").
     - Jika aturan gagal, barulah jatuh (fallback) ke LLM Reformulator.
       - Susun prompt berdasarkan `REFORMULATION_PROMPT` dan panggil API LLM.
       - KEMBALIKAN tuple (pesan dari LLM, "LLM").
       - Jika LLM error, kembalikan tuple (pesan asli, "None") (fallback).

5. FUNGSI reformulate_query(message, memory, llm)
   - Fungsi Wrapper kompatibilitas lama yang mengembalikan nilai _tuple_ (teks, metode).
```

**Bentuk Data Setelah Diproses:**
```python
# Tipe Intent yang terdeteksi
IntentType.NEEDS_RETRIEVAL
```

---

### Alur 5: Pencarian (Retrieval)

**Bentuk Data Awal:**
```text
// Pertanyaan (yang berpotensi sudah direformulasi)
"Apa saja syarat mendaftar KKP?"
```

**File Pemroses (Pseudocode):**

#### File: `src/retrieval/pipeline.py`

```markdown
ALGORITMA JALUR PENCARIAN UTAMA (pipeline.py)

1. IMPOR PUSTAKA
   - `dataclass`, loguru (logger), pengaturan (settings).
   - *Lazy Import* (Impor di dalam fungsi) untuk: `extract_query_components` (Self-Query), `HybridSearcher`, `ParentChildFetcher`, dan `CrossEncoderReranker` agar tidak terjadi *circular import* (impor saling muter).

2. STRUKTUR DATA RetrievalResult
   - `parent_documents`: Daftar (list) dokumen induk hasil akhir pencarian yang siap disuapkan ke LLM.
   - `is_empty`: Boolean (True jika kosong, False jika ada hasil).
   - Properti `num_docs`: Menghitung jumlah dokumen induk.

3. FUNGSI UTAMA run_retrieval(query, rerank_query)
   - Fungsi ini adalah konduktor (pengatur lalu lintas) semua langkah pencarian.
   - `query`: Pertanyaan untuk pencarian awal.
   - `rerank_query`: Pertanyaan asli user untuk perhitungan ulang skor di akhir (jika tidak ada, samakan dengan `query`).
   
   - TAHAP 1: Ekstrak Filter (Self-Query)
     - Panggil `extract_query_components(query)`.
     - Hasilnya: pertanyaan yang bersih dari kata filter, dan `filters` (contoh: cari di sumber "KKP", Bab II).
   
   - TAHAP 2: Pencarian Awal (Hybrid Search)
     - Buat objek `HybridSearcher()`.
     - Cari dokumen anak yang relevan dengan pertanyaan bersih dan filternya.
     - JIKA hasil kosong: Kembalikan `RetrievalResult` kosong.
   
   - TAHAP 3: Tarik Dokumen Utuh (Parent Fetching)
     - Buat objek `ParentChildFetcher()`.
     - Tarik dokumen induk berdasarkan ID dari dokumen anak yang ketemu.
   
   - TAHAP 4: Pengurutan Ulang (Reranking)
     - **Candidate Limiting**: Batasi jumlah dokumen induk yang akan di-Rerank (hanya Top N berdasar konfigurasi `max_parent_for_rerank`).
     - **Adaptive Reranking**: JIKA jumlah kandidat `<= settings.min_parent_for_rerank`, LEWATI proses Reranking (langsung pakai skor Hybrid) untuk menghemat waktu komputasi.
     - JIKA butuh di-Rerank, coba urutkan ulang dokumen induk memakai AI pintar (Cross Encoder) dan pertanyaan asli (`rerank_query`).
     - JIKA proses rerank gagal/error:
       - Tangkap error, log warning.
       - Urutan jangan diubah, cukup ambil N dokumen teratas (berdasarkan skor Hybrid).
   
   - TAHAP 5: Evaluasi Skor Rerank (Zero-Doc Shortcircuit)
     - JIKA skor *Top 1* < `settings.rerank_min_top_score`:
       - Kosongkan hasil dokumen (icu *Minimum Evidence Triggered*). LLM akan menjawab menggunakan mode obrolan biasa.
     - JIKA lulus skor minimum, terapkan aturan filter jarak: hapus dokumen yang skornya turun terlalu jauh dari *Top 1* (berdasar `settings.rerank_relative_gap`).
     - Potong hasil akhir hanya sejumlah `settings.rerank_top_n`.
   
   - Kembalikan objek `RetrievalResult` dengan daftar dokumen akhir yang sudah diurutkan dan disaring.
```

#### File: `src/retrieval/self_query.py`

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

3. DETEKSI SUMBER PANDUAN (PI / KKP)
   - Daftar kata khusus PI (`_PI_KEYWORDS`): "penulisan ilmiah", "seminar pi", dll.
   - Daftar kata khusus KKP (`_KKP_KEYWORDS`): "kuliah kerja praktik", "tempat kkp", dll.
   - Definisi string judul statis: `_SOURCE_PI` dan `_SOURCE_KKP`.
   - `_detect_source(query_lower)`:
     - Cek apakah teks punya kata PI dan/atau KKP.
     - JIKA HANYA ada PI: Kembalikan variabel statis `_SOURCE_PI`.
     - JIKA HANYA ada KKP: Kembalikan variabel statis `_SOURCE_KKP`.
     - JIKA ADA KEDUANYA atau TIDAK ADA SAMA SEKALI: Kembalikan None (jangan difilter, cari di dua-duanya).

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

#### File: `src/retrieval/query_expansion.py`

```markdown
ALGORITMA PERLUASAN KATA KUNCI (query_expansion.py)

1. IMPOR PUSTAKA
   - Ekspresi reguler (`re`), loguru.

2. KONSTANTA DAFTAR SINGKATAN
   - `UPPERCASE_ACRONYMS`: Kamus singkatan huruf besar ke kepanjangannya. (PI -> Penulisan Ilmiah, KKP -> Kuliah Kerja Praktik, SKS -> Satuan Kredit Semester, dll).
   - `LONG_FORM_TO_ACRONYM`: Kamus kepanjangan ke singkatan (penulisan ilmiah -> PI, dll).

3. FUNGSI _has_uppercase_token(text, token)
   - Mengecek apakah sebuah singkatan huruf kapital (misal "PI") benar-benar muncul sebagai kata utuh di dalam teks, bukan sebagai bagian dari kata lain (seperti "PINTAR").
   - Kembalikan True/False menggunakan Regex Boundary (`\b`).

4. FUNGSI _has_phrase(text_lower, phrase)
   - Mengecek substring biasa dalam teks huruf kecil.

5. FUNGSI expand_query(question)
   - JIKA pertanyaan kosong, kembalikan kosong.
   - Buat daftar `additions` kosong (untuk menampung kata tambahan).
   - Ubah teks pertanyaan jadi huruf kecil semua untuk pengecekan tipe ke-2.
   
   - Aturan 1: Singkatan Besar -> Kepanjangan
     - LOOP semua singkatan di `UPPERCASE_ACRONYMS`:
       - JIKA teks punya singkatan utuh (contoh ada kata "KKP"):
         - LOOP semua kemungkinan kepanjangannya (contoh "Kuliah Kerja Praktik").
         - JIKA kepanjangan itu belum ada di teks asli dan belum ditambahkan: Tambahkan ke `additions`.
   
   - Aturan 2: Kepanjangan -> Singkatan
     - LOOP semua frase di `LONG_FORM_TO_ACRONYM`:
       - JIKA teks punya frase utuh (contoh ada kata "kuliah kerja praktik"):
         - LOOP semua kemungkinan singkatannya (contoh "KKP").
         - JIKA singkatan itu tidak ada secara kapital di teks dan belum ditambahkan: Tambahkan ke `additions`.
   
   - JIKA tidak ada tambahan: Kembalikan teks asli.
   - JIKA ada: Gabungkan teks asli dengan tambahan (diberi spasi). Log aksi ini.
   - Kembalikan teks perluasan (contoh: "Apa itu kkp? Kuliah Kerja Praktik").

6. FUNGSI expand_query_smart(question, enable_expansion)
   - Bungkus (wrapper) untuk on/off fitur ini secara dinamis.
   - Jika `enable_expansion` False, kembalikan pertanyaan aslinya.
   - Jika True, panggil `expand_query(question)`.
```

#### File: `src/retrieval/hybrid_search.py`

```markdown
ALGORITMA PENCARIAN HYBRID (hybrid_search.py)

1. IMPOR PUSTAKA
   - `dataclass`, tipe data, objek `Document` Langchain.
   - `OpenAIEmbeddings`, `loguru` (logger), `Supabase`.
   - Modul pengaturan (settings) dan ekspansi query.
   - Konstanta: Dimensi Vektor (2000), default nilai parameter algoritma gabungan (RRF_K = 60).

2. STRUKTUR DATA HybridSearchResult
   - Menyimpan hasil pencarian yang sudah tergabung:
     - `document`: Objek teks lengkap (dari Langchain).
     - `hybrid_score`: Angka skor relevansi (gabungan vektor + kata).
     - `child_id`: ID unik potongan (chunk) anak.
     - `parent_id`: ID dokumen induk.

3. KELAS HybridSearcher
   - Bertugas mencari dokumen paling relevan menggunakan pencarian gabungan (BM25 Full Text Search + Vector Similarity). Penggabungan skor dilakukan oleh *Database PostgreSQL* memakai metode RRF (Reciprocal Rank Fusion).
   - `__init__`:
     - Buka koneksi Supabase.
     - Siapkan model pengubah kata ke vektor (Embedder) dari OpenAI.

   - `search(query, filters, top_k, enable_query_expansion)`:
     - TAHAP 1: EKSPANSI QUERY
       - Jika diaktifkan, ubah pertanyaan user menjadi bentuk yang lebih luas via LLM (fungsi `expand_query_smart`).
       - Contoh: "sks pi" -> "sks penulisan ilmiah syarat minimal".
     - TAHAP 2: EMBEDDING
       - Ubah query (pertanyaan) menjadi vektor 2000 dimensi menggunakan OpenAI.
       - Catat profil waktu eksekusi (`time.time()`) untuk proses Embedding.
     - TAHAP 3: EKSEKUSI PENCARIAN DATABASE (HYBRID RPC)
       - Siapkan parameter fungsi database (vektor, query asli, limit top K, bobot BM25, bobot Vektor, konstanta RRF, dan filter metadata (seperti section)).
       - Panggil prosedur database (RPC) bernama `hybrid_search`.
       - Catat profil waktu eksekusi RPC pencarian.
     - TAHAP 4: PENANGANAN KEGAGALAN (FALLBACK)
       - JIKA fungsi hybrid gagal atau kosong (mungkin karena query tidak cocok secara teks sama sekali):
         - Panggil pencarian Vektor saja (Dense Search) lewat prosedur `match_child_documents`.
         - Samakan skor kesamaan kosinus (similarity) dengan `rrf_score` agar formatnya tetap seragam.
     - TAHAP 5: FORMAT HASIL
       - LOOP setiap baris hasil dari database:
         - Bikin objek `Document` berisi teks utuh dan metadatanya (ID, judul, bab, sumber).
         - Masukkan ke objek `HybridSearchResult`.
     - Kembalikan daftar hasil (diurutkan berdasarkan skor `hybrid_score` dari terbesar).
```

#### File: `src/retrieval/parent_child.py`

```markdown
ALGORITMA PENGAMBILAN DOKUMEN INDUK (parent_child.py)

1. IMPOR PUSTAKA
   - Supabase client, loguru.
   - Konstanta pengaturan, model hasil pencarian (`HybridSearchResult`).

2. KELAS ParentChildFetcher
   - Konsep: Data dipecah kecil-kecil (anak) untuk dicari, tapi setelah ketemu, yang dikirim ke LLM adalah dokumen besar utuh (induk) agar LLM paham konteks lengkapnya.
   - `__init__`: Inisialisasi koneksi Supabase dan nama tabel dokumen induk (`table_parent_chunks`).

   - `fetch_parents(search_results)`:
     - TAHAP 1: PENGUMPULAN & DE-DUPLIKASI ID INDUK
       - Masukan: daftar potongan kecil (anak) hasil pencarian sebelumnya.
       - Siapkan sebuah kamus (dictionary) kosong bernama `parent_scores`.
       - LOOP tiap hasil pencarian anak:
         - Ambil `parent_id` dan skor relevansinya (`score`).
         - JIKA `parent_id` sudah ada di dalam kamus `parent_scores`:
           - Perbarui (Update) skor terbaiknya (pilih yang paling besar/maksimal).
           - Tambahkan ID anak ini ke daftar `matched_children`.
         - JIKA BELUM:
           - Buat rujukan baru di kamus: catat skor terbaik dan masukkan ID anak.
       - Ambil semua `parent_id` unik dari kamus tersebut.

     - TAHAP 2: AMBIL DOKUMEN INDUK DARI DATABASE
       - Gunakan query Supabase untuk memilih (Select) dokumen yang `parent_id`-nya ada dalam daftar unik tadi (`in_`).
       - Dapatkan data dokumen lengkapnya.
       - Catat profil waktu eksekusi pengambilan ke Supabase (`time.time()`).
       - Cek (Log Warning) jika ada `parent_id` yang ditarik tidak ditemukan fisiknya di tabel database (anomali).

     - TAHAP 3: TAMBAHKAN METADATA & URUTKAN KEMBALI
       - LOOP setiap dokumen induk yang didapat:
         - Ambil skor anak terbaiknya dari kamus `parent_scores`.
         - Ambil daftar ID anak yang memicu dokumen ini.
         - Sisipkan data tersebut ke dalam dokumen induk (kolom sementara: `best_child_score` dan `matched_children`).
       - Urutkan (Sort) daftar dokumen induk dari nilai `best_child_score` paling besar (menurun/descending).
     
     - Kembalikan daftar dokumen induk yang sudah berurut tersebut.
```

#### File: `src/retrieval/reranker.py`

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

#### File: `src/retrieval/source_utils.py`

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

**Bentuk Data Setelah Diproses:**
```json
// Daftar Dokumen Induk hasil penelusuran (Context)
[
  {
    "content": "Syarat mendaftar KKP adalah minimal telah menempuh 100 SKS...",
    "cross_encoder_score": 0.92,
    "title": "Syarat Pendaftaran"
  }
]
```

---

### Alur 6: Pembangkitan Jawaban (Generation)

**Bentuk Data Awal:**
```text
// Konteks dokumen + Pertanyaan User + Histori Percakapan
```

**File Pemroses (Pseudocode):**

#### File: `src/generation/chain.py`

```markdown
ALGORITMA GENERASI JAWABAN CHATBOT (chain.py)

1. IMPOR PUSTAKA
   - Langchain (Dokumen, Parser Output, Prompt Template, ChatOpenAI).
   - loguru (logger), modul konfigurasi, deteksi panduan.

2. KONSTANTA PROMPT
   - `SYSTEM_PROMPT`: Peran AI sebagai asisten akademik STMIK Wicida. Mengatur aturan menjawab (berbasis dokumen, cantumkan bab sumber, dilarang halusinasi, format list).
   - `HUMAN_PROMPT`: Format input untuk AI (Konteks dokumen + Pertanyaan User).
   - `HUMAN_PROMPT_WITH_HISTORY`: Format input yang mempertimbangkan histori percakapan.
   - `CONVERSATIONAL_PROMPT`: Format obrolan biasa (sapaan/terima kasih) tanpa pencarian dokumen.
   - `CLARIFICATION_PROMPT`: Format untuk meminta penjelasan lebih lanjut dari jawaban sebelumnya.

3. FUNGSI _format_context(documents)
   - Ambil list objek Dokumen dari proses Retrieval (Pencarian).
   - GABUNGKAN teks dari tiap dokumen dengan pembatas "---".
   - TAMBAHKAN header pada tiap dokumen (contoh: "[Sumber: Buku Panduan PI] - BAB II - Relevansi: 0.85").
   - KEMBALIKAN teks gabungan yang siap dibaca LLM.

4. FUNGSI _postprocess_answer(answer)
   - Rapikan hasil jawaban teks LLM.
   - HAPUS spasi berlebih dan ganti baris kosong yang terlalu banyak.
   - KEMBALIKAN teks rapi.

5. FUNGSI _build_sources(context_documents, limit=3)
   - Buat list meta-data sumber referensi (maksimal 3 teratas).
   - Ambil ID dokumen, judul, bab, dan skor kemiripan.
   - KEMBALIKAN array daftar sumber.

6. FUNGSI build_rag_chain(streaming)
   - Buat objek `ChatOpenAI` dengan model, suhu 0, dan token 1200.
   - Gabungkan `SYSTEM_PROMPT` dan `HUMAN_PROMPT`.
   - BENTUK "Chain" RAG: (Format Input Konteks) -> Prompt -> LLM -> Output String.
   - KEMBALIKAN chain.

7. KELAS RAGChain
   - Inisialisasi: Buat dan simpan instance LLM.
   - METHOD `invoke_with_history(question, context, history)`:
     - Log informasi pemrosesan.
     - **Adaptive History**: Jika dokumen konteks kosong (icu *Minimum Evidence Triggered*), potong histori paksa menjadi 1 giliran (maksimal 2 pesan terakhir) untuk mode obrolan biasa.
     - Hitung profil token input dan output menggunakan `tiktoken`.
     - Susun pesan konteks dan histori sebagai array `SystemMessage`, `HumanMessage`, dan `AIMessage`.
     - Masukkan konteks dan panggil LLM.
     - Cetak profil penggunaan token ke log.
     - Kembalikan jawaban LLM + sumber referensi.
   - METHOD `invoke_conversational(question, history)`:
     - Gunakan saat pengguna hanya basa-basi ("Halo", "Terima kasih").
     - Panggil LLM tanpa memasukkan dokumen konteks berat.
     - Kembalikan jawaban saja (sumber = kosong).
   - METHOD `invoke_clarification(question, history, last_context)`:
     - Gunakan jika pengguna minta penjelasan tambahan ("Tolong jelaskan lebih detail").
     - Cek apakah topik masih relevan dengan dokumen lama (`_check_context_relevance`).
     - Jika TIDAK RELEVAN (< 0.3): Beralih (Fallback) jalankan Retrieval pencarian ulang.
     - Jika RELEVAN: Minta LLM menjelaskan ulang dokumen sebelumnya.
     - Kembalikan jawaban.

8. FUNGSI generate_answer(question, context)
   - Fungsi sederhana untuk mengeksekusi Chain reguler.
   - Format jawaban dan kembalikan output-nya.
```

**Bentuk Data Setelah Diproses:**
```json
// Hasil Output Chatbot ke User
{
  "answer": "Berdasarkan pedoman KKP, syarat pendaftarannya adalah:\n1. Menempuh minimal 100 SKS\n2. Tidak ada nilai E\n3. IPK minimal 2.0.",
  "num_docs": 1,
  "intent": "needs_retrieval",
  "confidence": 0.99,
  "sources": [{"title": "Syarat Pendaftaran", "section": "BAB II"}]
}
```

---

### Di Luar Alur Utama (Config, Middleware, Evaluation)

**File Pemroses (Pseudocode):**

#### File: `config/settings.py`

```markdown
ALGORITMA KONFIGURASI SISTEM (config/settings.py)

1. IMPOR PUSTAKA
   - pydantic dan pydantic_settings (untuk memvalidasi dan memuat tipe data otomatis dari .env)

2. FUNGSI _find_env_file()
   - Cari file konfigurasi ".env".
   - Mulai dari direktori saat ini.
   - ULANGI hingga 5 level folder ke atas:
     - Jika file ".env" ditemukan di folder tersebut, kembalikan path-nya.
     - Mundur 1 level direktori.
   - KEMBALIKAN fallback ".env" jika tidak ditemukan secara eksplisit.

3. KELAS Settings (mewarisi BaseSettings)
   - Konfigurasi ini otomatis memuat variabel dari file `.env`.
   
   - VARIABEL APLIKASI UTAMA:
     - APP_NAME (Default: "Chatbot KKP/PI Assistant")
     - VERSION
     - ENVIRONMENT ("development", "staging", "production")
     - DEBUG mode
   
   - KONFIGURASI OPENAI (Wajib Diisi):
     - open_api_key, llm_model, embedding_model
     - Rate limit dan toleransi timeout OpenAI (retry max 3 kali).
     
   - KONFIGURASI DATABASE SUPABASE (Wajib Diisi):
     - supabase_url, supabase_service_key
     - Nama-nama tabel database (parent_documents, child_documents, user_quotas, chat_logs, conversation_sessions)
     
   - PENGATURAN RETRIEVAL (Pencarian RAG):
     - retrieval_top_k: jumlah potongan dokumen maksimal dicari (default 30)
     - rerank_top_n: jumlah dokumen final setelah disaring (default 8)
     - max_parent_for_rerank: jumlah maksimal parent dikirim ke reranker (default 8)
     - min_parent_for_rerank: syarat minimal parent agar reranker jalan (default 3)
     - rerank_min_top_score: skor top minimal untuk melanjutkan (default 0.0)
     - rerank_relative_gap: gap skor dari top score untuk menjaga dokumen (default 2.5)
     - bm25_weight: bobot pencarian teks BM25 (default 0.4)
     - dense_weight: bobot pencarian vektor semantic (default 0.6)
     
   - PENGATURAN MODEL LOKAL:
     - cross_encoder_model (untuk reranking dokumen lokal)
     
   - PENGATURAN TELEGRAM BOT:
     - TELEGRAM_BOT_TOKEN
     - Webhook URL, Secret Token, Path Webhook
     
   - PENGATURAN RATE LIMIT & MEMORI:
     - Batas request per hari (RATE_LIMIT_REQUESTS).
     - Maksimal sesi chat aktif, interval pembersihan sesi lama.
     - Penggunaan Database Sessions (USE_DATABASE_SESSIONS: True).
     - MAX_HISTORY_TURNS: Batas jumlah giliran histori yang dikirim ke LLM (default 3).

4. METODE VALIDATOR DATA:
   - FUNGSI validate_weights_sum:
     - Pastikan bahwa `bm25_weight` + `dense_weight` sama dengan 1.0. 
     - JIKA hasil jumlah tidak 1.0, lemparkan error "must equal 1.0".
   - FUNGSI validate_webhook_secret:
     - JIKA environment = "production" DAN ada webhook URL:
       - Pastikan token rahasia ada dan panjangnya minimal 16 karakter.
       - Jika tidak, lemparkan error keamanan.
   - FUNGSI validate_required_secrets:
     - Cek OpenAI key, Supabase key, dan Telegram bot token agar tidak boleh bernilai string kosong.

5. FUNGSI PEMBANTU (Helper Methods):
   - get_openai_config(): Mengembalikan dictionary konfigurasi khusus API OpenAI.
   - get_supabase_config(): Mengembalikan dictionary konfigurasi database Supabase.
   - is_production(): Cek apakah environment sedang production.
   - is_development(): Cek apakah environment sedang development.

6. FUNGSI get_settings()
   - Menggunakan `@lru_cache` (pola Singleton).
   - Memastikan kelas `Settings` hanya di-load 1 kali dari memori selama aplikasi berjalan.
   - KEMBALIKAN instance `Settings`.
```

#### File: `src/middleware/monitoring.py`

```markdown
ALGORITMA MIDDLEWARE PEMANTAUAN KINERJA (monitoring.py)

1. IMPOR PUSTAKA
   - `time`, `asyncio`, struktur data (`dataclass`), FastAPI/Starlette Middleware, loguru.

2. STRUKTUR DATA
   - `RequestMetrics`: Rekaman 1 request (waktu, metode HTTP, path, kode status HTTP, durasi ms, session ID, error).
   - `SystemMetrics`: Rekaman agregat (total requests, sukses, gagal, rata-rata durasi, sesi aktif). Menyimpan maksimal 1000 request terakhir di memori.
     - Punya fungsi `add_request` untuk mencatat request baru.
     - Punya fungsi `get_stats` untuk menarik ringkasan statistik berdasar jendela waktu tertentu (misal: 60 menit terakhir).

3. INSTANSI GLOBAL
   - `_system_metrics`: Variabel global (Single source of truth) untuk menyimpan metrik selama server berjalan.

4. KELAS MetricsMiddleware
   - Bertugas mencegat (intercept) setiap request yang masuk ke server FastAPI.
   - ALGORITMA `dispatch`:
     - Catat waktu mulai (`start_time`).
     - Jika request menuju API `/chat` (metode POST):
       - Coba bongkar (parse) JSON body-nya untuk mencari nilai `session_id`.
       - Susun ulang body agar bisa dibaca lagi oleh fungsi tujuan (karena body aslinya sekali baca hilang).
     - Lanjutkan eksekusi request ke fungsi utamanya (`call_next`).
     - Setelah selesai, catat waktu akhir dan hitung `duration_ms`.
     - Buat objek `RequestMetrics` dan simpan ke `_system_metrics`.
     - JIKA durasi > 5 detik: Tulis Peringatan (Warning) di log konsol (Request terlalu lambat).
     - Sisipkan *Header HTTP* "X-Response-Time" ke respon balik klien.

5. KELAS PerformanceTracker & AsyncPerformanceTracker
   - Digunakan dengan blok `with` (Context Manager) untuk menghitung lama waktu eksekusi sepotong fungsi tertentu (seperti Timer stopwatch).
   - Saat masuk blok (Enter): Mulai timer.
   - Saat keluar blok (Exit): Hentikan timer, hitung durasi.
   - Jika > 1 detik, tulis Warning. Jika di bawah 1 detik, cukup tulis Debug.
   - Jika ada error (exception), tulis Error log.

6. FUNGSI DEKORATOR track_performance
   - Membungkus (wrap) suatu fungsi (baik sinkron maupun asinkron).
   - Akan otomatis mengaplikasikan `PerformanceTracker` pada fungsi yang dipasangi penanda `@track_performance`.

7. FUNGSI UTILITAS SISTEM (Cek RAM & CPU)
   - `get_memory_usage()`: Gunakan modul `psutil` untuk mendapat total RAM yang dipakai aplikasi (dalam MB dan Persentase).
   - `get_cpu_usage()`: Mendapat angka persentase pemakaian CPU.
```

#### File: `src/middleware/security.py`

```markdown
ALGORITMA MIDDLEWARE KEAMANAN (security.py)

1. IMPOR PUSTAKA
   - `time`, hashing (`hashlib`, `hmac`), FastAPI Middleware, loguru.
   - Konfigurasi aplikasi.

2. KELAS RateLimitMiddleware
   - Tujuan: Membatasi jumlah *request* dari 1 klien per waktu (misal: 100 req per 60 detik) untuk cegah spam/DDoS.
   - `__init__`: Set batas limit dan jendela waktu (dari settings).
   - `_get_client_id`:
     - Tentukan identitas klien: Cek `session_id`.
     - Jika tidak ada, fallback ambil IP klien (dari header "X-Forwarded-For" atau host).
   - `_check_rate_limit`:
     - Bersihkan catatan request lama yang sudah kedaluwarsa.
     - Hitung total request dari Klien ID tersebut dalam waktu aktif.
     - JIKA total >= batas: Tolak (Kembalikan False).
     - JIKA total < batas: Catat request baru (Kembalikan True).
   - `dispatch`:
     - Abaikan URL `/health`.
     - Cek dengan `_check_rate_limit`.
     - JIKA dilarang: Lemparkan HTTPException (kode 429 Too Many Requests).
     - JIKA boleh: Lanjutkan request, dan tambahkan informasi Sisa Kuota (X-RateLimit-Remaining) ke Header Respon klien.

3. KELAS SecurityHeadersMiddleware
   - Tujuan: Menambah Header Keamanan HTTP wajib sesuai standar (untuk cegah eksploitasi peramban/browser).
   - `dispatch`:
     - Lanjutkan request. Pada saat memberikan response, tambahkan header:
       - `X-Content-Type-Options: nosniff`
       - `X-Frame-Options: DENY` (cegah Clickjacking iframe)
       - `X-XSS-Protection: 1; mode=block`
       - `Referrer-Policy`
     - Jika status Server adalah Produksi, aktifkan juga HSTS (`Strict-Transport-Security`).

4. FUNGSI verify_telegram_webhook(request_body, signature)
   - Digunakan agar orang luar tidak bisa sembarangan memalsukan *push message* seolah dari server Telegram.
   - Lakukan perhitungan HASH/HMAC SHA-256 pada body dengan Kunci Rahasia.
   - Bandingkan hasilnya (signature dari header) dengan hasil hitung kita secara konstan (pakai `hmac.compare_digest`).

5. FUNGSI sanitize_input(text, max_length)
   - Membersihkan teks masukan dari karakter berbahaya, tapi membiarkan teks natural bahasa Indonesia tetap utuh.
   - Potong panjang maksimal teks (default 1000).
   - Buang control character (seperti NULL byte atau escape character).
   - Normalisasi spasi putih ganda menjadi satu spasi saja.
   - Kembalikan teks bersih.

6. FUNGSI validate_chat_input(question, session_id)
   - Cek ID sesi (hanya boleh alfanumerik dan garis bawah/strip, minimal 3 maks 100 huruf).
   - Panggil `sanitize_input` ke pertanyaan.
   - Pastikan teks pertanyaan tidak kosong dan minimal 3 karakter.
   - Jika ada salah satu yang melanggar, lemparkan Error `InputValidationError`.

7. FUNGSI UTILITAS
   - `generate_secure_token`: Hasilkan token acak yang aman kriptografis.
   - `hash_sensitive_data`: Enkripsi/Sembunyikan teks penting agar aman ditulis ke log (hanya 16 karakter depan).
```

#### File: `src/evaluation/ragas_eval.py`

```markdown
ALGORITMA EVALUASI RAGAS DENGAN GROUND TRUTH (ragas_eval.py)

1. IMPOR PUSTAKA DAN KONSTANTA
   - RAGAS, metrik (faithfulness, relevancy, correctness, similarity, context_precision, context_recall).
   - Langchain (ChatOpenAI, OpenAIEmbeddings), datetime, math, loguru.
   - Definisi target threshold (nilai batas minimum = 0.85 untuk semua metrik).

2. DATASET EVALUASI (DENGAN GROUND TRUTH)
   - `EVAL_QUESTIONS_PI`: Kumpulan pertanyaan PI lengkap dengan `ground_truth` (kunci jawaban faktual).
   - `EVAL_QUESTIONS_KKP`: Kumpulan pertanyaan KKP lengkap dengan `ground_truth`.

3. FUNGSI get_eval_questions(dataset)
   - Ambil kumpulan soal berdasarkan nama dataset ("pi" atau "kkp").

4. FUNGSI create_evaluation_dataset(dataset)
   - Wrapper untuk mengambil list soal dan ground truth-nya.

5. FUNGSI _diagnose_metric(metric_name, score)
   - FUNGSI DIAGNOSTIK: Menganalisa penyebab jika ada skor metrik yang di bawah 0.85.
   - JIKA "faithfulness" gagal: "LLM berhalusinasi". Rekomendasi: perkuat prompt "jangan menambah info".
   - JIKA "answer_relevancy" gagal: "Jawaban menyimpang". Rekomendasi: perbaiki prompt "jawab langsung".
   - JIKA "answer_correctness" gagal: "Fakta salah". Rekomendasi: cek dokumen retriever atau perbaiki ground truth.
   - JIKA "answer_similarity" gagal: "Secara semantik jauh". Rekomendasi: jawaban ringkas.
   - JIKA "context_precision" gagal: "Top dokumen tidak relevan". Rekomendasi: kurangi top-K, tuning hybrid search.
   - JIKA "context_recall" gagal: "Dokumen yang dicari tidak ketemu". Rekomendasi: perbaiki chunking, cek ingest data.
   - KEMBALIKAN kamus (dictionary) berisi saran perbaikan.

6. FUNGSI UTAMA run_evaluation(pipeline_fn, eval_data, output_path)
   - Siapkan data evaluasi.
   - TAHAP 1: Generate Jawaban
     - LOOP semua soal: 
       - Panggil `pipeline_fn` (Chatbot) dengan pertanyaan.
       - Simpan teks jawaban (answer) dan dokumen (contexts).
       - Buat objek `SingleTurnSample` yang berisi: input user, response, contexts, reference (ground truth).
   - TAHAP 2: Buat Dataset
     - Jadikan `EvaluationDataset` Ragas.
   - TAHAP 3: Setup AI Penilai
     - Inisialisasi LLM `ChatOpenAI` dan `OpenAIEmbeddings`.
   - TAHAP 4: Jalankan RAGAS
     - Panggil `evaluate()` dengan 6 metrik bawaan RAGAS.
   - TAHAP 5: Hitung Agregat
     - Rata-ratakan skor tiap metrik (`_safe_score`).
     - Hitung rata-rata `overall`.
   - TAHAP 6: Evaluasi Hasil & Cetak Konsol
     - Cek apakah semua skor metrik ≥ 0.85.
     - Print persentase dan bar grafik sederhana (#).
   - TAHAP 7: Buat Diagnostik Gagal
     - Untuk setiap metrik yang gagal (< 0.85):
       - Panggil `_diagnose_metric()`.
       - Cari soal mana saja yang punya skor jelek di metrik tersebut (diurutkan dari yang terburuk).
       - Cetak penyebab kegagalan dan 3 pertanyaan terburuk ke log.
   - TAHAP 8: Simpan Laporan JSON
     - Bentuk struktur data laporan (konfigurasi, metrik lulus/gagal, detail tiap soal, dan diagnostik).
     - Tulis ke file (default: `evaluation_results_TIMESTAMP.json`).
     - KEMBALIKAN skor keseluruhan.
```

#### File: `src/evaluation/ragas_eval_no_gt.py`

```markdown
ALGORITMA EVALUASI RAGAS TANPA GROUND TRUTH (ragas_eval_no_gt.py)

1. IMPOR PUSTAKA DAN KONSTANTA
   - RAGAS, metrik (faithfulness, relevancy, context precision, custom score).
   - Langchain (ChatOpenAI, OpenAIEmbeddings), datetime, loguru.
   - Definisi `MetricRole` (HARD_GUARDRAIL, QUALITY_SIGNAL, BUSINESS_KPI).
   - Definisi konfigurasi tiap metrik (`METRIC_CONFIG`): target skor minimum, alasan, dan batasan false-negative.

2. DATASET PERTANYAAN
   - Kumpulan pertanyaan PI (`EVAL_QUESTIONS_PI`).
   - Kumpulan pertanyaan KKP (`EVAL_QUESTIONS_KKP`).

3. FUNGSI build_custom_metrics(evaluator_llm)
   - Buat metrik kustom dengan deskripsi LLM prompt:
     - `answer_completeness`: Mengukur kelengkapan informasi (fakta utama, syarat, konteks).
     - `answer_actionability`: Mengukur informasi konkret yang dapat dilakukan (angka spesifik, langkah-langkah).
   - KEMBALIKAN dictionary berisi objek metrik ini.

4. FUNGSI PEMBANTU (Helpers)
   - `_safe_score(value)`: Amankan hasil perhitungan metrik, jika tidak ada/error ganti jadi None.
   - `_get_score_at_index(metric_result, index)`: Ambil skor spesifik untuk 1 pertanyaan dalam daftar hasil evaluasi.
   - `_is_faithfulness_false_negative_suspect(score, context, answer)`: 
     - JIKA skor faithfulness terlalu rendah (< 0.8), TAPI ada dokumen panjang dan jawaban panjang: 
     - Tandai sebagai suspek "False Negative" (mungkin LLM salah nilai karena beda bahasa/parafrase).
   - `_categorize_item_result(item_metrics)`: Kategori status:
     - JIKA precision rendah -> "RETRIEVER_ISSUE"
     - JIKA faithfulness rendah -> "POSSIBLE_HALLUCINATION"
     - JIKA completeness rendah -> "INCOMPLETE_ANSWER"
     - JIKA relevancy rendah -> "LOW_RELEVANCY"
     - SELAIN ITU -> "PASS"

5. FUNGSI evaluate_rag_no_ground_truth(questions, answers, contexts, dataset_name)
   - Siapkan konfigurasi LLM penilai (ChatOpenAI suhu=0) dan Embedding (OpenAIEmbeddings).
   - Bangun metrik evaluasi (Faithfulness, Relevancy, Context Precision tanpa reference, Completeness, Actionability).
   - Bentuk `Dataset` HuggingFace (questions, answers, contexts).
   - JALANKAN fungsi `evaluate()` dari Ragas (akan mengirim API ke OpenAI).
   - Kumpulkan skor agregat rata-rata.
   - CEK Quality Gate:
     - Kategorikan error menjadi Guardrail Failures (fatal), Quality Warnings, dan Business KPI failures berdasar `MetricRole`.
   - SIAPKAN Laporan detail tiap pertanyaan:
     - Kategorikan tipe error.
     - Deteksi kebutuhan pengecekan manual (manual review).
   - CETAK hasil ke log konsol (`_log_results`).
   - KEMBALIKAN hasil lengkap berbentuk dictionary JSON.

6. FUNGSI PENYIMPANAN
   - `save_evaluation_results`: Simpan keseluruhan skor hasil JSON ke file (`evaluation_results_TIMESTAMP.json`).
   - `export_manual_review_items`: Ambil data yang butuh dicek manual, simpan ke file (`manual_review_TIMESTAMP.json`).

7. FUNGSI UTAMA run_full_evaluation_no_gt(rag_pipeline_func, dataset)
   - Tentukan pertanyaan (PI / KKP / Both).
   - LOOP untuk setiap pertanyaan:
     - Masukkan pertanyaan ke `rag_pipeline_func` (Pipeline Chatbot asli).
     - Tangkap teks jawaban dan list dokumen.
   - JALANKAN `evaluate_rag_no_ground_truth()`.
   - SIMPAN kedua file laporan JSON.
   - KEMBALIKAN (hasil_dict, file_main, file_review).
```

---


---

## 6. Referensi Tambahan & Infrastruktur

### 6.1 Dependency & Versi Tech Stack
Berikut adalah *library* utama dan versinya berdasarkan file `requirements.txt`:
- **Web Framework**: `fastapi==0.136.1`, `uvicorn==0.46.0`
- **Telegram Bot**: `python-telegram-bot==22.7`
- **Langchain (RAG)**: `langchain==1.2.15`, `langchain-core==1.2.31`, `langchain-openai==1.1.14`
- **AI / Embeddings**: `openai==2.32.0`, `sentence-transformers==5.4.1`, `transformers==5.5.4`
- **Database (Supabase)**: `supabase==2.28.3`
- **Evaluasi**: `ragas==0.4.3`

### 6.2 Data Konfigurasi: `section_keywords.yaml`
Digunakan oleh modul `src/retrieval/self_query.py` untuk menyaring dokumen berdasarkan Bab tertentu (Self Querying). Pemetaannya berformat YAML *key-value*.

**Skema:**
```yaml
Nama Bab (Section):
  - kata kunci 1
  - frasa kata kunci 2
```

**Contoh Cuplikan YAML:**
```yaml
Front Matter:
  - kata pengantar
  - daftar isi

BAB I:
  - latar belakang panduan
  - tujuan panduan

BAB II:
  - dosen pembimbing
  - syarat kkp
  - sks minimal
```

### 6.3 Daftar Lengkap Environment Variables (`config/settings.py`)
| Nama Variabel | Default | Deskripsi | Validasi / Aturan |
| --- | --- | --- | --- |
| `APP_NAME` | `"Chatbot KKP/PI Assistant"` | Nama aplikasi. | Opsional |
| `VERSION` | `"1.0.0"` | Versi rilis aplikasi. | Opsional |
| `ENVIRONMENT` | `"development"` | Mode enviroment aplikasi. | `"development"`, `"staging"`, `"production"` |
| `DEBUG` | `False` | Mengaktifkan mode debug. | Opsional |
| `OPEN_API_KEY` | *(Wajib)* | Kunci API OpenAI (Sengaja typo di kode). | Tidak boleh kosong |
| `LLM_MODEL` | `"gpt-4o-mini"` | Model generasi bahasa alami OpenAI. | Opsional |
| `EMBEDDING_MODEL` | `"text-embedding-3-large"` | Model konversi teks ke vektor. | Opsional |
| `OPENAI_MAX_RETRIES` | `3` | Batas retries koneksi OpenAI. | 1 s/d 10 |
| `OPENAI_TIMEOUT` | `60` | Batas timeout koneksi OpenAI (detik). | 10 s/d 300 |
| `SUPABASE_URL` | *(Wajib)* | URL proyek basis data Supabase. | Tidak boleh kosong |
| `SUPABASE_SERVICE_KEY`| *(Wajib)* | Kunci otorisasi khusus (*service role*) Supabase. | Tidak boleh kosong |
| `TABLE_PARENT_CHUNKS` | `"parent_documents"` | Nama tabel induk dokumen. | Opsional |
| `TABLE_CHILD_CHUNKS` | `"child_documents"` | Nama tabel anak (vektor). | Opsional |
| `TABLE_USER_QUOTAS` | `"user_quotas"` | Nama tabel kuota user. | Opsional |
| `TABLE_CHAT_LOGS` | `"chat_logs"` | Nama tabel riwayat log percakapan. | Opsional |
| `TABLE_CONVERSATION_SESSIONS` | `"conversation_sessions"` | Nama tabel manajemen sesi. | Opsional |
| `RETRIEVAL_TOP_K` | `30` | Jumlah awal chunk vektor ditarik sebelum *rerank*. | 5 s/d 100 |
| `RERANK_TOP_N` | `8` | Jumlah dokumen final setelah *rerank*. | 3 s/d 20 |
| `BM25_WEIGHT` | `0.4` | Bobot keyword *Hybrid Search*. | **Wajib 1.0** dg `DENSE_WEIGHT` |
| `DENSE_WEIGHT` | `0.6` | Bobot vektor *Hybrid Search*. | **Wajib 1.0** dg `BM25_WEIGHT` |
| `RAGAS_SAMPLE_SIZE` | `50` | Jumlah sampel untuk metrik evaluasi Ragas. | 10 s/d 500 |
| `RAGAS_TIMEOUT` | `300` | Batas waktu evaluasi Ragas (detik). | 60 s/d 600 |
| `CROSS_ENCODER_MODEL` | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` | Model klasifikasi silang untuk Reranking lokal. | Opsional |
| `CROSS_ENCODER_BATCH_SIZE` | `32` | Ukuran batch reranker model. | 1 s/d 128 |
| `HF_TOKEN` | `None` | Token akses Hugging Face (opsional). | Opsional |
| `LOG_LEVEL` | `"INFO"` | Tingkat pencatatan Log (Loguru). | `"DEBUG"`, `"INFO"`, dll |
| `LOG_FILE` | `None` | Lokasi file log lokal (opsional). | Opsional |
| `TELEGRAM_BOT_TOKEN` | *(Wajib)* | Token bot Telegram. | Tidak boleh kosong |
| `TELEGRAM_WEBHOOK_URL`| `""` (Kosong) | Endpoint webhook bot saat di production. | Opsional |
| `TELEGRAM_WEBHOOK_SECRET` | `""` (Kosong) | Kunci rahasia pengaman webhook. | **Wajib** & min 16 char (prod) |
| `TELEGRAM_WEBHOOK_PATH` | `"/api/telegram/webhook"` | Lokasi path URL internal webhook. | Opsional |
| `RATE_LIMIT_REQUESTS` | `13` | Maksimal kueri per pengguna. | 1 s/d 100 |
| `RATE_LIMIT_WINDOW` | `86400` | Jeda siklus pembatasan dalam detik. | 3600 s/d 604800 |
| `MAX_CONCURRENT_REQUESTS`| `10` | Batas jumlah request serentak ke API. | 1 s/d 50 |
| `REQUEST_TIMEOUT` | `30` | Waktu tunggu maksimum endpoint chat (detik). | 10 s/d 120 |
| `MAX_ACTIVE_SESSIONS` | `1000` | Kapasitas batas atas manajemen sesi aktif. | 100 s/d 10000 |
| `SESSION_CLEANUP_INTERVAL`| `3600` | Waktu kedaluwarsa sesi pasif (detik). | 300 s/d 7200 |
| `USE_DATABASE_SESSIONS` | `True` | Menggunakan Supabase untuk state storage. | `True`/`False` |
| `PORT` | `8000` | Variabel environment (non-settings.py) untuk port. | Opsional |

### 6.4 Autentikasi & Keamanan Endpoint (`/api/ai/chat`)
Endpoint utama `/api/ai/chat` berjalan sebagai **endpoint publik** yang tidak memerlukan Autentikasi statis (seperti *API Key*). Sistem perlindungannya bersandar penuh pada:
1. **RateLimitMiddleware**: Setiap pengguna dibatasi maksimal 13 sesi pertanyaan per 24 jam (berdasarkan `session_id` atau Alamat IP).
2. **Validasi Session ID & Input ValidationError**: `InputValidationError` (berlokasi di `security.py`) adalah sebuah *Custom Exception Class* kosong. Exception ini murni di-_raise_ untuk melempar error agar ditangani *Middleware* jika `session_id` berformat salah atau jika teks kueri `question` terlalu pendek (kurang dari 3 huruf).
3. **Input Sanitization**: Menghilangkan kontrol karakter jahat.

### 6.5 Arsitektur Infrastruktur & Deployment
1. **Testing**: Saat ini belum ada direktori khusus `/tests` untuk pengujian integrasi *(Unit Testing)*.
2. **Deployment**: Sistem berjalan dan di-*deploy* melalui _containerization_ (Docker). Konfigurasi infrastruktur terdefinisi di file `Dockerfile` dan `docker-compose.yml`.
3. **Migrasi Database**: File berektensi `.sql` di `/scripts` harus dieksekusi secara manual via Supabase SQL Editor. Tidak ada utilitas *Migration Runner* otomatis (seperti *Alembic*).
4. **Data Retention / Cleanup**: Untuk menjamin memori sesi Telegram tidak membludak, Supabase RPC `cleanup_idle_sessions` melakukan penghapusan *session_id* yang sudah pasif melampaui `SESSION_CLEANUP_INTERVAL`.
5. **Observability**: Log sistem menggunakan *library* `loguru` yang menyimpan catatannya secara lokal di *console* dan belum diekspor ke layanan sentralisasi (*Datadog* / *Sentry* dll).


## Checklist Kelengkapan File
- Total file di project: **37** (Tidak termasuk file data seperti section_keywords.yaml)
- Total file yang ada pseudocode-nya di dokumen ini: **37**

> [!NOTE]
> Semua file (100%) kode program sudah terwakili secara lengkap dalam dokumen ini.





