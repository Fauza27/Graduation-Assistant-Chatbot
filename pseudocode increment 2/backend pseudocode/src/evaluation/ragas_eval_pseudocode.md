# Pseudocode untuk `src/evaluation/ragas_eval.py`

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
