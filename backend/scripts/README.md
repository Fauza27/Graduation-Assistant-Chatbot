# Worker dan utility manual

Jalankan perintah dari folder `backend` dengan virtual environment aktif.

| Kebutuhan | Perintah |
| --- | --- |
| Mendaftarkan PDF evaluation agent | `python -m scripts.register_evaluation_documents` |
| Memproses batch dari dashboard | `python -m scripts.run_failure_evaluation --run-id <RUN_ID>` |
| Menguji ulang pertanyaan setelah perbaikan | `python -m scripts.run_regression_evaluation --run-id <RUN_ID>` |
| Mengekspor kolom child | `python scripts/database/export_child_documents.py` |
| Mengekspor kolom parent | `python scripts/database/export_parent_documents.py` |
| Memeriksa rencana rebuild chunk PI/KKP | `python scripts/database/rebuild_lossless_pi_kkp_chunks.py` |
| Memeriksa rencana publikasi chunk PI/KKP | `python scripts/database/publish_lossless_pi_kkp_chunks.py` |
| Memeriksa kesiapan database PI/KKP | `python scripts/database/publish_lossless_pi_kkp_chunks.py --check-database` |
| Demo pemeriksaan naskah Word | `python scripts/demos/demo_review.py` |

Ekspor CSV masuk ke `backup/exports/`. Ini bukan backup database lengkap.
Demo Word memakai naskah lokal di `naskah PI/` dan bukan bagian chatbot aktif.
Default naskah demo adalah `PI_Muhammad_Fauza_REVISED.docx`. Demo memerlukan
dependency opsional `python-docx`, yang belum tersedia di virtual environment
saat perapian dilakukan. Jika ingin memakai demo, instal dengan
`pip install python-docx`; chatbot utama tidak memerlukan dependency ini.

`reset_admin_password.py` adalah utility administrasi akun yang tetap berada
di folder ini. Jangan menjalankannya sebagai bagian pengujian chatbot biasa.

SQL lama di folder ini dipertahankan untuk riwayat dan pemeliharaan. Migration baru
berada di [migrations/](../migrations/). Jangan menjalankan semua SQL sekaligus.

Publikasi lossless PI/KKP memerlukan migration `2026091601_chunk_quality.sql`.
Opsi `--apply` membuat ulang 166 embedding melalui OpenAI dan memperbarui Supabase,
jadi jalankan hanya setelah output rencana tanpa opsi tersebut sudah diperiksa.

Detail pipeline: [Panduan program](../docs/PROGRAM_SAAT_INI.md).
Detail batch: [Evaluation agent](../docs/RAG_EVALUATION_AGENT.md).
