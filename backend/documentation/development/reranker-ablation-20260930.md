# Perbandingan retrieval dengan dan tanpa reranker (30 September 2026)

Ini adalah **uji regresi pengembangan**, bukan hasil evaluasi akhir penelitian. Pertanyaan akademik di bawah sudah pernah dipakai selama pengembangan. Tidak ada jawaban acuan yang diberikan ke chatbot saat replay.

Kedua mode memakai hybrid search, parent chunk, query planning, riwayat percakapan, dan prompt yang sama. Perbedaannya hanya pemilihan serta urutan parent chunk: mode aktif memakai cross-encoder dan relative gap; mode nonaktif mempertahankan urutan hybrid. Sumber kebenaran untuk penilaian manual adalah empat dokumen asli di `extract-pdf/`.

| Kasus | Reranker aktif | Reranker nonaktif | Bukti penilaian |
| --- | --- | --- | --- |
| Syarat mengambil Skripsi | Sesuai | Sesuai | Skripsi §2.5: 138 SKS, IPK 3,25 |
| Setelah memperoleh tempat KKP | Salah tahap: berkas ujian | Sesuai: konsultasi, form usulan, BAAK | KKP §2.7.1; parent prosedur `parent-kkp-007` hilang setelah reranking |
| Susunan bab laporan KKP | Sesuai | Sesuai | KKP BAB III dan IV: BAB I–V |
| Isi BAB I laporan KKP (lanjutan sesi) | Salah: isi BAB I buku panduan | Salah: isi BAB I buku panduan | KKP §4.2.1 memuat deskripsi tempat, waktu, lokasi; masalah rujukan/generation tetap ada |
| Syarat mengambil PI | Salah tahap: ketentuan ujian/akhir | Sesuai: 100 SKS dan IPK 2,00 | PI §2.5; parent syarat akademik lebih mudah masuk konteks tanpa reranker |
| Syarat jalur Karya Ilmiah | Sesuai | Sesuai | Non-Skripsi §3.1.2 |
| Lama KKP | Sesuai | Sesuai | KKP §2.7.1: minimal 30 hari kerja atau satu bulan |
| Resep nasi goreng; prakiraan cuaca | Keduanya ditolak | Keduanya ditolak | Di luar cakupan empat panduan |

Pada tujuh pertanyaan akademik ini, mode aktif menjawab 4 sesuai dan mode nonaktif 6 sesuai. Perbandingan tersebut terlalu kecil dan terlalu dekat dengan data pengembangan untuk menyatakan akurasi umum chatbot. Kedua mode tetap gagal pada satu pertanyaan lanjutan. Pengujian lengkap pada pertanyaan baru tetap diperlukan sebelum angka kualitas dipakai dalam skripsi.

Sesudah perbandingan, instruksi untuk informasi yang benar-benar tidak ditemukan diperjelas. Kasus uang saku KKP awalnya dijawab dengan penolakan yang diikuti dugaan tentang kebijakan instansi pada **kedua** mode. Setelah perubahan prompt, mode nonaktif menjawab singkat bahwa informasi itu belum ditemukan dalam konteks panduan, tanpa dugaan. Replay ulang tujuh pertanyaan akademik dengan prompt terakhir tetap menghasilkan 6 jawaban sesuai dan 1 jawaban salah (isi BAB I laporan KKP). Dua pertanyaan di luar cakupan juga dijawab tanpa mengarang fakta dan tanpa menampilkan sumber dokumen.

Total waktu replay sembilan pertanyaan: 71,0 detik (aktif) dan 31,0 detik (nonaktif). Pemanggilan pertama mode aktif mencakup pemuatan model cross-encoder (33,6 detik, dibanding 5,8 detik). Untuk delapan pertanyaan berikutnya: 37,4 berbanding 25,2 detik. Perbandingan waktu dipengaruhi kondisi jaringan dan cache; ini bukan benchmark terisolasi. Biaya LLM tercatat sekitar US$0,0079 (aktif) dan US$0,0091 (nonaktif), karena mode nonaktif biasanya mengirim lebih banyak dokumen ke generation.

Keputusan pengembangan: `RERANKER_ENABLED=false` sebagai default. Variabel lingkungan tersebut dapat diubah menjadi `true` untuk membandingkan ulang tanpa mengganti kode. Ambang absolut reranker sebelumnya juga sudah nonaktif (`rerank_min_top_score=None`); tidak tepat menyimpulkan setiap penolakan jawaban berasal dari ambang skor. Prompt sekarang menegaskan batas empat panduan. Jawaban yang tidak mengutip dokumen tidak lagi otomatis mendapat label sumber dari kandidat retrieval yang kebetulan ditemukan.

Artefak utama: `results/chatbot_repair/reranker-ablation-on-20260930.json`, `results/chatbot_repair/reranker-ablation-off-20260930.json`, `results/chatbot_repair/reranker-final-academic-20260930.json`, dan `results/chatbot_repair/reranker-final-prompt-smoke-20260930.json`. File-file ini memuat jawaban serta trace dan tidak boleh dipakai sebagai data uji independen.
