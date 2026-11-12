# Replay penuh GPT-6 Luna vs GPT-4o mini

## Metode

Kedua model dijalankan pada 163 pertanyaan yang sama dalam 20 sesi; setiap sesi memulai memori baru. Reranker nonaktif pada kedua replay. Pertanyaan dan urutannya identik (SHA-256 `fe4883350d36d3ccbf9af19c274aff7cd50af295f6556e8ce0f87d02d603aa71`). Runner hanya meneruskan pertanyaan ke chatbot; jawaban lama dan label penilaian tidak masuk ke prompt. Semua jawaban Luna diperiksa manual terhadap empat panduan asli dengan rubrik yang sama seperti perbandingan reranker. Lima pertanyaan ambigu dikeluarkan dari penyebut kualitas kedua model.

Replay memanggil komponen RAG langsung, bukan HTTP, autentikasi, atau penyimpanan sesi database. Setiap konfigurasi hanya dijalankan satu kali. Pertanyaan ini sudah pernah digunakan untuk pengembangan, sehingga hasilnya adalah regresi pengembangan dan **bukan evaluasi akhir independen untuk skripsi**. Kode sumber memiliki fingerprint berbeda di antara replay karena konfigurasi dan adaptor model berubah; prompt dan pemilihan reranker tetap sepadan, tetapi ini bukan eksperimen dengan seluruh kode identik.

## Hasil

| Ukuran | GPT-4o mini | GPT-6 Luna |
| --- | ---: | ---: |
| Benar | 127 | **142** |
| Sebagian benar | 15 | **6** |
| Salah | 16 | **10** |
| Ambigu | 5 | 5 |
| Benar dari 158 kasus yang dapat dinilai | 80,4% | **89,9%** |
| Median waktu per jawaban | **2,83 detik** | 3,04 detik |
| Persentil ke-95 waktu per jawaban | 6,95 detik | **4,04 detik** |
| Token input generation yang tercatat | **1.051.661** | 1.057.946 |
| Token output generation yang tercatat | 17.893 | **15.158** |
| Biaya LLM yang tercatat | US$0,1685 | **US$0,1134** |

Dalam perbandingan berpasangan, Luna lebih baik pada 23 pertanyaan, GPT-4o mini lebih baik pada 9, 126 seri, dan 5 ambigu. Biaya LLM yang tercatat turun sekitar 32,7%. Namun, penghitungan ini **belum mencakup panggilan LLM untuk reformulasi kueri**: replay mencatat metode reformulasi LLM pada 118 pertanyaan GPT-4o mini dan 119 pertanyaan Luna, tetapi penggunaan token panggilan tersebut belum masuk ke metrik biaya. Karena itu, angka US$0,1685 dan US$0,1134 bukan total tagihan API. Biaya embedding tercatat sekitar US$0,0005 pada masing-masing replay. Selisih latency dapat dipengaruhi variasi jaringan dan model; satu run tidak cukup untuk mengklaim peningkatan latency yang konsisten.

| Kelompok sesi | Jumlah pertanyaan | Benar GPT-4o mini | Benar GPT-6 Luna |
| --- | ---: | ---: | ---: |
| Skripsi | 49 (5 ambigu) | 35 | **40** |
| PI | 25 | 19 | **20** |
| KKP | 40 | 35 | **37** |
| Non-Skripsi | 41 | 31 | **38** |
| Campuran | 8 | 7 | 7 |

## Contoh yang membaik dan yang masih salah

- **S16Q02:** Luna menjawab Sinta 6 diterima dengan konversi nilai 30, sesuai Tabel 3.1 dan 3.6 Panduan Non-Skripsi. GPT-4o mini sebelumnya menolaknya.
- **S12Q02:** Luna mengambil isi BAB I *laporan* KKP (deskripsi tempat, waktu, lokasi) sesuai §4.2.1, sedangkan GPT-4o mini mengambil BAB I *buku panduan*.
- **S17Q02–03:** Luna menyatakan status *freelance* tidak diputuskan secara eksplisit dalam panduan jalur Profesional; GPT-4o mini menyatakan boleh tanpa dasar.
- **S02Q03, S06Q06, S08Q09:** Luna menolak jawaban yang sebenarnya ada: kewajiban membawa lembar bimbingan, waktu penandatanganan halaman pengesahan, dan presentasi PI 10 menit.
- **S04Q05 dan S09Q04:** Luna gagal mempertahankan fakta yang baru saja disebutnya sendiri pada pertanyaan lanjutan. Surat pengantar penelitian ditandatangani Wakil Ketua I; pakaian ujian PI menggunakan almamater.
- **S20Q07:** Kedua model keliru mengenai kewajiban menyaksikan tiga seminar: panduan PI §2.7.2 dan KKP §2.7.2 sama-sama mewajibkannya.

## Keputusan

GPT-6 Luna dipertahankan sebagai model default saat ini karena hasil pada dataset pengembangan menunjukkan lebih banyak jawaban benar dan biaya LLM yang tercatat lebih rendah. Tindak lanjut kualitas yang paling jelas adalah memperbaiki pemilihan bukti untuk pertanyaan lanjutan dan kasus penolakan yang keliru. Untuk laporan penelitian, gunakan set pengujian baru yang belum dipakai mengubah pipeline serta penilaian yang dipisahkan dari proses pengembangan.

## Artefak

- Replay GPT-4o mini: `results/chatbot_repair/replay-no-reranker-full-20260930.json`.
- Replay GPT-6 Luna: `results/chatbot_repair/replay-model-luna-full-20260930.json`.
- Penilaian manual Luna: `results/chatbot_repair/manual-luna-grades-20260930.json`.
- Perbandingan 163 kasus: `results/chatbot_repair/llm-comparison-20260930.json`.
- Skrip validasi dan perhitungan: `scripts/compare_llm_replay.py`.
