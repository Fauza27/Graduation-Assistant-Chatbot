# Perbaikan pemisahan pengembangan dan pengujian — 29 September 2026

## Status hasil sebelumnya

Angka 155 sesuai, 7 sebagian, dan 1 salah berasal dari replay 163 pertanyaan
yang telah dipakai selama pengembangan. Versi tersebut juga mengembalikan
21 respons melalui aturan jawaban siap pakai. Angka itu merupakan catatan
historis regresi pengembangan, bukan hasil uji independen dan bukan skor
versi setelah perbaikan ini.

Seluruh 163 pertanyaan lama beserta parafrasa dekat dan sesi turunannya
tetap diperlakukan sebagai data pengembangan. Menghapus aturan tidak
mengembalikan independensi dataset yang sudah digunakan untuk memperbaiki sistem.
Hasil mentah dan review lama dipertahankan agar riwayat penelitian dapat diaudit.

## Perubahan kode

- Menghapus `grounded_answers.py` dan `source_conflicts.py`, beserta jalan
  pintas yang mengembalikan jawaban tanpa generator. Menghapus catatan
  jawaban khusus yang sebelumnya ditambahkan setelah pemanggilan LLM.
- Menghapus fakta syarat kampus dari prompt. Prompt kini berisi aturan
  penggunaan bukti, cakupan, penanganan konflik, dan cara menjawab.
- Menghapus pencocokan pola soal ke nomor pasal, judul bagian tertentu,
  atau kalimat jawaban dalam pemilihan kandidat dan perluasan query.
  Retrieval tetap memakai pencarian, metadata domain, dan skor reranker.
- Mempertahankan normalisasi istilah serta konteks yang memang disebut
  pengguna. Reformulator menolak angka baru dan domain yang tidak ada
  dalam konteks percakapan. Pewarisan tahap tidak otomatis menambahkan
  kata "setelah". Tidak ada daftar pertanyaan penelitian dalam jalur chatbot.
- Membatasi filter BAB eksplisit pada pertanyaan tentang buku panduan.
  Nomor BAB laporan mahasiswa tidak boleh langsung dianggap nomor BAB
  tempat bukti disimpan di buku panduan.
- Postprocessing hanya merapikan spasi. Kalimat tidak lagi dihapus diam-diam
  berdasarkan kata seperti "biasanya" atau "tidak disebutkan".

Kamus singkatan dan alias domain tetap digunakan. Pemetaan istilah dari
korpus untuk pencarian bukan kunci jawaban. Isi jawaban akademik tetap
harus diperoleh dari dokumen yang ditemukan pada permintaan saat ini.

## Pemisahan input dan penilaian

`scripts/run_chatbot_replay.py` menyalin hanya nama sesi, indeks, dan pertanyaan
dari input. Jawaban lama, expected answer, evidence penilaian, dan label review
tidak diteruskan ke pipeline. Nama sesi hanya dipakai pada laporan, bukan prompt.
Memori dimulai kosong pada setiap sesi dan hanya berisi percakapan dari run baru.

Laporan replay memuat `evaluation_purpose=development_regression`,
`independent_test=false`, serta hash file input dan sumber/public configuration.
Hash kode tidak mencakup rahasia `.env` atau snapshot isi database; keduanya
tidak boleh dianggap tercakup oleh identitas kode tersebut.

Skrip audit historis dikunci ke hash replay yang dinilai dan menolak menimpa
review lama. Label historis tidak dapat diterapkan ke respons baru hanya
karena nomor pertanyaannya sama. Ekspor review baru tetap memiliki kolom
penilaian kosong; keberhasilan request tidak otomatis berarti jawaban benar.

## Prosedur pengujian penelitian berikutnya

1. Tetapkan kode, konfigurasi model/retrieval, dan versi dokumen sebelum uji akhir.
   Simpan commit/hash, konfigurasi tanpa rahasia, dan identitas snapshot korpus.
2. Kumpulkan sesi mahasiswa yang belum dipakai memperbaiki sistem. Pemisahan
   dilakukan per sesi, bukan memecah giliran percakapan yang sama. Parafrasa
   dekat dari soal pengembangan tidak dianggap independen.
3. Simpan pertanyaan terpisah dari rubrik, jawaban acuan, dan bukti penilaian.
   Siapkan acuan dari dokumen sebelum melihat jawaban chatbot. Dokumen panduan
   tetap tersedia untuk retrieval; itu memang sumber pengetahuan sistem RAG.
4. Jalankan pertanyaan dengan memori sesi baru. Simpan seluruh hasil, termasuk
   kegagalan, tanpa mengubah pipeline berdasarkan hasil sebagian pengujian.
5. Setelah run selesai dan hasil disimpan, lakukan penilaian terhadap acuan.
   Reviewer manusia perlu mengonfirmasi kategori benar/sebagian/salah dan
   ketidakjelasan dokumen. Pemeriksaan oleh asisten ini bukan penilai independen.
6. Jika hasil uji akhir dipakai untuk memperbaiki sistem, kumpulan tersebut
   menjadi data pengembangan untuk versi berikutnya. Pengukuran independen
   versi berikutnya membutuhkan kumpulan baru.

## Batas verifikasi

Tes otomatis memeriksa pemanggilan generator, perubahan bukti, pemisahan
jawaban acuan, memori sesi, dan tidak adanya pemilihan pasal secara khusus.
Tes dengan model tiruan hanya memeriksa aliran data, bukan akurasi LLM.
Pemeriksaan API dengan dokumen sintetis disimpan sebagai development diagnostic.
Hasilnya tidak menggantikan pengujian retrieval pada korpus asli atau pengujian
mahasiswa. Tidak ada skor akurasi baru untuk 163 pertanyaan pada versi ini.

Pada pemeriksaan API `evidence-only-smoke-v2-20260929.json`, empat dari enam
contoh sintetis mengikuti bukti atau menyatakan konteks kosong. Dua contoh
ketentuan berbeda masih bermasalah: model memilih prioritas tanpa dasar atau
menganggap proses berbeda meskipun konteks menyebut proses yang sama. Respons
dan catatan pemeriksaan disimpan lengkap di `results/chatbot_repair/`.
Kegagalan ini belum diselesaikan dan tidak ditutupi dengan jawaban pengganti.
Penghapusan hardcode tidak menjamin seluruh penalaran model benar.

Untuk mencoba versi baru melalui aplikasi, restart backend dan mulai percakapan
baru. Percakapan lama tetap menyimpan respons historis; data tersebut tidak
dihapus dari database. Perubahan ini tidak membutuhkan migrasi SQL.
