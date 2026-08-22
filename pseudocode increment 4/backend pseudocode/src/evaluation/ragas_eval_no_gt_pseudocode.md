# Pseudocode untuk `src/evaluation/ragas_eval_no_gt.py`

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
