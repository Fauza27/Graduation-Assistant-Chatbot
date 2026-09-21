# Analisis Parent Chunk dan Child Chunk

Tanggal audit: 16 September 2026

Status perbaikan lokal: 20 September 2026

## Status tindak lanjut

Seluruh perbaikan kode dari audit ini sudah disiapkan dan diuji secara lokal:

- reranker menilai teks child yang benar-benar ditemukan oleh hybrid search,
  termasuk memilih jendela teks yang relevan bila gabungan child terlalu panjang;
- kandidat child dengan isi identik disatukan sebelum pengambilan parent;
- chunk PI dan KKP dibangun ulang secara lossless dari hasil ekstraksi dokumen asli,
  dengan 23 parent/82 child PI dan 23 parent/84 child KKP serta ID lama tetap sama;
- filter section database diubah dari pencocokan substring menjadi prefix;
- migration menyinkronkan `metadata` dengan kolom utama dan menyediakan publikasi
  parent beserta seluruh child-nya dalam satu transaksi;
- regression test mencakup fakta yang sebelumnya hilang, konsistensi parent-child,
  input reranker, de-duplikasi kandidat, dan reproduktibilitas rebuild.

Perubahan schema dan isi chunk sudah diterapkan ke Supabase pada 20 September
2026. Migration `2026091601_chunk_quality.sql` berhasil dijalankan, lalu 46 parent
dan 166 child PI/KKP diterbitkan dengan versi `lossless-v2-20260920`. Seluruh
embedding berstatus `success` dan verifikasi pascapublikasi tidak menemukan
perbedaan content, section, metadata, atau versi.

Uji retrieval langsung juga menemukan fakta anti-plagiarisme PI pada `pi-022` dan
fakta evaluasi keberhasilan KKP pada `kkp-042`. Setelah reranking, parent yang
memuat masing-masing fakta berada pada peringkat pertama.

## Tujuan dan ruang lingkup

Audit ini membandingkan tiga lapisan data:

1. tabel `parent_documents` dan `child_documents` pada database Supabase;
2. ekspor chunk JSON yang tersedia di folder `extract-pdf`;
3. teks hasil ekstraksi dari empat dokumen panduan asli: PI, KKP, Skripsi, dan Non-Skripsi.

Audit database dilakukan secara baca-saja. Tidak ada `INSERT`, `UPDATE`, `DELETE`, atau perubahan skema yang dijalankan.

## Ringkasan hasil

Struktur data parent-child dalam kondisi sehat. Seluruh child mempunyai parent, seluruh parent mempunyai child, semua embedding tersedia, dan isi setiap child ditemukan secara utuh di dalam parent-nya.

Masalah terbesar berada pada cara chunk dipakai setelah retrieval dan pada mutu chunk PI/KKP:

1. **Reranker dapat tidak melihat child yang sebenarnya cocok.** Reranker menilai bagian awal parent maksimal 2.000 karakter. Sebanyak 104 dari 373 child berada sebagian atau seluruhnya di luar bagian yang dinilai.
2. **Chunk PI dan KKP merupakan versi ringkas dari dokumen asli.** Ringkasan tersebut mempertahankan banyak aturan utama, tetapi menghilangkan sejumlah detail yang tetap mungkin ditanyakan pengguna.
3. **Metadata section Non-Skripsi tidak konsisten.** Kolom utama `section` sudah dinormalisasi, tetapi `metadata.section` lama pada 115 child belum ikut diperbarui.
4. **Ukuran chunk antar panduan tidak seragam.** PI/KKP memiliki child yang jauh lebih pendek daripada Skripsi/Non-Skripsi. Hal ini tidak merusak data, tetapi menghasilkan karakter retrieval yang berbeda untuk tiap panduan.

## Inventaris database

| Domain | Parent | Child | Median token parent | Median token child |
|---|---:|---:|---:|---:|
| PI | 23 | 82 | 552 | 134 |
| KKP | 23 | 84 | 512 | 118 |
| Skripsi | 48 | 89 | 327 | 272 |
| Non-Skripsi | 81 | 118 | 311 | 305 |
| **Total** | **175** | **373** | — | — |

Satu parent memiliki 1 sampai 8 child, dengan median 1 dan rata-rata 2,1 child per parent.

## Integritas relasi dan isi

Semua pemeriksaan berikut menghasilkan **0 masalah**:

- orphan child atau child tanpa parent;
- parent tanpa child;
- ID child yang tercantum di parent tetapi tidak ada di tabel child;
- child yang tidak tercantum pada parent-nya;
- child yang dimiliki lebih dari satu parent;
- perbedaan domain antara parent dan child;
- content kosong;
- child tanpa informasi halaman;
- embedding kosong atau berstatus gagal;
- child yang isinya tidak ditemukan dalam content parent.

Isi dan ID pada database juga sama dengan empat ekspor JSON saat ini. Perbedaan terhadap ekspor hanya ditemukan pada normalisasi nama section Non-Skripsi.

## Temuan 1: reranker tidak selalu melihat bukti yang cocok

Hybrid search mencari **child chunk**, lalu `ParentChildFetcher` mengambil parent-nya. Akan tetapi, reranker menerima content parent dari awal dan memotong input pada 2.000 karakter. Informasi tentang child mana yang cocok memang disimpan sebagai `matched_children`, tetapi teks child tersebut belum diprioritaskan sebagai input reranker.

Hasil pengukuran:

- 53 dari 175 parent melewati batas input 2.000 karakter;
- 269 child terlihat penuh oleh reranker;
- 53 child hanya terlihat sebagian;
- 51 child tidak terlihat sama sekali;
- total child yang bukti relevannya berpotensi terpotong: **104 dari 373 (27,9%)**.

| Domain | Terlihat penuh | Sebagian | Tidak terlihat | Terdampak |
|---|---:|---:|---:|---:|
| PI | 63 | 9 | 10 | 23,2% |
| KKP | 72 | 6 | 6 | 14,3% |
| Skripsi | 55 | 16 | 18 | 38,2% |
| Non-Skripsi | 79 | 22 | 17 | 33,1% |

Contoh:

- `ptas-021`, berisi alur proposal Skripsi, baru dimulai sekitar karakter ke-5.064 pada parent;
- `ptans-026`, berisi alur proposal Non-Skripsi, baru dimulai sekitar karakter ke-6.012;
- `ptas-046`, berisi penjelasan Bab IV dan Bab V Skripsi, baru dimulai sekitar karakter ke-3.560;
- `ptans-062`, bagian ketiga dari penjelasan bagian awal laporan, baru dimulai sekitar karakter ke-3.251.

Artinya, hybrid search dapat menemukan child yang tepat, tetapi parent tersebut tetap dapat memperoleh skor reranker rendah karena bagian yang membuktikan kecocokan tidak ikut dinilai.

Perbaikan yang diterapkan membuat teks khusus untuk reranking dari:

1. judul dan section parent;
2. child yang cocok;
3. bila masih cukup, child tetangga atau potongan konteks di sekitarnya.

Parent lengkap tetap digunakan pada tahap generation. Menaikkan batas karakter saja bukan solusi utama karena cross-encoder tetap memiliki batas token dan biaya inferensi akan naik.

## Temuan 2: chunk PI dan KKP kehilangan sebagian detail sumber

Perbandingan berbasis urutan kata menunjukkan perbedaan besar antara generasi chunk:

| Domain | Kata pada sumber | Total kata parent | Cakupan 5-gram sumber | Cakupan 10-gram sumber |
|---|---:|---:|---:|---:|
| PI | 10.538 | 5.784 | 21,19% | 9,07% |
| KKP | 11.747 | 5.525 | 20,38% | 8,43% |
| Skripsi | 10.815 | 10.815 | 98,13% | 95,85% |
| Non-Skripsi | 15.052 | 16.303 | 96,22% | 91,59% |

Angka PI/KKP yang rendah tidak berarti sekitar 80% fakta pasti hilang. Banyak kalimat diubah menjadi ringkasan sehingga susunan katanya berbeda. Namun, pemeriksaan isi menemukan detail yang benar-benar tidak ada pada seluruh parent PI/KKP, antara lain:

- bukti anti-plagiarisme harus mencantumkan **persentase kemiripan dan sumber kecocokan**; chunk hanya menyimpan batas maksimal dan contoh aplikasi;
- beberapa ketentuan rinci tabel, seperti mengulang header pada halaman lanjutan;
- jumlah salinan dokumen pada formulir permohonan ujian;
- pada KKP, uraian rinci mengenai keselarasan pekerjaan dengan mata kuliah, dampak langsung dan nilai tambah bagi organisasi, serta evaluasi keberhasilan dari sisi teknis, proses kerja, dan pengalaman pribadi.

Ada pula detail yang hilang dari parent prosedur utama tetapi masih muncul di parent lampiran. Contohnya, pendaftaran ujian melalui laman KPST. Uji retrieval langsung untuk pertanyaan lokasi pendaftaran PI dan KKP masih menemukan parent lampiran administrasi yang memuat KPST. Redundansi tersebut membantu jawaban saat ini, tetapi hasilnya rapuh karena bergantung pada lampiran alih-alih bagian prosedur utama.

Akibatnya, untuk pertanyaan yang jawabannya termasuk detail yang benar-benar dihilangkan, retrieval tidak mungkin memberi bukti lengkap kepada LLM walaupun query, embedding, dan reranker bekerja sempurna. Kasus seperti ini harus diklasifikasikan sebagai masalah **extraction/chunk content**, bukan masalah query atau reranking.

Perbaikan yang diterapkan pada ekspor lokal:

1. bangun ulang parent dan child PI/KKP dari teks sumber yang setia, tanpa meringkas fakta;
2. gunakan heading sebagai batas semantik;
3. pecah bagian panjang menjadi child sekitar 250–500 token dengan sedikit overlap bila kalimat atau daftar berlanjut;
4. bentuk parent dari kelompok child yang masih membahas satu topik;
5. simpan ringkasan hanya sebagai metadata tambahan bila diperlukan, bukan sebagai pengganti teks sumber;
6. regenerasi embedding setelah content child berubah.

## Temuan 3: section Non-Skripsi tidak konsisten

Pada data Non-Skripsi, kolom `section` sudah menggunakan bentuk lengkap seperti:

- `BAB II KETENTUAN UMUM > ...`;
- `BAB III BENTUK TUGAS AKHIR NON SKRIPSI > ...`;
- `BAB V FORMAT DAN TATA CARA PENULISAN > ...`.

Namun, 115 dari 118 child masih memiliki `metadata.section` lama, misalnya hanya `2.6...`, `3.3...`, atau `5.5...`.

RPC hybrid search saat ini memfilter kolom utama `child_documents.section`, sehingga retrieval utama tetap bekerja. Ketidaksamaan ini tetap berisiko bagi endpoint lama, alat admin, ekspor, atau proses berikutnya yang membaca JSON metadata.

Perbaikannya adalah menyamakan `metadata.section` dengan kolom `section` melalui migrasi idempoten, lalu memperbarui file ekspor agar import berikutnya tidak mengembalikan nilai lama. Migrasi database belum dijalankan dalam audit ini.

## Temuan 4: granularitas dan duplikasi

Child PI/KKP mempunyai median 118–134 token, sedangkan Skripsi/Non-Skripsi sekitar 272–305 token. Tidak ada child di atas 700 token. Hanya dua child di bawah 40 token, keduanya daftar gambar yang sangat pendek.

Ada empat parent di atas 2.000 token. Yang terbesar adalah:

- `parent-non-skripsi-017`: 2.688 token;
- `parent-skripsi-012`: 2.317 token;
- `parent-non-skripsi-016`: 2.111 token;
- `parent-non-skripsi-040`: 2.058 token.

Tidak ditemukan parent duplikat atau near-duplicate. Ada 11 kelompok child yang sama persis antara PI dan KKP, terutama aturan format, daftar pustaka, dan isi surat keputusan yang memang dibagikan oleh kedua panduan. Ini bukan korupsi data, tetapi dapat mengurangi variasi kandidat bila source belum berhasil dideteksi.

Sebanyak 49 child Non-Skripsi mempunyai judul `(bagian/total)`. Pemecahan ini masih wajar, tetapi makin memperkuat kebutuhan agar reranker menilai child yang cocok dan tidak hanya awal parent.

## Urutan perbaikan

1. **Prioritas pertama — perbaiki input reranker.** Gunakan child yang cocok sebagai bukti utama untuk menilai parent.
2. **Prioritas kedua — bangun ulang chunk PI/KKP secara lossless.** Ini menutup kasus ketika jawaban memang ada di dokumen asli tetapi tidak pernah masuk ke database.
3. **Prioritas ketiga — sinkronkan metadata section Non-Skripsi.** Lakukan melalui SQL idempoten setelah isi migrasi ditinjau.
4. **Prioritas keempat — tambahkan regression test berbasis pertanyaan.** Masukkan pertanyaan untuk fakta yang saat ini hilang dan untuk child yang letaknya di akhir parent.
5. **Prioritas kelima — de-duplicate kandidat lintas sumber saat source tidak terdeteksi.** Terapkan hanya bila pengujian menunjukkan kandidat duplikat benar-benar menurunkan recall.

## Dampak terhadap komponen query

Audit live database menunjukkan bahwa filter bab harus memakai prefix yang spesifik terhadap sumber. RPC menggunakan pencocokan substring, sehingga nilai mentah `BAB II` juga cocok dengan `BAB III`. PI, KKP, dan Skripsi sekarang menggunakan delimiter, misalnya `BAB II >`, sedangkan Non-Skripsi menggunakan nama bab lengkap, misalnya `BAB II KETENTUAN UMUM`. Filter `Front Matter` tidak diterapkan ke Skripsi karena data Skripsi memakai label khusus seperti `Kata Pengantar` dan `Daftar Isi`.

Aturan self-query sudah disesuaikan dengan struktur tersebut. Ini mencegah filter yang valid dibuang untuk Non-Skripsi dan mencegah filter `Front Matter` yang tidak kompatibel mengosongkan hasil Skripsi.

## Batasan audit

- Jumlah token merupakan estimasi dengan tokenizer `cl100k_base`.
- Cakupan n-gram mengukur kemiripan tekstual, bukan kesetaraan makna.
- Audit menilai snapshot database pada tanggal yang tercantum di atas.
- Uji retrieval langsung dilakukan tanpa meminta LLM membuat jawaban, sehingga tidak memakai token generation.
