# Catatan penelitian dan uji regresi chatbot — 28 September 2026

## Tujuan dan batas pengujian

Pengujian ini memeriksa apakah chatbot dapat mempertahankan konteks percakapan,
menemukan bagian panduan yang tepat, dan membatasi jawaban pada informasi yang
didukung dokumen PI, KKP, Skripsi, serta Non-Skripsi. Sebanyak 163 pertanyaan
dalam 20 sesi lama dijalankan ulang sesuai urutannya. Pertanyaan tersebut
**pernah digunakan untuk memperbaiki sistem**, sehingga hasilnya adalah uji
regresi pada kasus yang dikenal, bukan ukuran kemampuan pada pertanyaan baru.

Replay memakai komponen retrieval dan generation nyata melalui Supabase dan
OpenAI, tetapi memori sesi dibuat lokal. Tidak ada penulisan sesi, metrik, atau
hasil evaluasi ke database. Replay tidak menguji HTTP, autentikasi, website,
Telegram, atau SUS. Agent evaluasi tidak dijalankan.

## Data dan reproduksibilitas

- Dataset dan jawaban lama: `tmp/agent-research-complete-20260921.json`.
- Putaran sebelum perbaikan terbaru: `results/chatbot_repair/replay-full-20260928.json`.
- Manifest konfigurasi dan hash kode putaran tersebut:
  `results/chatbot_repair/replay-full-20260928-manifest.json`.
- Putaran sesudah perbaikan: `results/chatbot_repair/replay-final-regression-20260928.json`.
- Manifest putaran sesudah perbaikan:
  `results/chatbot_repair/replay-final-regression-20260928-manifest.json`.
- Lembar penetapan acuan tanpa respons model:
  `results/chatbot_repair/reference-template-163-20260928.csv`.
- Lembar review dengan respons model pertama:
  `results/chatbot_repair/review-full-20260928.csv`.
- Lembar review dengan respons model sesudah perbaikan:
  `results/chatbot_repair/review-final-regression-20260928.csv`.

File hasil di atas bersifat lokal dan berada dalam direktori yang diabaikan
Git. Manifest menyimpan model, parameter efektif, versi dasar Git, dan hash
file yang memengaruhi replay tanpa menyimpan kredensial. Identitas snapshot
chunk dan dokumen panduan perlu dikaitkan dengan hasil saat menyusun Bab IV.
Konfigurasi efektif pada putaran pertama memakai `gpt-4o-mini`, embedding
`text-embedding-3-large`, cross-encoder `ms-marco-MiniLM-L-6-v2`, `top_k=20`,
delapan kandidat parent untuk rerank, lima konteks akhir, dan selisih skor
relatif 2,5. Putaran sesudahnya memakai model dan angka parameter yang sama;
perbedaannya ada pada kode pemrosesan query, pemilihan kandidat, dan jawaban
untuk konflik panduan yang diketahui.

## Hasil teknis putaran pertama

| Ukuran | Hasil |
| --- | ---: |
| Sesi dan pertanyaan | 20 sesi, 163 pertanyaan |
| Respons berhasil dibuat | 163 |
| Error API/pipeline | 0 |
| Median waktu per pertanyaan | 6,13 detik |
| Persentil ke-90 waktu per pertanyaan | 8,36 detik |
| Waktu kumulatif pertanyaan | 1.058,98 detik |
| Biaya generation yang tercatat | US$0,128023 |
| Biaya embedding yang tercatat | US$0,000462 |

Jumlah respons yang berhasil dibuat **bukan** jumlah jawaban yang benar.
Waktu ini berasal dari replay komponen secara berurutan pada satu lingkungan;
ia bukan pengukuran end-to-end melalui website atau jaringan mahasiswa.
Angka biaya berasal dari metrik generation dan embedding yang tercatat dalam
replay; biaya pemanggilan reformulator dan komponen lain tidak boleh dianggap
tercakup tanpa pengukuran tambahan. Angka ini bukan tagihan total akun API.

## Hasil teknis putaran sesudah perbaikan

| Ukuran | Hasil |
| --- | ---: |
| Sesi dan pertanyaan | 20 sesi, 163 pertanyaan |
| Respons berhasil dibuat | 163 |
| Error API/pipeline | 0 |
| Median waktu per pertanyaan | 6,02 detik |
| Persentil ke-90 waktu per pertanyaan | 7,83 detik |
| Waktu kumulatif pertanyaan | 1.030,12 detik |
| Biaya generation yang tercatat | US$0,126001 |
| Biaya embedding yang tercatat | US$0,000477 |

Perbedaan waktu dan biaya dua putaran bukan ukuran keberhasilan perbaikan
ketepatan. Jumlah jawaban yang benar baru dapat dihitung sesudah penetapan
acuan dan penilaian isi. Kedua putaran memakai pertanyaan yang pernah digunakan
selama pengembangan, sehingga tidak boleh disebut pengujian independen.

## Temuan dari pemeriksaan isi terarah

| Kasus | Bukti dokumen dan penyebab | Tindakan |
| --- | --- | --- |
| S02Q06, topik Skripsi tidak dapat dilanjutkan | Panduan Skripsi §2.4.3 poin 6 menyebut permohonan judul baru kepada Ketua Program Studi. Reformulasi awal kehilangan domain, kemudian kandidat bagian ini juga kalah sebelum rerank karena berada di luar delapan parent pertama. | Domain percakapan dipertahankan, query alternatif memakai istilah panduan, dan bagian mahasiswa bimbingan diprioritaskan untuk maksud ini. Replay terarah kemudian mengambil `parent-skripsi-009` dan menjawab sesuai pasal. |
| S07Q01, syarat mengambil PI | Panduan PI bagian syarat dan ketentuan menyebut 100 SKS dan IPK 2,00. Pertanyaan umum tentang “syarat” semula dijawab memakai syarat kelulusan ujian PI; parent persyaratan masuk pencarian tetapi gugur akibat reranking. | Untuk maksud mengambil mata kuliah, kandidat syarat pengambilan dipisahkan dari syarat ujian/kelulusan. Replay terarah menjawab 100 SKS dan IPK 2,00. |
| S11Q06, laporan kepada dosen saat KKP | Panduan KKP §2.4.2 poin 3 menyebut total delapan pertemuan yang terbagi dua saat pelaksanaan dan enam saat laporan. §2.7.2 poin 1(3) menyebut delapan laporan selama pelaksanaan. Kedua pasal tidak selaras. | Ketika kedua pasal masuk konteks, jawaban penjaga menyebut keduanya tanpa memilih satu angka. Perbedaan dalam dokumen tetap memerlukan klarifikasi dari pengelola panduan. |
| S20Q05–Q06, “yang mana tadi” | Penulis ulang pertanyaan semula memilih Skripsi saja, walaupun pengguna baru membandingkan PI, KKP, dan Skripsi. | Domain yang disebut pengguna dalam percakapan terbaru dipertahankan untuk pertanyaan pemilihan; replay terarah menjawab PI sebagai jalur tanpa instansi dan KKP sebagai jalur dengan pembimbing lapangan. |
| S20Q07, tiga seminar PI dan KKP | Panduan PI bagian tahap pelaksanaan dan Panduan KKP §2.7.2 sama-sama menyebut minimal tiga kali hadir pada seminar laporan. Kedua parent relevan semula kalah oleh bagian prosedur ujian. | Query pencarian dibuat per domain dan kandidat tahap penyusunan diprioritaskan. Replay terarah kemudian menemukan kedua aturan. |

## Pertanyaan baru dan perbaikan susulan (29 September 2026)

Delapan pertanyaan baru dalam empat sesi dibuat setelah putaran 163 kasus.
Acuan dan pasal pendukungnya ditulis sebelum hasil chatbot dilihat di
`results/chatbot_repair/holdout-reference-20260928.json`; manifest menyimpan
hash acuan dan pertanyaan. Replay pertama tersimpan di
`results/chatbot_repair/replay-holdout-20260929.json`.
Seluruh delapan respons dibuat tanpa error teknis. Enam respons memenuhi unsur
inti acuan. Dua respons tentang usia publikasi jalur Karya Ilmiah salah:
chatbot menyatakan batas waktu tidak ada, padahal Panduan Non-Skripsi §3.1.2
poin 4 menyebut naskah aktif atau dipublikasikan dalam dua tahun terakhir.

Jejak retrieval menunjukkan `parent-non-skripsi-021` sudah masuk kandidat
rerank, tetapi kalah oleh bagian sistematika proposal dan tidak masuk konteks
jawaban. Untuk pertanyaan tentang usia publikasi, query kini ditambah istilah
"ketentuan karya ilmiah" dan parent ketentuan diprioritaskan jika tersedia.
Replay susulan **hanya untuk dua pertanyaan tersebut** ada di
`results/chatbot_repair/replay-holdout-s24-repair-20260929.json`.
Keduanya kini mengambil `parent-non-skripsi-021`: artikel 18 bulan dinyatakan
masih dalam batas waktu, sedangkan dua tahun satu bulan melewatinya.

Enam dari delapan adalah hasil pemeriksaan awal terhadap acuan yang ditulis
sebelum replay. Hasil susulan dua dari dua adalah **uji perbaikan kasus yang
sudah diketahui**, bukan tambahan kasus baru atau skor kemampuan umum.
Frasa "aktif atau dipublikasikan" dalam panduan juga perlu dicatat saat
menyusun jawaban acuan rinci untuk kasus yang status aktifnya tidak diketahui.

Sesi KKP tentang aturan yang tidak disebutkan panduan juga dijalankan ulang di
`results/chatbot_repair/replay-s14-grounding-20260929.json`. Pertanyaan tentang
jam kerja, bekerja dari rumah, uang saku, sakit, dan penentuan tanggal meminta
aturan yang tidak dinyatakan secara langsung. Jawaban awal beberapa kali
menambahkan saran atau ketentuan lain setelah menyatakan bahwa aturan khusus
tidak ada. Pascaproses kini mempertahankan pernyataan keterbatasan itu saja
untuk dua pola pembuka yang teramati: "tidak disebutkan" dan "tidak ada
ketentuan". Pola kedua ditambahkan setelah replay tersebut; pemeriksaan ulang
secara deterministik pada jawaban tersimpan menunjukkan kelima jawaban itu
berhenti pada pernyataan keterbatasan. Belum ada replay live sesudah penambahan
pola kedua.

**Koreksi sumber:** Panduan KKP §2.7.1 poin 9 memang menetapkan minimal
30 hari kerja atau satu bulan. Aturan itu tidak ditemukan dalam konteks yang
diambil untuk pertanyaan tentang sakit pada putaran regresi. Jadi kekeliruan
tersebut adalah klaim yang tidak didukung konteks retrieval pada respons itu,
bukan angka yang tidak ada dalam dokumen asli. Pascaproses yang lebih hati-hati
ini mengutamakan jawaban terbatas saat aturan khusus tidak ditemukan; ia dapat
menghilangkan aturan terkait yang sebenarnya relevan. Kasus seperti ini tetap
perlu dinilai manusia, bukan dihitung otomatis sebagai benar.

Ada pula masalah yang belum layak disebut selesai. Pada pertanyaan KKP tentang
kerja dari rumah, uang saku, sakit, dan tanggal pelaksanaan, jawaban beberapa
kali menyatakan aturan tidak ada tetapi masih menambahkan dugaan atau saran
yang tidak tertulis. S17Q01 menyebut pekerjaan Web Developer sebagai bukti
kelayakan jalur profesional tanpa memastikan seluruh syaratnya. S19Q02 pada
putaran akhir sudah menyebut BAB II, Daftar Pustaka, dan lampiran; jawaban ini
tetap perlu dimasukkan ke penilaian isi bersama kasus lain.
Kasus tersebut memerlukan penilaian isi dan perbaikan lanjutan yang terukur;
tes unit dan keberhasilan HTTP tidak cukup untuk menganggapnya benar.

Sesi yang diawali “sempro” tanpa menyebut Skripsi atau Non-Skripsi juga perlu
ditandai sebagai ambigu. Nama sesi pada dataset hanya alat pengelompokan dan
tidak dikirim ke chatbot. Menilai respons seolah domainnya sudah pasti akan
memberi kesimpulan yang keliru.

## Atribusi kesalahan dari jejak replay tersimpan

Pemeriksaan lanjutan dilakukan secara **offline** pada 163 respons putaran
regresi, query hasil reformulasi, kandidat parent, skor/keputusan rerank,
konteks akhir, dan dokumen panduan asli. Tidak ada pertanyaan atau API yang
dijalankan ulang dalam pemeriksaan ini. Seluruh 163 respons memiliki setidaknya
satu dokumen konteks, tetapi itu tidak berarti pasal yang dibutuhkan sudah ada.
Delapan belas respons memakai ungkapan seperti "tidak disebutkan" atau "tidak
tersedia"; sebagian tepat dan sebagian salah, sehingga frekuensi frasa itu
bukan angka kesalahan.

| Kasus yang diverifikasi | Bukti pada jejak dan panduan | Tahap penyebab utama |
| --- | --- | --- |
| S08Q09: chatbot menjawab presentasi PI 15 menit | Panduan PI bagian mekanisme ujian menyebut **10 menit** presentasi dan 50 menit tanya jawab. Child `pi-024` yang memuat aturan masuk kandidat, tetapi parent `parent-008` tersisih oleh ambang relatif reranker. Model kemudian menyatakan angka 15 menit tanpa bukti dari konteks akhir. | Pemilihan rerank, diikuti jawaban terlalu yakin. |
| S09Q03 dan S09Q05: pakaian pria dan durasi ujian PI disebut tidak ada | Panduan PI pada bagian yang sama menyebut pakaian pria serta batas **60 menit** ujian. Parent `parent-008` masuk kandidat, tetapi tersisih dari konteks akhir kedua pertanyaan. | Pemilihan rerank. |
| S12Q07–Q08: surat balasan dianggap tidak diatur sebagai lampiran, lalu daftar berkas ujian disebut sebagai lampiran laporan | Panduan KKP BAB IV bagian akhir menyebut **Surat Balasan dari Tempat Penelitian** sebagai lampiran. Parent `parent-kkp-012` tidak masuk kandidat pencarian untuk Q07. Q08 kemudian meneruskan konteks yang salah dan mengambil syarat administrasi ujian. | Pencarian dokumen dan kesinambungan konteks. |
| S04Q02: diwajibkan mengajukan perpanjangan/revisi saat proposal lewat satu tahun | Panduan menyebut masa berlaku satu tahun akademik, tetapi prosedur perpanjangan yang ditegaskan chatbot tidak tercantum pada pasal tersebut. | Penyimpulan jawaban melampaui bukti. |
| S04Q03–Q04: percakapan seminar proposal beralih ke prosedur PI | Q01–Q02 dijawab dengan Skripsi, tetapi Q03 menafsirkan "penelitian" sebagai PI dan Q04 meneruskannya. Nama sesi tidak dikirim ke chatbot; maksud awal "sempro" sendiri ambigu, sehingga ini masalah kesinambungan domain, bukan bukti tunggal bahwa satu domain pasti benar. | Penyelesaian konteks percakapan. |
| S07Q08: beberapa mahasiswa pada satu tempat PI dikatakan mungkin boleh | Panduan PI yang diperiksa tidak menyatakan izin atau batas jumlah mahasiswa per tempat. Respons bergerak dari "tidak ada ketentuan" menjadi izin bersyarat yang tidak didukung. | Penyimpulan jawaban melampaui bukti. |
| S13Q01: jawaban mencampur waktu pendaftaran dan pelaksanaan seminar | Parent `parent-kkp-007` yang memuat syarat hadir minimal tiga seminar sudah menjadi satu-satunya konteks akhir. Panduan mengaitkan syarat ini dengan pelaksanaan seminar, sedangkan mahasiswa bertanya tentang pendaftaran. Jawaban perlu membedakan dua tahap itu secara tegas. | Penyusunan jawaban dari bukti yang tersedia. |
| S17Q01: pekerjaan Web Developer dinyatakan cukup untuk kelayakan jalur Profesional | §3.2.3 menyebut Web Developer sebagai contoh pekerjaan, sedangkan §3.2.2 masih mensyaratkan produk IT yang digunakan dan dokumen evaluasi kerja. Informasi dua syarat terakhir belum diberikan mahasiswa. | Kelengkapan bukti dan kesimpulan kelayakan. |

Pola ini menunjukkan kesalahan berasal dari **lebih dari satu tahap**. Kasus
yang berhasil ditemukan dalam audit terarah tidak boleh dipakai untuk
menghitung proporsi kesalahan setiap tahap di seluruh 163 pertanyaan. Atribusi
kuantitatif memerlukan jawaban acuan, penilaian isi per pertanyaan, dan aturan
yang konsisten untuk kasus dengan lebih dari satu penyebab. Jejak juga
menunjukkan reranker menggunakan child yang cocok dan jendela teks relevan,
bukan sekadar 2.000 karakter pertama parent; batas panjang tidak terbukti
sebagai penyebab kasus PI di atas.

Koreksi audit: S02Q05 semula diduga sebagai klaim tanpa dasar. Pemeriksaan
ulang Panduan Skripsi §2.4.3 poin 5 menunjukkan Dosen Pembimbing boleh
menyempurnakan judul selama inti permasalahan tidak berubah. Poin 6 mengatur
permohonan judul baru ketika penulisan tidak dapat dilanjutkan. Karena itu,
jawaban untuk revisi kecil **tidak boleh dicatat sebagai kesalahan pasti**;
kalimat "tidak perlu ajukan ulang" merupakan penafsiran dari dua ketentuan,
bukan kutipan prosedur yang dinyatakan eksplisit.

## Penilaian isi menurut proposal

Lembar `reference-template-163-20260928.csv` menyembunyikan respons, hasil
retrieval, dan nama sesi deskriptif. Penilai dapat menetapkan domain, jenis
pertanyaan, maksud lanjutan, keterjawaban, unsur jawaban acuan, serta lokasi
bukti dari panduan sebelum melihat jawaban sistem. Sesudah itu, respons pada
lembar review dapat diklasifikasikan sebagai benar dan lengkap, sebagian
benar, salah, atau gangguan teknis sesuai rancangan proposal. Pertanyaan yang
tidak tersedia informasinya dan pertanyaan ambigu dilaporkan terpisah.

Pemeriksaan kasus dalam catatan ini bersifat eksploratif: peneliti melihat
sebagian respons sebelum membuat acuan tertulis. Karena itu, jangan mengubah
temuan di atas menjadi persentase ketepatan final atau mengaku bahwa seluruh
163 jawaban sudah dinilai secara buta. Pengujian black-box melalui aplikasi
dan SUS mahasiswa masih merupakan kegiatan yang berbeda.

## Perbaikan dan replay terarah 29 September 2026

Jejak audit di atas dipakai untuk mengubah pemilihan kandidat, parser bagian
panduan, dan reformulator. Pertanyaan tentang waktu, presentasi, atau pakaian
ujian PI/KKP memprioritaskan bagian prosedur ujian ketika bagian itu masuk
kandidat. Replay pada sesi PI kemudian mengambil `parent-008` dan menjawab
S08Q09 **10 menit**, S09Q03 ketentuan pakaian pria, serta S09Q05 **60 menit**.
Hasil terarah tersimpan di `results/chatbot_repair/replay-targeted-quality-20260929.json`.

Pertanyaan lampiran laporan KKP diberi query pencarian dengan istilah
"BAB IV bagian akhir". Replay pertama masih gagal karena *self-query* memberi
filter BAB II pada kedua query, termasuk query yang menyebut BAB IV secara
eksplisit. Parser sekarang mengutamakan BAB yang dinyatakan jelas dan tidak
memilih satu BAB bila pertanyaan membandingkan dua BAB. Replay berikutnya di
`results/chatbot_repair/replay-quality-followup-20260929.json` mengambil
`parent-kkp-012` untuk S12Q07 dan menjawab bahwa surat balasan termasuk
lampiran. S12Q08 juga mengambil parent tersebut, tetapi masih menambahkan
contoh "dokumentasi foto" ke jawaban tentang lampiran wajib. Prompt kemudian
diperjelas agar membedakan daftar "antara lain" dari daftar syarat wajib;
perubahan prompt ini belum dinilai tersendiri pada kasus tersebut.

Reformulator pernah mengubah lima pertanyaan dari replay lama menjadi kalimat
pernyataan berisi jawaban, bukan query pencarian. Hasil tanpa tanda tanya kini
ditolak; domain atau jalur yang memang pernah disebut pengguna dapat dibawa
sebagai fallback tanpa menyalin jawaban assistant. Normalisasi juga tidak lagi
menggandakan istilah `Penulisan Ilmiah (PI)` menjadi dua nama lengkap.

Untuk pertanyaan kelayakan jalur Profesional, kandidat ketentuan dan
kualifikasi dipertahankan bersama. Replay terarah S17Q01 kini menyebut bahwa
Web Developer termasuk contoh pekerjaan **dengan syarat tambahan**: bekerja
sebagai IT Profesional di perusahaan/instansi, menghasilkan produk IT yang
digunakan, serta memiliki dokumen evaluasi kerja. Ini lebih tepat daripada
menyatakan kelayakan hanya berdasarkan nama pekerjaan.

S13Q01 tetap perlu perhatian editorial: panduan mensyaratkan tiga kehadiran
seminar sebelum *melaksanakan* seminar KKP, sedangkan mahasiswa bertanya
tentang sebelum *mendaftar*. Jawaban sistem menyebut kedua tahap itu, tetapi
belum memisahkannya dengan jelas. Ini bukan bukti bahwa kewajiban tiga
seminar tidak ada. Perbedaan tahap harus masuk acuan penilaian manusia.

Putaran regresi penuh setelah perubahan ini selesai dan tersimpan di
`results/chatbot_repair/replay-quality-full-20260929.json`, dengan konfigurasi
dan hash kode pada `results/chatbot_repair/replay-quality-full-20260929-manifest.json`.
Seluruh **163 pertanyaan dalam 20 sesi** menghasilkan respons tanpa error
teknis. Median waktu respons teramati **4,57 detik**, p90 **6,04 detik**, dan
biaya generasi yang tercatat pada replay **US$0,121567**. Replay sebelumnya
tercatat median **6,02 detik**, p90 **7,83 detik**, dan biaya generasi
**US$0,126001**. Perbedaan waktu dan biaya ini bukan bukti kausal peningkatan
performa karena jaringan, cache, serta isi prompt dapat berubah antar putaran.

Pemeriksaan manual terhadap kasus sasaran pada replay penuh mengonfirmasi
S08Q09 menjawab presentasi PI **10 menit**, S09Q03 menyebut pakaian ujian pria,
S09Q05 menjawab total ujian **60 menit**, S12Q07 menemukan surat balasan di
lampiran KKP, dan S17Q01 menyatakan kelayakan Web Developer secara bersyarat.
S12Q08 masih menamai contoh lampiran sebagai daftar yang seluruhnya "wajib"
serta menambahkan contoh yang tidak tertulis pada bagian tersebut. S13Q01
masih kurang jelas membedakan syarat sebelum pendaftaran dari syarat sebelum
pelaksanaan seminar. Keduanya memerlukan penilaian dan perbaikan lanjutan;
keberhasilan teknis replay tidak sama dengan ketepatan isi.

Lembar `results/chatbot_repair/review-quality-full-20260929.csv` memuat seluruh
respons untuk dinilai manusia. Karena 163 pertanyaan ini sudah pernah dipakai
dalam pengembangan dan belum seluruhnya diberi jawaban acuan, hasil ini tidak
boleh dilaporkan sebagai skor akurasi final atau pengujian independen.

## Probe pemeriksa jawaban terpisah

Dengan izin pengguna, empat draf jawaban dan konteks akhirnya dikirim ke
`gpt-4o-mini` untuk dinilai terpisah. Hasil mentah tersimpan di
`results/chatbot_repair/verifier-probe-20260929.json`. Model menilai S08Q09
dan S17Q01 didukung konteks, S13Q01 sebagian didukung, dan S12Q08 didukung.
Pemeriksaan manual membenarkan dua penilaian positif pertama serta masalah
S13Q01, tetapi **putusan untuk S12Q08 keliru**. Teks sumber hanya menyebut
lampiran "antara lain" Surat Pengantar, Surat Balasan, dan Form Penilaian;
jawaban menyebut semuanya "wajib" serta memberi contoh foto dan laporan
harian yang tidak tertulis di bagian tersebut. Pemeriksa bahkan mengulang
klaim itu dalam jawaban sarannya. Empat contoh ini terlalu sedikit untuk
mengukur kinerja pemeriksa secara statistik, tetapi cukup menunjukkan bahwa
pemeriksa dengan model dan konteks yang sama tidak boleh dipercaya sebagai
penentu otomatis kebenaran jawaban. Probe ini tidak mengubah pipeline chatbot.
