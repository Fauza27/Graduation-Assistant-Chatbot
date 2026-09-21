# Organisasi folder backend

Diperbarui: 15 September 2026. Penjelasan perilaku program ada di
[PROGRAM_SAAT_INI.md](PROGRAM_SAAT_INI.md).

```text
backend/
├── main.py                         # Entry point server dan CLI
├── application.py                  # Factory FastAPI dan lifecycle
├── README.md                       # Navigasi dan quick start
├── config/                         # Settings, prompt/config pendukung, manifest PDF
├── src/                            # Kode aplikasi
│   ├── api/                        # Route HTTP
│   ├── auth/                       # Google, JWT, refresh token
│   ├── services/                   # Orkestrasi chat, session, cache, request guard
│   ├── retrieval/                  # Query planner, pencarian, parent, reranker
│   ├── generation/                 # Prompt, LLM, memory, summary
│   ├── monitoring/                 # Metrik dan trace
│   ├── evaluation_agent/           # Investigasi kegagalan dan regression
│   ├── evaluation/                 # Evaluasi RAGAS
│   ├── ingestion/                  # Kode ingestion yang dipertahankan
│   └── bot/                        # Integrasi bot yang dipertahankan
├── tests/                          # Suite test aktif
├── migrations/                     # Migration database bertanggal
├── scripts/                        # Worker dan utility pemeliharaan
│   ├── run_failure_evaluation.py
│   ├── run_regression_evaluation.py
│   ├── register_evaluation_documents.py
│   ├── database/                   # Utility ekspor child/parent ke CSV
│   ├── demos/                      # Demo review Word, terpisah dari runtime chatbot
│   └── *.sql                       # SQL pemeliharaan/historis, dipertahankan path-nya
├── docs/                           # Dokumentasi program
│   ├── PROGRAM_SAAT_INI.md          # Panduan utama kondisi sekarang
│   ├── FILE_ORGANIZATION.md         # Dokumen ini
│   ├── RAG_EVALUATION_AGENT.md      # Panduan fitur evaluation agent
│   ├── database/                   # Arsip dokumentasi database terdahulu
│   └── journal/                    # Dokumentasi historis dan eksperimen lama
├── ADR/                            # Riwayat keputusan arsitektur
├── extract-pdf/                     # PDF asli dan hasil ekstraksi; dipakai manifest
├── backup/                         # Data lokal yang dipertahankan
│   ├── schema_20260913_222732.sql    # Snapshot schema lama, lokasi tetap
│   ├── exports/                    # Ekspor CSV child/parent
│   └── old data/                    # Data lama pengguna
├── results/                        # Hasil eksperimen dan laporan evaluasi lokal
├── logs_eksperimen_rag/             # Log eksperimen penelitian
├── personal_docs/                  # Catatan dan percakapan pribadi
├── naskah PI/                      # Naskah pribadi
└── virtual_environment/            # Environment Python pengguna
```

Tree ini menampilkan komponen utama, bukan seluruh file. `.env`, dependency,
konfigurasi test, dan file deployment tetap berada di root backend.

## Aturan penempatan file

- Kode runtime masuk ke `src/`; entry point tetap di root.
- Utility manual masuk ke `scripts/`, dengan subfolder jika fungsinya berbeda.
- Dokumentasi fitur masuk ke `docs/`; penjelasan historis masuk ke `docs/journal/`.
- Migration bertanggal masuk ke `migrations/`. Jangan memindahkan atau menjalankan
  ulang SQL lama hanya untuk menyeragamkan nama folder.
- Ekspor database masuk ke `backup/exports/`; laporan evaluasi tetap di
  `results/evaluations/<RUN_ID>/` agar path artefak tidak berubah.
- PDF dalam manifest tetap di lokasi sekarang. Mengubah lokasinya memerlukan
  pembaruan manifest dan pemeriksaan registry sumber.
- Cache Python, pytest, dan Ruff boleh dibuat ulang serta tidak perlu disimpan di Git.

## Perapian yang dilakukan

| Sebelumnya | Sekarang |
| --- | --- |
| `export_child_documents.py` di root | `scripts/database/export_child_documents.py` |
| `export_parent_documents.py` di root | `scripts/database/export_parent_documents.py` |
| Dua CSV ekspor di root | `backup/exports/` dengan nama file yang sama |
| `demo_review.py` di root | `scripts/demos/demo_review.py` |
| `Laporan_Refaktorisasi_Arsitektur.md` di root | `docs/journal/Laporan_Refaktorisasi_Arsitektur.md` |
| `scripts/DATABASE_DOCUMENTATION.md` | `docs/database/DATABASE_DOCUMENTATION_ANTERIOR.md` |
| `percakapan.txt` di root | `personal_docs/percakapan.txt` |
| README lama | Arsip `docs/journal/README_LAMA.md`, README aktif menjadi navigasi |
| Panduan organisasi lama | Arsip `docs/journal/FILE_ORGANIZATION_LAMA.md`, panduan aktif diperbarui |

Path script yang dipindah sudah disesuaikan. Utility ekspor sekarang menulis CSV
ke `backup/exports/`, sehingga hasil baru tidak menumpuk di root.
Demo Word diarahkan ke naskah `PI_Muhammad_Fauza_REVISED.docx` yang tersedia;
naskah default dengan nama lama sudah tidak ditemukan. Dependency demo bersifat
opsional, seperti dijelaskan di `scripts/README.md`.

Cache `__pycache__`, `.pytest_cache`, `.ruff_cache`, folder `.benchmarks` kosong,
dan sisa sementara di `tmp/` dibersihkan. File preview evaluasi sementara yang
tidak dipakai kode juga dibersihkan jika tersedia. Cache dapat muncul kembali
setelah menjalankan program atau test; `.gitignore` sudah mencakupnya.

Tidak ada penghapusan dokumen asli, source code lama pengguna, naskah, backup SQL,
hasil evaluasi batch, atau virtual environment. Perubahan frontend yang sudah
ada sebelum perapian ini tidak disentuh.

## Status dokumentasi arsip

`docs/database/DATABASE_DOCUMENTATION_ANTERIOR.md` adalah catatan schema dari
tahap sebelumnya. Ia belum mencakup seluruh tabel evaluation agent yang ditambahkan
kemudian. Rujukan schema terbaru pada kode ada di `migrations/` dan repository aktif.

Link relatif dalam dokumen arsip mengikuti lokasi saat dokumen itu ditulis dan
dapat tidak berlaku setelah pengarsipan. Arsip disimpan untuk menjaga isi dan
riwayat; navigasi yang dipakai sekarang ada di README dan panduan utama.
