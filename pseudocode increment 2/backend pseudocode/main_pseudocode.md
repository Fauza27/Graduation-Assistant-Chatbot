# Pseudocode untuk `main.py`

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
