# RAG Evaluation Agent

Fitur ini membantu admin mencari penyebab jawaban chatbot yang salah atau tidak
lengkap. Evaluator menggunakan tiga sumber yang berbeda:

1. PDF asli sebagai sumber kebenaran.
2. Child chunk aktif untuk menilai hasil ekstraksi dan pemotongan dokumen.
3. Trace request untuk melihat query processing, retrieval, parent assembly,
   reranker, context akhir, dan jawaban.

Evaluator hanya membuat temuan dan rekomendasi. Perubahan chunk, konfigurasi,
prompt, dan kode tetap memerlukan keputusan manusia.

## Alur penggunaan

1. Admin membuka detail request pada halaman Monitoring.
2. Admin menilai jawaban sebagai benar, salah, tidak lengkap, atau belum pasti.
   Expected answer dan catatan bersifat opsional.
3. Kasus salah, tidak lengkap, dan belum pasti muncul di halaman Evaluasi RAG.
4. Admin memilih kasus dan membuat batch. API hanya membuat antrean dengan status
   `pending`, sehingga proses panjang tidak berjalan di dalam web server.
5. Worker dijalankan dari terminal menggunakan `run_id` yang ditampilkan dashboard.
6. Worker membaca setiap halaman PDF asli dalam window yang saling overlap,
   memeriksa semua pertanyaan per batch, lalu memverifikasi kandidat bukti dengan
   halaman di sekitarnya.
7. Bukti terverifikasi dibandingkan dengan chunk aktif. Trace request kemudian
   digunakan untuk menentukan tahap kegagalan paling awal.
8. Admin membaca temuan dan menyetujui atau menolak rekomendasi.
9. Setelah perbaikan diterapkan, regression runner mengirim ulang pertanyaan yang
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
```

Daftarkan dan validasi dokumen:

```powershell
python scripts/register_evaluation_documents.py
```

Jalankan batch yang dibuat dashboard:

```powershell
python scripts/run_failure_evaluation.py --run-id <RUN_ID>
```

Worker juga dapat langsung membuat dan menjalankan batch seluruh kasus gagal:

```powershell
python scripts/run_failure_evaluation.py
```

Batasi ke kasus tertentu dengan mengulang argumen berikut:

```powershell
python scripts/run_failure_evaluation.py --case-id <CASE_ID_1> --case-id <CASE_ID_2>
```

Setelah perbaikan diterapkan, jalankan regression test:

```powershell
python scripts/run_regression_evaluation.py --run-id <RUN_ID>
```

Laporan lokal disimpan di `results/evaluations/<RUN_ID>/report.json` dan
`report.md`. Temuan, bukti, rekomendasi, dan hasil regression juga disimpan di
database agar dapat ditampilkan di dashboard.

## Isi migration 2026091403

Migration membuat registry dokumen asli, penyimpanan trace pipeline, evaluation
case, batch run, evidence, finding, recommendation, dan regression result. Migration
juga menambahkan referensi versi sumber serta metadata versi chunking ke tabel
parent dan child yang sudah ada.

Migration tidak menghapus tabel, dokumen, chunk, maupun data percakapan. Foreign
key memakai `ON DELETE CASCADE` hanya untuk menjaga konsistensi jika suatu evaluation
run atau source document kelak sengaja dihapus. Policy RLS dibuat hanya bila belum
ada dan akses tabel evaluator dibatasi ke `service_role`.
