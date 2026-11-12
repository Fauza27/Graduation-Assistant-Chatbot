# Perbandingan reranker aktif dan nonaktif pada 163 pertanyaan

## Cara pengujian

Sebanyak 163 pertanyaan dalam 20 sesi lama dijalankan dua kali dengan urutan dan batas sesi yang sama. Setiap sesi memulai memori percakapan baru. Jalur pengujian memanggil komponen RAG langsung, tanpa HTTP, autentikasi, atau penulisan sesi ke database. Setiap jawaban diperiksa terhadap empat dokumen panduan asli. Kunci jawaban dan penilaian tidak diberikan kepada chatbot saat pengujian.

Status *benar* berarti jawaban utama sesuai panduan dan menjawab pertanyaan; *sebagian* berarti inti jawaban tepat tetapi ada klaim tambahan yang tidak didukung, sumber/konteks keliru, atau bagian penting kurang; *salah* berarti kebijakan/angka keliru, klaim tanpa dasar, atau menolak jawaban yang sebenarnya ada; *ambigu* berarti konteks pertanyaan tidak cukup jelas untuk membedakan konfigurasi dengan adil. Penilaian dilakukan secara manual dan dapat diaudit per pertanyaan pada `results/chatbot_repair/reranker-comparison-20260930.json`.

Kedua replay menyelesaikan 163 pertanyaan tanpa error. Berkas pertanyaannya identik (SHA-256 `fe4883350d36d3ccbf9af19c274aff7cd50af295f6556e8ce0f87d02d603aa71`). *Fingerprint* kode dua replay berbeda karena perbaikan pembacaan sitasi dilakukan di antara keduanya; perbaikan tersebut tidak mengubah prompt atau teks jawaban yang dihasilkan, tetapi perbandingan ini tetap bukan eksperimen dengan seluruh kode persis identik. Panggilan model dilakukan pada waktu berbeda sehingga variasi keluaran dan jaringan juga mungkin berpengaruh.

## Hasil

| Ukuran | Reranker aktif | Reranker nonaktif |
| --- | ---: | ---: |
| Benar | 120 | **127** |
| Sebagian benar | 16 | 15 |
| Salah | 22 | **16** |
| Ambigu | 5 | 5 |
| Benar dari 158 kasus yang dapat dinilai | 75,9% | **80,4%** |
| Median waktu per jawaban | 3,68 dtk | **2,83 dtk** |
| Persentil ke-95 waktu | **6,21 dtk** | 6,95 dtk |
| Median waktu tahap reranking | 0,84 dtk | 0 dtk |
| Token input LLM | **758.266** | 1.051.661 |
| Biaya LLM tercatat | **US$0,1245** | US$0,1685 |

Pada perbandingan pertanyaan yang sama, reranker aktif lebih baik di 6 kasus dan nonaktif lebih baik di 16 kasus; 136 seri dan 5 ambigu. Angka biaya hanya mencakup biaya LLM yang dicatat replay. Menonaktifkan reranker menaikkan token input dan biaya LLM sekitar 35% relatif terhadap konfigurasi aktif, karena lebih banyak konteks masuk ke prompt. Median jawaban nonaktif lebih cepat sekitar 0,85 detik. Persentil ke-95 tidak mengikuti median; pengaruh jaringan dan variasi generasi membuat klaim percepatan di seluruh distribusi tidak tepat.

## Contoh penyebab

- **Reranker menyingkirkan bukti yang tepat.** Pada S06Q04 (materi pendadaran Skripsi), bagian §2.6.3 berada di kandidat reranker aktif tetapi ditolak, sehingga jawaban salah menyatakan ujian hanya membahas skripsi. Tanpa reranker, bagian itu masuk konteks dan jawaban benar. Pada S07Q01, bagian syarat PI juga ditolak reranker aktif dan jawaban bergeser ke syarat setelah ujian.
- **Reranker kadang membantu.** Pada S09Q04 (almamater untuk ujian PI), reranker aktif memasukkan bagian prosedur ujian PI dan menjawab benar. Tanpa reranker, bagian tersebut tidak lolos pemilihan konteks dan chatbot menolak menjawab.
- **Masalah di luar reranker tetap ada.** Pada S12Q02 kedua mode salah mengambil BAB I *buku panduan* ketika ditanya BAB I *laporan* KKP. Panduan §4.2.1 menyebut deskripsi tempat, waktu pelaksanaan, dan lokasi. Pada S16Q02 kedua mode menolak Sinta 6, padahal Tabel 3.1 memasukkannya dan Tabel 3.6 memberi konversi nilai 30. Rencana kueri untuk pertanyaan lanjutan itu juga kehilangan konteks Non-Skripsi (`domain_detected=UNKNOWN`). Pada S20Q07 kedua mode mengatakan hanya KKP yang wajib menonton tiga seminar, padahal panduan PI §2.7.2 butir 4 dan panduan KKP §2.7.2 sama-sama mewajibkannya.
- **Klaim tanpa dasar dokumen.** Pada S14Q07 kedua mode menetapkan sendiri pihak yang menentukan tanggal mulai dan selesai KKP, sementara panduan hanya meminta waktunya dicatat dan menjelaskan konsultasi awal. Pada S17Q02 kedua mode menyatakan kerja *freelance* memenuhi jalur profesional, padahal panduan tidak memutuskan kasus itu dan meminta pekerjaan di perusahaan/instansi serta surat pengangkatan.

## Keputusan sementara

Untuk konfigurasi saat ini, `RERANKER_ENABLED=false` lebih masuk akal sebagai default: lebih banyak jawaban benar dan median respons lebih cepat pada replay ini. Default kode saat ini memang `false`. Konsekuensinya ialah token input dan biaya LLM lebih tinggi. Mengaktifkan kembali reranker lama tanpa perubahan belum didukung hasil ini. Perbaikan berikutnya sebaiknya menargetkan pemilihan bukti untuk pertanyaan lanjutan, pembedaan bab buku dan bab laporan, serta kehati-hatian saat panduan tidak menetapkan kebijakan.

Ini adalah pengujian regresi saat pengembangan, bukan pengujian akhir yang independen: 163 pertanyaan pernah digunakan untuk menemukan dan memperbaiki masalah. Hasil satu replay per konfigurasi juga belum mengukur variasi jawaban antar-run. Untuk klaim penelitian, diperlukan kumpulan pertanyaan baru atau pembagian data yang jelas serta penilaian oleh penilai lain.

## Artefak

- Jawaban lengkap reranker aktif: `results/chatbot_repair/replay-reranker-on-full-20260930.json`.
- Jawaban lengkap reranker nonaktif: `results/chatbot_repair/replay-no-reranker-full-20260930.json`.
- Rubrik dan pengecualian penilaian manual: `results/chatbot_repair/manual-reranker-grades-20260930.json`.
- Perbandingan dan penilaian 163 kasus: `results/chatbot_repair/reranker-comparison-20260930.json`.
- Skrip perhitungan yang memeriksa kecocokan pertanyaan: `scripts/compare_reranker_replay.py`.
