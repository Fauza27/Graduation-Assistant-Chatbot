# Penjelasan program saat ini

Tanggal penulisan: 15 September 2026.

Dokumen ini menjelaskan implementasi yang ada di kode sekarang, bukan seluruh
rencana pengembangan. Penjelasan database mengacu pada kode dan migration;
database tidak diubah atau diperiksa ulang secara langsung saat dokumentasi ini dibuat.
Angka konfigurasi di bawah adalah default dalam kode dan dapat diganti melalui `.env`.

## 1. Program ini melakukan apa?

Program ini adalah chatbot akademik berbasis **Retrieval-Augmented Generation
(RAG)** untuk pedoman PI, KKP, Skripsi, dan Non-Skripsi. Ketika menerima pertanyaan,
program mencari bagian pedoman yang relevan, kemudian meminta LLM menyusun jawaban
dengan menggunakan bagian tersebut sebagai konteks.

Selain chatbot, tersedia pengelolaan akun dan riwayat percakapan, dashboard admin
untuk pengelolaan chunk dan monitoring, serta evaluation agent untuk menyelidiki
kasus jawaban yang gagal. Website memakai frontend Next.js; backend memakai
FastAPI. Data disimpan di Supabase/PostgreSQL, pencarian semantik memakai embedding,
dan pengurutan ulang memakai model cross-encoder.

Model dan batas operasional ditentukan oleh [config/settings.py](../config/settings.py).
Contoh pengaturan tanpa credential asli ada di [.env.example](../.env.example).
Panduan halaman dan alur admin frontend ada di [FRONTEND_UI.md](FRONTEND_UI.md).

## 2. Peta komponen utama

| Komponen | Tanggung jawab | Lokasi |
| --- | --- | --- |
| Entry point | Menjalankan server, CLI, ingestion, atau evaluasi lama | `main.py` |
| Aplikasi HTTP | Membuat FastAPI, memasang router, CORS, dan lifecycle | `application.py` |
| API | Validasi request, autentikasi, dan respons HTTP | `src/api/` |
| Service chatbot | Menghubungkan session, query, retrieval, generation, dan monitoring | `src/services/ai_services.py` |
| Query planner | Menyiapkan query pencarian dan menangani pertanyaan lanjutan | `src/retrieval/query_planner.py` |
| Retrieval | Filter, pencarian hybrid, pengambilan parent, dan reranking | `src/retrieval/` |
| Generation | Prompt, pemanggilan LLM, dan memory percakapan | `src/generation/` |
| Session | Penyimpanan percakapan dan cache session | `src/services/session_strategy.py`, `session_store.py` |
| Auth | Verifikasi Google, JWT, dan refresh token | `src/auth/` |
| Monitoring | Metrik, trace, biaya, dan snapshot konfigurasi | `src/monitoring/` |
| Evaluation agent | Membaca PDF asli, mencari penyebab gagal, dan merekomendasikan perbaikan | `src/evaluation_agent/` |
| Evaluasi RAGAS | Evaluasi metrik yang terpisah dari agent investigasi | `src/evaluation/` |
| Worker manual | Registrasi dokumen, evaluasi batch, dan regression | `scripts/` |

Folder `src/bot/` dan `src/ingestion/` tetap dipertahankan. Detail internal kedua
folder tersebut tidak termasuk peninjauan sumber untuk panduan ini. Kode lama
di `src/generation/intent_classifier/ga_dibutuhin_lagi/` juga dipertahankan sebagai
arsip pengguna. Keberadaan file lama tidak berarti file itu dipanggil chatbot aktif.

## 3. Alur pertanyaan di website

```text
Mahasiswa mengirim pertanyaan dari frontend
  → API memeriksa token, input, kapasitas request, dan kuota
  → Service memuat memory session milik mahasiswa
  → Query planner menyiapkan query pencarian
  → Retrieval mencari child chunk dan mengambil parent terkait
  → Reranker memilih dokumen yang paling relevan
  → LLM menerima pertanyaan + dokumen + summary + percakapan terbaru
  → Jawaban ditambahkan ke memory
  → Jika memory melewati anggaran token, percakapan lama diringkas
  → Session, log, metrik, dan trace disimpan
  → Jawaban dikirim ke frontend
```

Service utama ada di [ai_services.py](../src/services/ai_services.py). Riwayat
dipakai untuk membantu memahami pertanyaan lanjutan. Dokumen yang berhasil
ditemukan tetap menjadi sumber informasi akademik; summary percakapan bukan
pengganti pedoman asli.

Endpoint chat publik website adalah `POST /api/ai/chat`. Request website memerlukan
identitas mahasiswa. Client publik tidak bisa menyamar sebagai channel Telegram
untuk melewati autentikasi; jalur Telegram menggunakan webhook internal dengan
pemeriksaan secret tersendiri.

## 4. Pemrosesan query sekarang

Query planner menyimpan beberapa bentuk pertanyaan agar perubahannya dapat dilacak:

| Bentuk | Makna |
| --- | --- |
| `original_query` | Pertanyaan persis dari pengguna |
| `normalized_query` | Pertanyaan setelah normalisasi |
| `resolved_query` | Pertanyaan yang sudah diperjelas jika membutuhkan konteks sebelumnya |
| `search_queries` | Satu atau beberapa query untuk pencarian |
| `rerank_query` | Pertanyaan asli untuk menilai relevansi hasil retrieval |

Pertanyaan seperti “kalau yang itu bagaimana?” dapat membutuhkan reformulasi.
Program mencoba aturan deterministik terlebih dahulu; reformulator dapat memakai
LLM ketika perlu. Pertanyaan yang sudah jelas tidak otomatis membutuhkan panggilan
LLM tambahan untuk query planning.

Pertanyaan yang berisi beberapa subpertanyaan eksplisit dapat dipecah menjadi
maksimal tiga query pencarian. Hasilnya digabungkan sebelum seleksi dokumen akhir.
Pemecahan ini berbasis aturan, sehingga tidak setiap kalimat dengan kata “dan”
akan dipecah.

Alur aktif sudah **retrieval-first**: tidak menunggu classifier intent lama untuk
memutuskan apakah pertanyaan boleh mencari dokumen. Folder `intent_classifier`
masih berisi reformulator yang dipakai, tetapi itu berbeda dari classifier lama.

Referensi: [query_planner.py](../src/retrieval/query_planner.py) dan
[reformulator.py](../src/generation/intent_classifier/reformulator.py).

## 5. Bagaimana retrieval bekerja?

### Child dan parent mempunyai fungsi berbeda

**Child chunk** adalah potongan lebih kecil untuk pencarian yang spesifik.
**Parent document** berisi konteks lebih luas untuk menyusun jawaban. Setelah child
ditemukan, program mengambil parent yang terkait, sehingga LLM tidak hanya
menerima potongan pendek yang kehilangan penjelasan di sekitarnya.

### Tahapan pencarian

1. Membaca filter sumber/bagian yang dapat dikenali dari pertanyaan.
2. Melakukan ekspansi singkatan akademik jika sesuai.
3. Menggabungkan pencarian semantik berbasis embedding dan pencarian teks PostgreSQL.
4. Menggabungkan hasil beberapa query jika query planner melakukan dekomposisi.
5. Mengambil parent terkait dan membatasi kandidat yang masuk reranker.
6. Menilai relevansi kandidat dan menyiapkan konteks akhir untuk LLM.

Nama konfigurasi `bm25_weight` masih digunakan, tetapi jalur database aktif
menggunakan PostgreSQL full-text search dan penggabungan ranking. Nama itu tidak
berarti seluruh implementasi memakai mesin BM25 terpisah.

### Perubahan penting pada reranker

Input cross-encoder sekarang mencakup **judul, section, dan isi dokumen**. Judul
dan section membantu model memahami potongan yang isinya sendiri kurang jelas.
Teks gabungan dibatasi panjangnya; default batas input adalah 2.000 karakter.
Isi asli parent yang tersedia untuk generation tidak diganti oleh teks input ini.

Seleksi reranker mempertimbangkan skor kandidat terbaik, jarak skor relatif, dan
batas jumlah hasil. Jika jumlah kandidat kecil, pipeline dapat melewati
cross-encoder; jika reranker mengalami error, tersedia fallback berdasarkan
hasil hybrid. Trace mencatat sumber skor agar skor hybrid dan cross-encoder
tidak disalahartikan sebagai skala yang sama.

Contoh pengujian sebelumnya: pertanyaan tentang tiga syarat jalur Profesional
Non-Skripsi gagal karena parent yang berisi jawaban ditolak saat reranking.
Setelah judul dan section ikut diberikan, bukti yang benar masuk konteks dan
chatbot berhasil menjawab tiga syarat tersebut. Ini merupakan hasil untuk kasus
yang diuji, bukan jaminan bahwa semua pertanyaan sudah benar.

Referensi: [pipeline.py](../src/retrieval/pipeline.py) dan
[reranker.py](../src/retrieval/reranker.py).

## 6. Memory percakapan: dua level

### Level 1 — Percakapan terbaru

Memory menyimpan pesan terbaru pengguna dan assistant. Anggaran dihitung
berdasarkan token, bukan sekadar membuang pesan setelah mencapai lima turn.
Beberapa pasangan tanya-jawab terbaru tetap dipertahankan utuh.

### Level 2 — Summary percakapan lama

Summary dibuat **oleh LLM**, bukan oleh algoritma ringkasan buatan sendiri.
Program memberikan summary sebelumnya dan pasangan tanya-jawab lama kepada LLM,
lalu meminta satu ringkasan gabungan. Prompt meminta LLM mempertahankan topik,
kondisi yang dinyatakan pengguna, jawaban sebelumnya, serta hal yang belum selesai,
tanpa menambahkan fakta baru.

```text
Tambahkan jawaban ke memory
  → Hitung token summary dan pesan terbaru
  → Jika berlebih dan ada pasangan lama yang dapat dipadatkan:
      summary lama + percakapan lama → LLM → summary baru
  → Pasang summary baru dan keluarkan pasangan lama dari recent memory
  → Pertahankan pasangan terbaru dan simpan state session
```

Aturan memilih pesan lama dan menghitung token dijalankan kode. Penulisan isi
summary dilakukan LLM. Biaya panggilan summary ikut dicatat pada metrik request.

Default konfigurasi:

| Parameter | Default | Makna |
| --- | --- | --- |
| `MEMORY_MAX_HISTORY_TOKENS` | 2.500 | Target anggaran gabungan summary dan pesan terbaru |
| `MEMORY_MIN_RECENT_TURNS` | 2 | Minimal pasangan tanya-jawab terbaru yang dipertahankan |
| `MEMORY_SUMMARY_MAX_TOKENS` | 500 | Batas ukuran summary |

Pemadatan hanya mengeluarkan pesan lama setelah menerima summary yang valid.
Jika summarization gagal, pesan lama tetap dipertahankan. Bila pasangan terbaru
sangat panjang, anggaran dapat sementara terlampaui karena pasangan tersebut
dipertahankan. Jadi batas ini adalah mekanisme pengendalian konteks, bukan
jaminan bahwa setiap kondisi selalu tepat di bawah batas token.

Summary dan recent messages disimpan sebagai state terstruktur di penyimpanan
session yang sudah ada. Format state mendukung pembacaan data lama; perubahan
memory ini sendiri tidak membutuhkan tabel baru.

Referensi: [memory.py](../src/generation/memory.py),
[summarizer.py](../src/generation/summarizer.py), dan
[token_utils.py](../src/generation/token_utils.py).

## 7. Session, cache, dan cleanup

Dengan `USE_DATABASE_SESSIONS=true`, session disimpan di database dan memiliki
cache LRU di memory proses untuk mempercepat akses. LRU membuang entry yang
paling lama tidak dipakai ketika kapasitas penuh. Session yang keluar dari cache
dapat dimuat kembali dari database.

**Cleanup berkala hanya membersihkan cache, bukan menghapus percakapan database.**
Penghapusan session melalui tindakan pengguna merupakan operasi terpisah yang
tetap memeriksa kepemilikan session. Cache LRU bukan level ketiga memory percakapan.

Dengan `USE_DATABASE_SESSIONS=false`, session hanya berada di memory proses.
Cleanup atau restart dapat menghilangkan session pada mode tersebut karena tidak
ada penyimpanan persisten.

Ada pula cache hasil retrieval. Cache ini berbeda dari cache session dan tidak
menyimpan jawaban akhir LLM sebagai respons siap pakai. Versi/revisi knowledge base
ikut menentukan validitas cache agar perubahan chunk tidak memakai hasil lama.

## 8. Auth frontend dan backend

Frontend menampilkan proses login Google, lalu mengirim Google ID token ke
`POST /api/auth/google/verify`. Backend memverifikasi token Google, memperbarui
akun mahasiswa, dan mengeluarkan access token aplikasi. Frontend memakai token
itu sebagai `Authorization: Bearer ...` untuk endpoint yang dilindungi.

Backend tetap bertanggung jawab memeriksa identitas, role, dan kepemilikan data.
Membuka halaman login di frontend saja tidak membuat endpoint backend aman.
Admin menggunakan jalur autentikasi tersendiri dengan pemeriksaan akun admin.

Mekanisme refresh token tersedia dan dikendalikan `ENABLE_REFRESH_TOKENS`.
Jika aktif, refresh token disimpan melalui cookie HttpOnly, dirotasi ketika
dipakai, dan dapat dicabut saat logout. Jalur mahasiswa dan admin dipisahkan.
Default kode adalah `false`; jangan menganggap refresh aktif hanya karena
endpoint dan kode frontend sudah tersedia.

Referensi backend: [auth.py](../src/api/auth.py) dan `src/auth/`.
Referensi frontend: `frontend/src/lib/auth.ts`, `adminAuth.ts`, dan `api.ts`
di project induk.

## 9. Perlindungan request dan monitoring

Program membatasi jumlah request AI yang berjalan bersamaan dan lama tunggu
antrean. Kuota pengguna diperiksa/diperbarui dengan operasi database yang atomik.
Kapasitas request diperoleh sebelum kuota dipakai, sehingga request yang ditolak
karena server sibuk tidak langsung menghabiskan kuota.

Jika waktu request terlampaui, API dapat mengembalikan timeout. Pekerjaan dalam
thread tidak selalu bisa dihentikan langsung; slot tetap ditahan sampai pekerjaan
tersebut benar-benar selesai agar beban paralel tidak diam-diam membengkak.

Monitoring merekam ID request, durasi tahapan, token dan estimasi biaya, penggunaan
cache, kandidat retrieval, keputusan reranker, konteks akhir, jawaban, dan error.
Trace juga mencatat snapshot konfigurasi yang relevan dan checksum kode untuk
membedakan versi pipeline saat request dibuat dengan versi ketika dievaluasi.

Credential seperti API key, token, service key, dan isi `.env` tidak dimasukkan ke
snapshot konfigurasi. Trace percakapan tetap berisi pertanyaan dan konteks dokumen,
sehingga bukan data yang layak dipublikasikan sembarangan.

Health endpoint tersedia di `/health/`, `/health/liveness`, dan
`/health/readiness`. OpenTelemetry tersedia sebagai opsi, dengan default nonaktif.

## 10. Pengelolaan knowledge base oleh admin

Dashboard admin mendukung pemeriksaan dan pengeditan chunk. Jalur pengeditan
menjaga hubungan parent-child, merekam audit perubahan, mengelola status pembaruan
embedding, dan menginvalidasi cache retrieval yang terdampak.

Mengubah isi chunk tidak selalu langsung berarti embedding baru sudah selesai
dibuat. Status pekerjaan embedding perlu diperiksa sebelum menganggap pencarian
semantik sudah mencerminkan perubahan tersebut.

Jangan mengedit parent/child langsung di database tanpa memahami hubungan dan
aturan konsistensinya; jalur admin menyediakan pemeriksaan yang dipakai aplikasi.

## 11. Evaluation agent: cara kerja dan batasannya

Agent ini menyelidiki **mengapa sebuah jawaban gagal**, termasuk apakah jawaban
ada dalam dokumen asli tetapi gagal ditemukan/dipakai oleh pipeline.

### Dari mana kasus berasal?

- Otomatis: request tanpa dokumen relevan, semua kandidat ditolak, atau error retrieval.
- Manual: admin menandai jawaban yang salah atau tidak lengkap dari monitoring.

Kasus otomatis dimulai sebagai `unreviewed`. Jawaban keliru yang tetap mempunyai
hasil retrieval belum tentu terdeteksi oleh aturan otomatis; penilaian admin
tetap diperlukan untuk kasus tersebut. Expected answer, evidence, dan catatan
membantu verifikasi, tetapi tidak semua field wajib diisi saat membuat kandidat.

### Bagaimana batch diperiksa?

1. Admin memilih kasus dan membuat batch berstatus `pending`.
2. Worker manual menjalankan batch tersebut dari terminal.
3. Worker membaca PDF asli sesuai manifest, dari awal sampai akhir dalam window
   halaman yang saling overlap. Agent tidak hanya membaca chunk yang sudah dibuat.
4. Kandidat bukti diperiksa kembali bersama halaman di sekitarnya.
5. Bukti asli dibandingkan dengan child chunk dan trace pipeline.
6. Agent menentukan tahap gagal dan menyusun alasan serta rekomendasi spesifik.
7. Laporan disimpan ke database dan `results/evaluations/<RUN_ID>/`.

LLM dipakai untuk membaca/menganalisis bukti dan menyusun diagnosis. Kode juga
melakukan pemeriksaan terukur, seperti aturan seleksi reranker dan cakupan teks
chunk. Pemeriksaan cakupan kata bukan bukti sempurna tentang kesetaraan makna.

Agent dapat menilai masalah query, ketersediaan informasi, ekstraksi/chunking,
pencarian, perakitan parent, reranking, konteks akhir, atau generation sesuai data
yang tersedia. Untuk request lama dengan trace tidak lengkap, diagnosis memiliki
batasan; agent tidak dapat memulihkan skor yang tidak pernah disimpan.

### Rekomendasi dan perbaikan

Laporan yang dibaca admin sekarang berfokus pada **alasan gagal yang spesifik dan
rekomendasi perbaikannya**. Informasi teknis lengkap tetap disimpan dalam JSON dan
database untuk audit. Rekomendasi dapat menunjuk file, fungsi, atau parameter
tertentu dan harus membedakan usulan eksperimen dari perbaikan yang terbukti.

Agent tidak otomatis mengubah kode, konfigurasi, maupun chunk. Admin/pengembang
memutuskan perbaikan, kemudian menjalankan regression test: pertanyaan yang sama
dikirim ulang dalam session baru dan dibandingkan dengan bukti terverifikasi.
Langkah regression menggunakan bukti hasil evaluasi sebelumnya agar tidak perlu
membaca semua dokumen lagi untuk setiap perbaikan.

**Belum ada scheduler otomatis.** Membuat batch di dashboard hanya membuat antrean;
worker terminal diperlukan untuk memprosesnya. Memilih satu kasus juga tidak
otomatis membatasi dokumen yang dibaca; cakupan dokumen mengikuti manifest.

Panduan endpoint dan worker lengkap:
[RAG_EVALUATION_AGENT.md](RAG_EVALUATION_AGENT.md).

## 12. Database dan migration

Tabel knowledge base menyimpan parent dan child; tabel session menyimpan state
percakapan. Akun, kuota, log, audit chunk, dan request metrics mendukung operasi
aplikasi. Evaluation agent memerlukan penyimpanan terpisah untuk versi dokumen,
kasus, batch, bukti, temuan, rekomendasi, dan hasil regression agar tidak tercampur
dengan percakapan mahasiswa.

Migration baru di [migrations/](../migrations/):

| File | Tujuan utama |
| --- | --- |
| `2026091401_auth_refresh_tokens.sql` | Penyimpanan refresh token dan operasi rotasinya |
| `2026091402_request_trace_security.sql` | Pembatasan akses trace/request |
| `2026091403_rag_evaluation.sql` | Registry dokumen asli dan data evaluasi agent |
| `2026091601_chunk_quality.sql` | Publikasi lossless PI/KKP, sinkronisasi metadata, dan filter section berbasis prefix |
| `2026092101_evaluation_soft_failures.sql` | Alasan antrean evaluasi untuk jawaban abstain dan kasus gagal retrieval |

Migration evaluasi membuat `source_documents`, `source_document_versions`,
`rag_execution_traces`, `evaluation_cases`, `evaluation_runs`,
`evaluation_run_cases`, `evaluation_evidence`, `evaluation_findings`,
`evaluation_recommendations`, dan `regression_results`, serta tabel pencatat
migration. Ada pula penambahan metadata sumber pada tabel chunk yang sudah ada.
Migration kualitas chunk menambahkan versi dan urutan chunk, memperbaiki metadata
lama, memperketat filter bab, serta menyediakan RPC atomik untuk mengganti satu
parent bersama semua child dan embedding-nya tanpa mengubah ID.
Migration soft failure menyimpan alasan sebuah kasus masuk antrean evaluasi. Ini
memungkinkan agent membedakan informasi yang benar-benar tidak tersedia, retrieval
yang gagal, dan jawaban yang perlu menjelaskan batas cakupan bukti terkait.

Backup `backup/schema_20260913_222732.sql` adalah snapshot lama sebelum migration
evaluasi, sehingga tidak mewakili seluruh struktur terbaru. SQL lama di `scripts/`
dipertahankan untuk riwayat dan kebutuhan pemeliharaan; bukan daftar perintah
yang harus semuanya dijalankan kembali.

Rebuild PI/KKP memerlukan migration kualitas chunk tersebut sebelum script publikasi
database dijalankan. Ekspor JSON dapat dibangun dan diperiksa tanpa akses database.

## 13. Cara menjalankan dan memeriksa program

Semua perintah berikut dijalankan dari folder `backend`.

### Menjalankan server

```powershell
.\virtual_environment\Scripts\Activate.ps1
python main.py
```

Default port adalah 8000; variabel `PORT` dapat menggantinya. Pada environment
`development`, reload aktif. Dokumentasi API tersedia di `http://localhost:8000/docs`.
Frontend dijalankan terpisah dari folder frontend, mengikuti script `package.json`.

### Chat interaktif dari terminal

```powershell
python main.py --cli
```

Mode CLI berguna untuk pengujian lokal dan tidak sama dengan jalur auth website.

### Pengujian otomatis

```powershell
python -m pytest -q
```

`pytest.ini` membatasi koleksi ke `tests/`; script eksperimen historis dalam
arsip dokumentasi tidak ikut dijalankan sebagai test aktif.

### Menjalankan evaluation agent

Dependency evaluasi: `pip install -r requirements-eval.txt`. Fitur API dikendalikan
`EVALUATION_AGENT_ENABLED`; daftar PDF ada di `config/evaluation_documents.yaml`.

```powershell
python -m scripts.register_evaluation_documents
python -m scripts.run_failure_evaluation --run-id <RUN_ID>
python -m scripts.run_regression_evaluation --run-id <RUN_ID>
```

Ganti `<RUN_ID>` dengan ID batch, tanpa tanda `<` dan `>`. Registrasi dokumen
diperlukan saat menyiapkan/memperbarui sumber, bukan sebelum setiap batch.
Evaluasi membaca dokumen dan dapat menggunakan API LLM berbayar. Untuk mengubah
cakupan PDF, gunakan manifest yang sesuai; `--case-id` membatasi kasus, bukan sumber PDF.

### Mengekspor data chunk

```powershell
python scripts/database/export_child_documents.py
python scripts/database/export_parent_documents.py
```

CSV disimpan di `backup/exports/`. Utility ini mengekspor kolom tertentu, bukan
backup database lengkap; khusus ekspor parent, isi parent tidak disertakan.

## 14. Jika ingin mengubah bagian tertentu

| Kebutuhan | Mulai membaca dari |
| --- | --- |
| Jawaban pertanyaan lanjutan kurang tepat | Query planner, reformulator, memory |
| Jawaban ada di pedoman tetapi tidak ditemukan | Trace request, hybrid search, filter, child-parent |
| Dokumen benar ditemukan lalu ditolak | Reranker dan aturan seleksi dalam pipeline |
| Dokumen benar sudah masuk konteks tetapi jawaban salah | Generation chain dan prompt |
| Percakapan terlalu panjang atau summary kurang baik | Memory, summarizer, konfigurasi token |
| Riwayat session atau akses pengguna bermasalah | API sessions, session strategy/store, auth |
| Laporan agent perlu diubah | `src/evaluation_agent/report.py`, model client, dashboard evaluasi |
| Cakupan dokumen evaluasi berubah | Manifest dan document reader |

Gunakan request ID untuk menghubungkan pertanyaan, log, trace, dan evaluation case.
Lakukan perbaikan berdasarkan bukti tahap yang gagal, lalu ulangi kasus dan
pertanyaan kontrol untuk memeriksa dampaknya.

## 15. Perubahan besar dibanding dokumentasi lama

- Memory berubah dari batas jumlah turn menjadi recent messages dan summary LLM.
- Cleanup session tidak lagi dimaksudkan untuk menghapus data database secara berkala.
- Query memakai planner dan retrieval-first; classifier intent lama bukan gerbang chatbot aktif.
- Reranker menerima judul dan section selain content; keputusan kandidat tercatat lebih lengkap.
- Auth backend memeriksa identitas dan pemilik session, dengan dukungan refresh token opsional.
- Penanganan kapasitas, kuota, timeout, cache, dan monitoring diperkuat.
- Evaluation agent memiliki antrean kasus otomatis/manual, bukti PDF asli,
  diagnosis sesuai konfigurasi, laporan ringkas, dan regression runner.
- Root backend dirapikan; dokumentasi historis dan file data tetap disimpan.

Program masih berada dalam pengembangan. Scheduler agent dan perbaikan otomatis
oleh agent belum diterapkan. Dokumen di `docs/journal/` dan `ADR/` menjelaskan
riwayat keputusan; bila alurnya berbeda, gunakan panduan ini dan kode aktif sebagai
rujukan kondisi sekarang.
