# Uji ulang 163 pertanyaan tanpa reranker — 30 September 2026

Replay memakai 20 sesi dengan memori baru per sesi. Runner hanya membaca pertanyaan; jawaban acuan dan penilaian lama tidak diberikan kepada chatbot. Kode yang diuji memiliki fingerprint `099154f0a963...` dan `reranker_enabled=false`. Ini **uji regresi pengembangan**, bukan data uji independen, karena pertanyaan pernah digunakan dalam pengembangan.

## Pelaksanaan

- 163/163 pertanyaan memperoleh jawaban; tidak ada error pada hasil yang digabungkan.
- Dua proses sempat berjalan paralel. Sesi 9 pada proses pertama terhenti oleh OpenAI HTTP 429 karena batas *token per menit*, bukan saldo. Sesi 9–10 kemudian diulang utuh secara berurutan dengan memori baru. Hanya sesi utuh yang masuk ke hasil gabungan.
- Rata-rata waktu per pertanyaan 3,36 detik, median 2,83 detik, persentil ke-95 6,84 detik. Angka ini berasal dari replay lokal, bukan waktu HTTP dari browser.
- Biaya LLM yang dicatat runner sekitar US$0,1685 untuk 163 jawaban; biaya embedding tidak termasuk dalam angka ini.

## Temuan yang diperiksa terhadap dokumen asli

| Kasus | Hasil terbaru | Bukti atau penyebab |
| --- | --- | --- |
| S03Q05, batas halaman proposal Skripsi | Benar: minimal 40 halaman | Panduan Skripsi §2.6.1; sebelumnya jawaban tidak menemukan batas |
| S11Q01, langkah setelah memperoleh tempat KKP | Benar: konsultasi, form usulan, BAAK, surat pengantar | Panduan KKP §2.7.1; sebelumnya meloncat ke berkas ujian |
| S18Q05, NPWP jalur Wirausaha | Benar: harus atas nama perusahaan | Panduan Non-Skripsi §3.3.2; sebelumnya menyatakan NPWP pribadi mungkin boleh |
| S09Q03–Q05, pakaian dan durasi ujian PI | Salah: tiga jawaban menyatakan informasi tidak ditemukan | Panduan PI §2.7.3 menjelaskan pakaian pria dan ujian maksimal 60 menit. Parent prosedur ujian ada di kandidat, tetapi tidak masuk konteks akhir ketika urutannya kalah oleh lampiran dan anggaran token habis. |
| S12Q02, isi BAB I laporan KKP | Salah: menjelaskan BAB I buku panduan | Panduan KKP §4.2.1 memuat deskripsi tempat, waktu, dan lokasi. Parent bagian laporan justru tersedia dalam kandidat teratas; masalah ada pada pemilihan bukti saat generation. |
| S12Q07, surat balasan sebagai lampiran | Tidak lengkap: mengatakan tidak disebut secara eksplisit | Panduan KKP §4.3 memuat surat balasan dalam daftar contoh lampiran. Self-query salah membatasi pencarian ke BAB II, sehingga §4.3 tidak ikut terambil. |
| S04Q02 dan Q04–Q05, alur setelah sempro | Salah: menambah kewajiban perpanjangan yang tidak tertulis dan salah mengidentifikasi penerbit/penandatangan surat | Reformulasi melekat pada “seminar proposal” tanpa mengikat domain Skripsi; retrieval mencampur Skripsi dan Non-Skripsi, lalu generation memilih ketentuan yang keliru. Nama domain memang tidak disebut eksplisit dalam percakapan sesi ini. |
| S14Q07, penentu tanggal mulai/selesai KKP | Salah: menyatakan tanggal ditentukan instansi | Panduan KKP menyebut durasi minimal dan jadwal kegiatan dalam laporan, tetapi tidak menetapkan pihak yang menentukan tanggal tersebut. |

Ini contoh yang diverifikasi, **bukan audit manual lengkap atas seluruh 163 jawaban**. Karena itu, jumlah jawaban benar/salah total belum dapat dinyatakan secara bertanggung jawab. Angka 6/7 pada percobaan kecil sebelumnya terlalu optimistis untuk mewakili seluruh sesi.

## Pemeriksaan balik reranker

Sesi 9 diulang dengan reranker aktif dan kode/prompt yang sama. Pertanyaan tentang “jas atau almamater” (S09Q04) menjadi benar karena parent prosedur ujian PI dinaikkan ke konteks. Pertanyaan pakaian pria (S09Q03) dan durasi satu jam (S09Q05) tetap salah. Dengan demikian, menghidupkan kembali reranker juga tidak menyelesaikan akar masalah secara konsisten. Perlu perbaikan pemilihan potongan konteks dan pemahaman rujukan percakapan sebelum memilih konfigurasi akhir berdasarkan evaluasi yang lebih luas.

Replay juga menemukan empat jawaban di sesi 19 yang menuliskan sumber sebagai daftar setelah `Sumber:` tetapi metadata `sources` kosong. Pola sitasi daftar sudah diperbaiki pada parser dan diuji setelah replay; jawaban pada berkas replay tetap dibiarkan apa adanya untuk menjaga jejak hasil yang sebenarnya.

Artefak hasil gabungan: `results/chatbot_repair/replay-no-reranker-full-20260930.json`. Pembanding terbatas: `results/chatbot_repair/replay-reranker-on-session09-20260930.json`. Berkas gabungan menyimpan nama tiga proses asal dan catatan pemulihan HTTP 429.
