# Backend chatbot akademik RAG

Backend FastAPI untuk chatbot pedoman PI, KKP, Skripsi, dan Non-Skripsi.
Fitur utama meliputi pencarian hybrid, reranking, memory dengan summary LLM,
session persisten, autentikasi, monitoring, pengelolaan chunk, dan evaluation agent.

Penjelasan program yang sudah disesuaikan dengan kode saat ini:
**[Panduan program saat ini](docs/PROGRAM_SAAT_INI.md)**.

## Menjalankan server

Dari folder `backend`, gunakan virtual environment yang sudah tersedia dan
pastikan konfigurasi `.env` terisi. Template konfigurasi ada di `.env.example`.

```powershell
.\virtual_environment\Scripts\Activate.ps1
python main.py
```

Default server: `http://localhost:8000`. Dokumentasi API: `/docs`.
Frontend Next.js dijalankan terpisah dari folder `frontend` di project induk.

Untuk instalasi environment baru, dependency backend ada di `requirements.txt`,
dependency pengujian di `requirements-dev.txt`, dan dependency worker evaluasi
di `requirements-eval.txt`.

## Pengujian dan evaluasi

```powershell
python -m pytest -q
python main.py --cli
```

Evaluation agent menyelidiki kasus gagal menggunakan PDF asli dan trace pipeline.
Admin membuat batch; worker masih dijalankan manual, tanpa scheduler:

```powershell
python -m scripts.run_failure_evaluation --run-id <RUN_ID>
python -m scripts.run_regression_evaluation --run-id <RUN_ID>
```

Persiapan database, registrasi PDF, dan penggunaan lengkap:
[Panduan evaluation agent](docs/RAG_EVALUATION_AGENT.md).

## Navigasi project

- [Program saat ini](docs/PROGRAM_SAAT_INI.md): arsitektur, alur, konfigurasi, dan batas fitur.
- [UI frontend](docs/FRONTEND_UI.md): halaman, alur admin, dan cara menjalankannya.
- [Organisasi folder](docs/FILE_ORGANIZATION.md): lokasi kode, data, utility, dan arsip.
- [Migration database](migrations/README.md): migration bertanggal dan aturan penggunaannya.
- [Dokumentasi API](docs/API_DOCUMENTATION.md): referensi tambahan; route aktif juga dapat dilihat di `/docs`.
- [Riwayat keputusan arsitektur](ADR/): keputusan pada tahap pengembangan sebelumnya.

Dokumentasi lama disimpan di `docs/journal/`, termasuk
[README sebelumnya](docs/journal/README_LAMA.md). Dokumen historis dapat menjelaskan
alur yang sudah diganti; gunakan panduan program saat ini untuk kondisi terbaru.

Credential `.env`, virtual environment, backup database, hasil evaluasi,
dan catatan pribadi disimpan lokal serta tidak dimaksudkan untuk ikut commit.
