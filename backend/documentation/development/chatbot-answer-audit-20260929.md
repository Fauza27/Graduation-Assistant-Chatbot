# Audit awal isi 163 jawaban chatbot — 29 September 2026

Audit ini memeriksa seluruh respons pada replay
`results/chatbot_repair/replay-quality-full-20260929.json` terhadap empat
dokumen panduan asli di `extract-pdf/`. Setiap pertanyaan dibaca dalam urutan
sesinya. Jejak query, kandidat, dan konteks akhir diperiksa untuk kasus yang
bermasalah. Hasil per pertanyaan, alasan, pasal, dan dugaan tahap penyebab ada
di `results/chatbot_repair/review-manual-20260929.csv`. Putusan dibuat manual
oleh asisten, **bukan** oleh pemeriksa AI yang sebelumnya gagal mendeteksi
kesalahan lampiran KKP.

| Status audit awal | Jumlah | Arti |
| --- | ---: | --- |
| Tidak ditemukan masalah materi | 132 | Pokok jawaban sesuai dengan ketentuan yang diperiksa; ini bukan sertifikasi bahwa setiap kalimat sempurna. |
| Sebagian benar/bermasalah | 16 | Pokok jawaban ada, tetapi ada klaim tambahan, cakupan, kelengkapan, atau rujukan yang perlu diperbaiki. |
| Salah jelas | 14 | Jawaban inti salah, melenceng ke domain/tahap lain, atau tidak menjawab padahal aturan tersedia. |
| Belum dapat diputuskan | 1 | Bunyi panduan sendiri memerlukan penafsiran/definisi tambahan. |
| **Total** | **163** | Semua respons telah diperiksa pada tingkat isi. |

Dengan definisi ini, **setidaknya 14 jawaban salah jelas** dan **16 lagi
bermasalah meski memiliki unsur benar**. Angka 132/163 tidak layak disebut
akurasi penelitian: pertanyaan ini sudah dipakai selama pengembangan, audit
belum buta, dan belum dinilai oleh penilai kedua. Kategori bisa berubah setelah
acuan jawaban dan batas toleransi ditetapkan secara formal.

## Kasus yang salah jelas

| Kasus | Yang dijawab | Yang tertulis pada panduan | Penyebab dominan |
| --- | --- | --- | --- |
| S03Q05 | Tidak ada batas minimal halaman proposal Skripsi. | Skripsi 2.6.1: minimal **40 halaman**, dengan bagian yang tidak ikut dihitung. | Pasal sempat masuk kandidat, tetapi tidak masuk konteks akhir; model lalu menyatakan ketiadaan aturan. |
| S04Q02–Q06 | Percakapan setelah seminar proposal beralih ke PI; penerbit serta penandatangan surat penelitian juga salah/tidak dijawab. | Skripsi 2.6.1–2.6.2: masa berlaku proposal satu tahun akademik; surat penelitian diterbitkan BAAK, diparaf Pembimbing, ditandatangani Wakil Ketua I, dan penelitian dilaporkan berkala. | Domain dan tahap lanjutan tidak dipertahankan. Nama sesi "setelah sempro" tidak dikirim kepada chatbot; pertanyaan awal tanpa kata Skripsi juga ambigu, tetapi peralihan ke PI tetap tidak didukung oleh istilah sempro. |
| S04Q07–Q08 | PI tanpa instansi tidak perlu surat pengantar BAAK. | PI 2.7.1 poin 5–6 tetap menyebut penerbitan surat BAAK; pengecualian adalah **penyerahan surat ke instansi** saat tidak ada instansi. | Model mengubah pengecualian langkah penyerahan menjadi pengecualian penerbitan. |
| S06Q06 | Halaman pengesahan Skripsi ditandatangani sebelum pendadaran. | Skripsi 2.6.4 poin 4: Pembimbing dan Penguji menandatangani **setelah perbaikan naskah memenuhi syarat**. | Retrieval mengambil penjelasan bentuk halaman, bukan prosedur tahap akhir; model menebak waktunya. |
| S07Q05 | Seluruh sumber studi literatur PI harus buku/jurnal. | PI bagian daftar pustaka: minimal 15 referensi dan **80%** berasal dari buku/jurnal. | Model memperluas aturan persentase menjadi kewajiban seluruh sumber. |
| S07Q08 | Beberapa mahasiswa boleh memakai satu tempat PI bila tempatnya memadai. | Panduan PI yang diperiksa tidak memberi izin atau kuota bersama semacam itu. | Dugaan praktis dinyatakan sebagai aturan. |
| S11Q01 | Setelah memperoleh tempat KKP, mahasiswa diminta menyiapkan berkas **ujian** KKP. | KKP 2.7.1: konsultasi dan persetujuan kegiatan, form usulan, lalu surat pengantar BAAK. | Tahap awal tertukar dengan pendaftaran ujian; hasil pencarian lampiran administrasi mendominasi. |
| S12Q02 | BAB I laporan KKP diisi latar belakang dan tujuan **buku panduan**. | KKP Tabel 3.1 dan 4.2.1: BAB I laporan berisi deskripsi tempat KKP, waktu pelaksanaan, dan lokasi. | Model mencampur BAB I buku sumber dengan BAB I naskah mahasiswa. |
| S18Q05 | Panduan tidak menyebut apakah NPWP harus atas nama perusahaan; NPWP pribadi mungkin bisa. | Non-Skripsi 3.3.2 poin 4 secara eksplisit menyebut **NPWP atas nama perusahaan**. | Pasal tepat ada pada kandidat, tetapi gugur dari konteks akhir; model tetap memberi dugaan. |

S04 menyumbang tujuh dari 14 kasus salah jelas. Ini menunjukkan satu kesalahan
penetapan domain dapat merusak beberapa giliran berikutnya. Penilaian S04
memakai maksud sesi uji sebagai alur setelah seminar proposal Skripsi;
chatbot hanya menerima isi pesan, sehingga untuk pengujian yang benar-benar
mandiri domain awal harus disebutkan oleh mahasiswa atau chatbot meminta
klarifikasi sebelum memberi aturan khusus.

## Jawaban sebagian benar dan kasus ambigu

Daftar lengkap 16 kasus sebagian benar ada di CSV. Pola utamanya:

- **Aturan contoh dijadikan kewajiban:** S12Q07–Q08 menyatakan lampiran KKP
  "harus/wajib", padahal bagian akhir menggunakan "antara lain"; Q08 juga
  menambah contoh foto/laporan harian pada daftar tersebut.
- **Cakupan tahapan tidak dibedakan:** S13Q01 tidak tegas memisahkan syarat
  hadir tiga seminar sebelum **pelaksanaan** seminar KKP dari pertanyaan
  tentang sebelum **pendaftaran**. S19Q02–Q03 menjawab jalur Profesional saja
  ketika percakapan sedang membandingkan Profesional dan Wirausaha.
- **Syarat/penjelasan tidak lengkap:** S18Q01, Q04, dan Q07 melewatkan sebagian
  syarat umum Wirausaha atau NIB saat menjelaskan legalitas. S18Q08 tidak
  menjawab dengan jelas apakah akun media sosial dapat menjadi satu-satunya
  bentuk *company profile*.
- **Klaim tambahan atau rujukan:** S01Q08 memberi langkah lanjutan yang tidak
  ditetapkan panduan; S03Q02 mencampur berkas Skripsi dan Non-Skripsi;
  S05Q06 mengutip Non-Skripsi dalam sesi Skripsi walau kedua panduan memuat
  aturan video yang sama; S07Q07, S09Q01, S11Q07, dan S04Q09 memerlukan batas
  klaim atau jawaban yang lebih langsung.

S15Q08 ditandai **belum dapat diputuskan**. Non-Skripsi 3.1.2 poin 4 berbunyi
naskah harus "berstatus AKTIF atau DIPUBLIKASI dalam 2 tahun terakhir".
Jawaban menolak mutlak publikasi tiga tahun lalu, tetapi status "aktif" belum
didefinisikan untuk kasus itu. Diperlukan interpretasi penanggung jawab
panduan sebelum menetapkan jawaban acuan.

## Implikasi untuk perbaikan berikutnya

Prioritas pertama adalah menjaga domain dan tahap ketika pertanyaan lanjutan
tidak menyebut keduanya, serta meminta klarifikasi jika riwayat memang belum
menetapkannya. Kedua, retrieval perlu membedakan pasal prosedur dari lampiran
formulir serta "BAB I panduan" dari "BAB I laporan". Ketiga, generation harus
membedakan kewajiban, contoh, dan pengecualian langkah; ketika pasal spesifik
tidak masuk konteks akhir, jawaban tidak boleh menyatakan aturan tidak ada di
seluruh panduan. Keempat, dokumen PI dan Non-Skripsi sendiri perlu klarifikasi
untuk kasus yang disebut di atas. Audit ini belum mengubah kode chatbot atau
menjalankan pertanyaan ulang.
