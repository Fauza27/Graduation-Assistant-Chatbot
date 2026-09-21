# UI frontend dan cara menggunakannya

Diperbarui: 15 September 2026.

UI mengikuti design system yang sudah ada: warna ungu, permukaan putih,
sidebar, kartu, badge status, serta tipografi project. Halaman chat, profil,
riwayat, dan knowledge base yang sudah ada dipertahankan sebagai fondasi.

## Halaman dan alur utama

| Halaman | Kegunaan |
| --- | --- |
| `/chat` | Bertanya kepada chatbot dan membuka sumber pedoman |
| `/riwayat` | Mengakses percakapan sebelumnya |
| `/profil` | Melihat profil mahasiswa |
| `/admin/login` | Login admin, terpisah dari shell dashboard |
| `/admin/dashboard` | Mengelola knowledge base |
| `/admin/dashboard/monitoring` | Memeriksa request dan menilai jawaban |
| `/admin/dashboard/evaluations` | Memilih kasus dan melihat riwayat batch |
| `/admin/dashboard/evaluations/<RUN_ID>` | Membaca progres, temuan, dan rekomendasi batch |

### 1. Menilai jawaban

Pada Monitoring, buka detail request. Form penilaian menampilkan jawaban yang
tersimpan, lalu pilihan Benar, Salah, Tidak lengkap, atau Belum pasti.
Jawaban harapan, referensi/bukti, dan catatan admin bersifat opsional.

Untuk penilaian pertama, endpoint baca kasus berdasarkan request juga
mengembalikan jawaban dari trace. Ini membantu admin memeriksa jawaban sebelum
evaluation case dibuat. Endpoint tetap memerlukan autentikasi admin dan tidak
mengirim seluruh trace. Request lama yang tidak menyimpan trace/jawaban mungkin
tidak memiliki preview jawaban.

Menandai Benar mengeluarkan kasus dari antrean. Status Salah, Tidak lengkap,
Belum pasti, dan kandidat Belum dinilai dapat masuk batch. Saat mengedit
penilaian yang sudah ada, UI menggunakan PATCH dan mempertahankan metadata bukti
yang tidak diubah.

### 2. Membuat batch

Pada Evaluasi RAG, tab Antrean kasus menyediakan pencarian, filter status,
pemilihan checkbox, dan pagination. Klik pertanyaan untuk memeriksa kasus.

Pilih kasus secara eksplisit, lalu klik Buat batch. Checkbox pada header memilih
semua kasus sesuai filter, termasuk yang berada di halaman lainnya. Jumlah
pilihan ditampilkan sebelum batch dibuat.

Dialog konfirmasi menjelaskan jumlah kasus dan penggunaan API LLM saat analisis.
Membuat batch hanya membuat antrean; analisis belum berjalan.

Setelah berhasil, UI menampilkan perintah worker yang bisa disalin dan tautan
ke halaman detail batch. Jalankan perintah itu dari terminal backend dengan
virtual environment aktif. Tidak ada scheduler atau tombol yang diam-diam
menjalankan pekerjaan LLM panjang dalam web server.

### 3. Membaca hasil dan meninjau rekomendasi

Detail batch menampilkan status, progres, dan temuan dengan alasan gagal serta
rekomendasi perbaikan. Filter membantu membatasi tampilan ke tahap kegagalan tertentu.
Jawaban lama, jawaban harapan, dan bukti tersedia melalui bagian yang dapat dibuka
jika diperlukan, sehingga laporan utama tetap ringkas.

Rekomendasi yang masih diusulkan dapat disetujui atau ditolak. Persetujuan tidak
otomatis mengubah kode/chunk. Setelah perbaikan diterapkan, bagian uji ulang
menampilkan perintah regression runner.

Antrean dan detail batch diperbarui setiap 15 detik jika ada batch menunggu/berjalan
dan tab browser terlihat. Pembaruan ini membaca status; bukan scheduler agent.

## Penyempurnaan UX lain

- Navigasi admin tersedia pada ponsel, termasuk dari knowledge base.
- Drawer menu dapat ditutup melalui tombol, backdrop, atau Escape. Fokus keyboard
  dibatasi pada menu saat dibuka; menu tersembunyi tidak menerima fokus.
- Dialog memakai elemen `dialog` native untuk pengelolaan fokus dan Escape.
- Loading, kegagalan memuat data, tombol coba kembali, dan kondisi kosong ditampilkan.
- Tombol batch tidak memilih seluruh antrean secara implisit ketika tidak ada pilihan.
- Sitasi chat memakai tombol sehingga bisa diakses dengan keyboard.
- Input chat mengikuti batas API: 3 sampai 500 karakter.
- Tombol lampiran yang belum memiliki backend dihapus dari composer.
- Indikator salin hanya muncul jika operasi clipboard berhasil.
- Respons request lama tidak ditambahkan ke percakapan baru setelah pengguna mengganti session.

## Menjalankan frontend

Jalankan backend seperti biasa dari folder `backend`:

```powershell
.\virtual_environment\Scripts\Activate.ps1
python main.py
```

Pada terminal lain, dari folder `frontend`:

```powershell
npm run dev
```

Default frontend berada di `http://localhost:3000`. Pastikan
`NEXT_PUBLIC_API_BASE_URL` mengarah ke backend yang ingin dipakai. Untuk backend
lokal, nilainya dapat berupa `http://127.0.0.1:8000`. Google client ID frontend dan
backend harus sesuai. Jika mengganti port/origin frontend, origin tersebut perlu
diizinkan oleh pengaturan CORS backend.

Perubahan UI ini tidak membutuhkan library produksi tambahan dan tidak membutuhkan
migration SQL baru. Perubahan kecil respons API preview jawaban menggunakan tabel
trace yang sudah dibuat pada migration evaluasi sebelumnya.

## Struktur kode UI

| Lokasi di frontend | Tanggung jawab |
| --- | --- |
| `src/components/evaluation/CaseReview.tsx` | Form penilaian bersama monitoring dan antrean |
| `src/components/evaluation/EvaluationUI.tsx` | Dialog, status, empty state, dan perintah worker |
| `src/components/evaluation/evaluation.module.css` | Style fitur evaluasi dan form penilaian |
| `src/lib/evaluationApi.ts` | Kontrak request ke backend |
| `src/lib/evaluationUtils.ts` | Label, tanggal, ringkasan rekomendasi, dan perintah worker |
| `src/app/admin/dashboard/evaluations/page.tsx` | Antrean, pilihan kasus, dan riwayat batch |
| `src/app/admin/dashboard/evaluations/[runId]/page.tsx` | Detail batch dan peninjauan rekomendasi |
| `src/app/admin/layout.tsx` | Shell admin dan navigasi responsif |

Request pemuatan data yang sudah tidak relevan dibatalkan dengan AbortController.
Daftar kasus, bukti, dan rekomendasi pada laporan dikelompokkan dengan Map agar
tidak memfilter seluruh daftar berulang untuk setiap temuan. Store admin diakses
dengan selector untuk mengurangi render akibat perubahan state yang tidak dipakai.

## Pengujian

Pemeriksaan mencakup TypeScript, lint file yang berubah, build Next.js, dan interaksi
Chrome desktop/ponsel. Pengujian browser memakai respons API contoh untuk
memeriksa UI tanpa menjalankan LLM atau mengubah database.

Hasil dan screenshot lokal disimpan di `backend/results/ui/`. Hasil tersebut
memverifikasi perilaku frontend dengan API contoh, bukan pengujian login asli,
hasil retrieval nyata, atau biaya/performa produksi. Kontrak preview jawaban juga
diuji pada suite test backend.

Alur program backend: [PROGRAM_SAAT_INI.md](PROGRAM_SAAT_INI.md).
Alur worker agent: [RAG_EVALUATION_AGENT.md](RAG_EVALUATION_AGENT.md).
