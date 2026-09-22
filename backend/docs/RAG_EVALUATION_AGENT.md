# RAG Evaluation Agent

Fitur ini membantu admin mencari penyebab jawaban chatbot yang salah atau tidak
lengkap. Evaluator menggunakan empat sumber yang berbeda:

1. PDF asli sebagai sumber kebenaran.
2. Child chunk aktif untuk menilai hasil ekstraksi dan pemotongan dokumen.
3. Trace request untuk melihat query processing, retrieval, parent assembly,
   reranker, context akhir, dan jawaban.
4. Snapshot konfigurasi request, konfigurasi worker saat evaluasi, serta potongan
   fungsi dan prompt dari file pipeline yang telah ditentukan secara eksplisit.

Nilai API key, credential database, token, dan isi `.env` tidak dimasukkan ke
snapshot. Kode diambil sebagai teks tanpa dieksekusi. Checksum membedakan versi
kode request baru dari checkout saat evaluasi; request lama tanpa checksum
ditandai memiliki keterbatasan provenance.

Laporan Markdown dan dashboard menampilkan alasan gagal yang spesifik serta
rekomendasi perbaikan singkat dengan target file/fungsi/parameter. Konfigurasi,
source, bukti, dan catatan validasi tetap menjadi konteks analisis dan tersimpan
dalam JSON/database, tanpa memenuhi laporan yang dibaca admin.
Kriteria lulus reranking dirender dari aturan seleksi dan konfigurasi sebenarnya,
bukan threshold yang dikarang LLM. Eksperimen harus mencatat parameter yang dipakai,
memasukkan bukti ke context akhir, menjawab expected answer, dan melewati regresi.
Nilai usulan adalah eksperimen sampai regression test membuktikan hasilnya.
Agent harus menyebut keterbatasan data dan tidak boleh mengklaim penyebab
threshold tanpa skor yang lengkap.

Trace baru menyimpan seluruh skor reranker sebelum pemilihan top-N/relative gap,
alasan penerimaan/penolakan, dan panjang teks sebelum/sesudah pemotongan. Hal ini
tidak mengubah aturan pemilihan dokumen akhir. Input cross-encoder menyertakan
title dan section sebelum content, dengan batas panjang yang sama. Skor yang tidak tercatat pada trace lama
tidak dapat dipulihkan; diperlukan replay untuk mengujinya.

Evaluator hanya membuat temuan dan rekomendasi. Perubahan chunk, konfigurasi,
prompt, dan kode tetap memerlukan keputusan manusia.

## Alur penggunaan

1. Sistem otomatis memasukkan request tanpa dokumen relevan, seluruh kandidat
   yang ditolak, error retrieval, dan jawaban yang menyatakan informasi tidak
   tersedia sebagai kandidat `unreviewed`.
   Alasan antrean disimpan pada `queue_reason`.
2. Admin juga dapat membuka detail request pada halaman Monitoring dan menilai
   jawaban sebagai benar, salah, tidak lengkap, atau belum pasti.
   Expected answer dan catatan bersifat opsional.
3. Kandidat otomatis dan kasus yang ditandai admin muncul di halaman Evaluasi RAG.
4. Admin memilih kasus dan membuat batch. API hanya membuat antrean dengan status
   `pending`, sehingga proses panjang tidak berjalan di dalam web server.
5. Worker dijalankan dari terminal menggunakan `run_id` yang ditampilkan dashboard.
6. Worker menganalisis pertanyaan per sesi sebelum membaca dokumen. Hasilnya berisi
   pertanyaan mandiri, satu atau beberapa dokumen tujuan, jenis pertanyaan, serta
   kebutuhan informasi yang harus dibuktikan. Pertanyaan perbandingan, misalnya
   PI dan KKP, memiliki kebutuhan terpisah untuk setiap dokumen.
7. Routing bersifat lunak. Domain yang disebut mahasiswa dipertahankan, sementara
   routing ambigu atau berkeyakinan rendah diperluas agar dokumen yang benar tidak
   hilang akibat keputusan awal.
8. Worker memproses satu dokumen tujuan pada satu waktu. Seluruh halaman asli pada
   dokumen itu dibaca dan di-cache, lalu pencarian hanya dijalankan untuk pertanyaan
   yang diarahkan ke dokumen tersebut.
9. LLM memverifikasi kandidat terbaik beserta halaman di sekitarnya. Selain kutipan
   persis dan halaman fisik, verifier wajib memeriksa subjek, atribut, lingkup
   akademik, satuan, dan ID kebutuhan informasi yang benar-benar dijawab.
10. Jika tidak ada kandidat yang berhasil diverifikasi, statusnya
   `inconclusive`/`ambiguous`. Kondisi tersebut tidak dianggap sebagai bukti bahwa
   informasi tidak tersedia dan tidak boleh menghasilkan rekomendasi untuk
   menambah isi dokumen.
11. Pertanyaan baru dinyatakan memiliki jawaban setelah semua kebutuhan informasi
   tercakup. Bukti dari beberapa panduan digabungkan untuk pertanyaan lintas dokumen.
12. Bukti terverifikasi dibandingkan dengan chunk aktif. Untuk jawaban abstain,
   evaluator juga dapat menyimpan bukti yang terkait tetapi berbeda cakupan,
   misalnya aturan proposal ketika pertanyaannya tentang naskah akhir. Bukti
   tersebut tidak dianggap sebagai jawaban langsung.
13. Trace request kemudian digunakan untuk menentukan tahap kegagalan paling awal.
14. Admin membaca temuan dan menyetujui atau menolak rekomendasi.
15. Setelah perbaikan diterapkan, regression runner mengirim ulang pertanyaan yang
   sama dan membandingkan hasil baru dengan bukti yang sudah diverifikasi.

## Persiapan

Install dependency worker:

```powershell
pip install -r requirements-eval.txt
```

Isi `config/evaluation_documents.yaml` dengan path PDF asli dan nilai `chunk_source`
yang sama dengan kolom `source` pada `child_documents`. Setelah migration database
dijalankan, aktifkan API evaluasi:

```dotenv
EVALUATION_AGENT_ENABLED=true
EVALUATION_MODEL=gpt-4o-mini
EVALUATION_PAGE_WINDOW=3
EVALUATION_CANDIDATE_WINDOWS_PER_CASE=8
EVALUATION_CONTEXT_TURNS=3
```

`EVALUATION_CANDIDATE_WINDOWS_PER_CASE` membatasi halaman kandidat yang dikirim
ke LLM untuk setiap kasus. `EVALUATION_CONTEXT_TURNS` menentukan banyaknya turn
sebelumnya yang dipakai untuk memahami pertanyaan lanjutan. Perubahan mekanisme
pencarian bukti ini menggunakan tabel yang sudah ada dan tidak memerlukan migration
database tambahan.

Daftarkan dan validasi dokumen:

```powershell
python -m scripts.register_evaluation_documents
```

Jalankan batch yang dibuat dashboard:

```powershell
python -m scripts.run_failure_evaluation --run-id <RUN_ID>
```

Worker juga dapat langsung membuat dan menjalankan batch seluruh kasus gagal:

```powershell
python -m scripts.run_failure_evaluation
```

Batasi ke kasus tertentu dengan mengulang argumen berikut:

```powershell
python -m scripts.run_failure_evaluation --case-id <CASE_ID_1> --case-id <CASE_ID_2>
```

Setelah perbaikan diterapkan, jalankan regression test:

```powershell
python -m scripts.run_regression_evaluation --run-id <RUN_ID>
```

Laporan lokal disimpan di `results/evaluations/<RUN_ID>/report.json` dan
`report.md`. Temuan, bukti, rekomendasi, dan hasil regression juga disimpan di
database agar dapat ditampilkan di dashboard.

## Migration evaluasi

Migration membuat registry dokumen asli, penyimpanan trace pipeline, evaluation
case, batch run, evidence, finding, recommendation, dan regression result. Migration
juga menambahkan referensi versi sumber serta metadata versi chunking ke tabel
parent dan child yang sudah ada.

Migration tidak menghapus tabel, dokumen, chunk, maupun data percakapan. Foreign
key memakai `ON DELETE CASCADE` hanya untuk menjaga konsistensi jika suatu evaluation
run atau source document kelak sengaja dihapus. Policy RLS dibuat hanya bila belum
ada dan akses tabel evaluator dibatasi ke `service_role`.

Sebelum membuat unique index pada `request_metrics.request_id`, migration memeriksa
ID historis yang duplikat. Baris pertama tetap memakai ID lama dan baris duplikat
berikutnya memperoleh UUID baru. Tidak ada row metrics yang dihapus. Langkah ini
diperlukan karena satu trace harus menunjuk tepat ke satu request.

Migration `2026092101_evaluation_soft_failures.sql` menambahkan `queue_reason`
pada `evaluation_cases`. Nilainya membedakan kasus yang ditambahkan oleh admin,
retrieval error, kandidat yang seluruhnya ditolak, tidak adanya dokumen relevan,
dan jawaban abstain. Migration ini tidak mengubah chat, chunk, atau embedding.
