# Perbaikan jawaban chatbot — 29 September 2026

> Catatan historis: implementasi jawaban khusus dan pemilihan pasal yang
> dijelaskan di bawah sudah dicabut. Lihat
> [perbaikan pemisahan pengembangan dan pengujian](chatbot-evaluation-integrity-20260929.md).
> Hasil replay versi ini tidak mewakili akurasi versi saat ini maupun uji independen.

## Dasar audit

Audit awal atas 163 respons dalam 20 sesi ada di
`chatbot-answer-audit-20260929.md` dan
`results/chatbot_repair/review-manual-20260929.csv`.
Audit itu menandai 14 jawaban salah jelas, 16 sebagian benar/bermasalah,
dan satu kasus yang bunyi panduannya sendiri ambigu. Semua putusan awal
dibandingkan dengan empat panduan asli di `extract-pdf/`.

## Perubahan

- Reformulasi pertanyaan lanjutan menjaga domain, jalur, tahap, dan nama
  dokumen yang disebut mahasiswa. Reformulasi yang menyisipkan jawaban
  atau mengubah pertanyaan tentang panjang proposal menjadi tahap setelah
  seminar ditolak/diperbaiki.
- Pemilihan kandidat mengutamakan pasal yang tepat untuk halaman proposal,
  surat penelitian, BAB I laporan KKP, lampiran KKP, syarat Wirausaha,
  serta tabel penilaian kedua jalur Non-Skripsi. Pertanyaan berkas ujian PI
  juga mencari pasal awal tentang penelitian tanpa instansi.
- Instruksi generasi membedakan aturan wajib, contoh, pengecualian,
  deskripsi, dan saran praktis. Beberapa klausul yang berulang kali
  disalahartikan memiliki jawaban singkat yang hanya aktif jika kutipan
  panduan terkait masuk konteks retrieval.
- Dua pasal KKP yang tidak selaras tentang frekuensi laporan saat
  pelaksanaan dijelaskan bersama; chatbot tidak memilih salah satunya
  seolah pasti. Daftar berkas ujian PI diberi catatan tentang belum
  jelasnya pengganti surat balasan/daftar wawancara untuk PI tanpa instansi.

## Verifikasi

Regresi penuh `results/chatbot_repair/replay-repair-final-163-v2-20260929.json`
menyelesaikan **163/163 pertanyaan tanpa error eksekusi**. Setelah
regresi itu, tiga jawaban yang masih kurang tepat ditemukan dari audit
isi: redaksi 80% sumber PI, konflik bimbingan KKP, dan kelengkapan
syarat Wirausaha. Ketiganya diperbaiki lalu diuji ulang pada
`results/chatbot_repair/replay-final-residual-20260929.json`
(sesi PI, KKP, Wirausaha). Reformulasi tanda tangan surat penelitian
diuji ulang pada `results/chatbot_repair/replay-final-signature-20260929.json`.
Seluruh 330 tes otomatis lulus setelah semua perbaikan, termasuk
perbaikan reformulator untuk pertanyaan tanda tangan.

Replay memakai komponen RAG sungguhan dan memori lokal baru untuk setiap
sesi. Replay ini **tidak** menguji HTTP, autentikasi, atau penyimpanan sesi
database. Jawaban LLM dapat berubah antar-run. Berkas regresi penuh dan
uji terarah sesudahnya adalah run berbeda, bukan satu dataset hasil yang
boleh digabung sebagai satu skor final.

## Batas penelitian

- Pertanyaan yang sama telah digunakan selama pengembangan. Hasilnya
  adalah regresi pengembangan, bukan pengukuran akurasi pada data uji
  independen dan bukan angka Bab IV yang siap diklaim.
- Panduan Non-Skripsi menyebut karya ilmiah berstatus “AKTIF atau
  DIPUBLIKASI dalam dua tahun terakhir”, tetapi tidak mendefinisikan
  “AKTIF” untuk publikasi tiga tahun lalu. Status akhirnya perlu
  klarifikasi program studi.
- Panduan PI mencantumkan surat balasan dan daftar wawancara pada berkas
  ujian, tetapi prosedur awal mengecualikan pengunggahan surat balasan
  bagi PI tanpa instansi. Pengganti pada tahap ujian tidak dijelaskan.
- Pertanyaan seminar proposal tanpa menyebut Skripsi atau Non-Skripsi
  tidak dapat diberi satu daftar administrasi: IPK dan panjang proposal
  keduanya berbeda. Chatbot sekarang menyampaikan perbedaannya dan
  meminta pengguna menyebut jalur.
