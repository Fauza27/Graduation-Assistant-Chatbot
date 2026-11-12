# Kesiapan pengujian skripsi 10 Oktober 2026

## Kesimpulan pemeriksaan

Perbaikan prapengujian telah diterapkan pada pengelolaan percakapan, batas konteks, keterlacakan permintaan, sumber jawaban, dan penyimpanan percakapan pada peramban. Setelah perubahan, 309 tes backend dan empat tes helper frontend lulus. Lint, pemeriksaan TypeScript, serta build produksi frontend juga berhasil.

Evaluasi utama belum dimulai. Pemeriksaan database aktif terhenti karena DNS tidak dapat meresolusikan hostname Supabase dari lingkungan ini (`getaddrinfo failed`, kode 11001). Penyebab pada sisi proyek atau jaringan belum diketahui. Karena itu, kelengkapan korpus aktif, penerapan migrasi, akses akun, penyimpanan metrik dan jejak, serta PDF pada penyimpanan daring belum dapat dipastikan melalui pemeriksaan langsung.

Laporan konfigurasi lokal setelah seluruh perbaikan berada di `results/readiness/20261010-final-local.json`. Arsip awal `20261010-local.json` dipertahankan. Laporan menyatakan `database.checked: false`; keberhasilan pemeriksaan lokal tidak menyatakan database telah siap.

## Lingkup dan batas pemeriksaan

Pemeriksaan membaca konfigurasi, kode jalur percakapan, retrieval, generation, memory, monitoring, autentikasi, antarmuka, serta dokumentasi pengembangan. Tes otomatis menggunakan mock untuk jawaban dan layanan luar. Pemeriksaan ini tidak menggantikan uji black-box BF01–BF18, regresi 163 kasus, evaluasi utama 120 kasus, atau SUS sebagaimana Revisi 18.

Tidak ada migrasi, ingestion, perubahan rekaman database, reset kuota, deployment, maupun pengambilan respons 120 kasus utama dalam pekerjaan ini. Pada reproduksi awal masalah memory, planner belum dimock sehingga terdapat pemanggilan model untuk pemeriksaan pengembangan; tes tersebut kemudian diperbaiki agar memakai mock. Respons pemeriksaan pengembangan tidak menjadi hasil evaluasi penelitian.

Worktree telah berisi perubahan pengguna sebelum pemeriksaan. Perubahan tersebut dipertahankan. Daftar `git diff` keseluruhan tidak boleh diperlakukan sebagai daftar perubahan yang seluruhnya dibuat pada pemeriksaan ini.

## Temuan dan perbaikan

| Temuan | Perbaikan | Bukti pemeriksaan otomatis |
| --- | --- | --- |
| ID permintaan HTTP berbeda dari ID rekaman chat; ID masukan klien juga dapat dipakai berulang. | Server membuat ID baru, menggunakannya pada collector dan respons chat, serta membuka header ID melalui CORS. | Dua permintaan dengan ID klien sama menghasilkan ID server berbeda; header, body, dan collector cocok. |
| Batas konteks dihitung menggunakan perkiraan karakter; jejak dapat mencantumkan dokumen yang tidak masuk konteks. | Konteks dibatasi menurut token pada teks akhir, termasuk label dan pembatas. Jejak ID serta daftar sumber memakai dokumen yang benar-benar dimasukkan. | Teks multibyte tidak melampaui anggaran; dokumen yang tidak terkirim tidak masuk daftar ID atau sumber. |
| Pesan pengguna dapat tertinggal dalam cache memory ketika retrieval gagal. | Pemrosesan dilakukan pada salinan memory; perubahan baru disimpan melalui jalur penyelesaian percakapan. | Memory awal tidak berubah setelah kegagalan retrieval yang dimock. |
| Kegagalan penyimpanan sesi ditelan sehingga chat dapat dilaporkan sukses meskipun riwayat tidak tersimpan. | Kegagalan penyimpanan diteruskan sebagai error layanan dengan HTTP 503. Error kepemilikan sesi tetap diteruskan untuk HTTP 403. Status HTTP kegagalan layanan dan deadline dicatat sebelum penyimpanan metrik. | Mock gagal simpan tidak menghasilkan sukses atau log interaksi sukses; memory awal tidak berubah; error kepemilikan diteruskan dan endpoint memberi HTTP 503. |
| Ringkasan kosong atau yang tidak dapat masuk anggaran dapat menghapus percakapan lama. | Penghapusan giliran lama dibatalkan jika ringkasan hasil pemadatan kosong. | Isi memory tetap tersedia ketika anggaran ringkasan tidak mencukupi. |
| Lapisan layanan memasang kembali sumber retrieval meskipun generator mengembalikan daftar sumber kosong. | Keputusan generator untuk tidak menyertakan sumber dipertahankan; fallback hanya untuk hasil lama yang tidak memiliki field sumber. | Sapaan dengan sumber kosong tetap tidak menampilkan sumber akademik. |
| Pekerjaan model yang selesai setelah timeout dapat melanjutkan penyimpanan percakapan. | Deadline atau pembatalan menandai collector; sebelum mulai menyimpan percakapan, layanan menolak hasil terlambat. Slot worker tetap ditahan hingga pekerjaan selesai. | Hasil terlambat tidak memanggil penyimpanan percakapan; deadline memasang penanda pembatalan. |
| Snapshot tidak memuat status reranker serta beberapa implementasi memory dan layanan. | Status reranker dan checksum file terkait ditambahkan pada snapshot konfigurasi publik. | Snapshot memiliki status dan checksum, tanpa kredensial. |
| Logout dan pergantian akun dapat meninggalkan percakapan akun sebelumnya pada penyimpanan peramban. | State dan penyimpanan percakapan dibersihkan saat logout, login baru, serta perubahan pemilik token. Refresh akun yang sama tetap mempertahankan sesi. | Tes frontend memeriksa pergantian akun, refresh, dan logout. |
| Sumber yang tidak dikenal membuka Skripsi secara default; nomor halaman tercetak dianggap nomor halaman PDF. | Domain eksplisit diprioritaskan, sumber tak dikenal tidak membuka dokumen, dan navigasi halaman hanya memakai `pdf_pages` yang eksplisit. Metadata `pages` tidak dipakai sebagai indeks PDF. | Tes frontend memeriksa domain, sumber tak dikenal, serta perbedaan halaman tercetak dan PDF. |

Sumber yang ditampilkan berasal dari kandidat dokumen di konteks, bukan hasil validasi otomatis bahwa setiap klaim jawaban didukung sumber tersebut. Penilaian ketepatan tetap menggunakan unsur acuan dan halaman panduan.

## Pemeriksaan yang telah selesai

- Backend: `python -m pytest -q` menghasilkan **309 passed**, dengan empat peringatan deprecation dependensi. Sebelum perubahan, suite berisi 296 tes lulus. Tiga belas tes tambahan memeriksa jalur yang belum tercakup.
- Frontend: `npm run test` menghasilkan **4 passed** untuk helper sumber dan autentikasi.
- Frontend: `npm run lint`, `npx tsc --noEmit`, dan `npm run build` berhasil.
- `git diff --check` tidak menemukan kesalahan whitespace; Git memberikan peringatan konversi LF/CRLF.
- Empat PDF pada manifest sumber tersedia secara lokal dan checksum SHA-256 dicatat.

Jumlah tes di atas adalah hasil pemeriksaan perangkat lunak. Angka tersebut tidak digunakan sebagai ketepatan jawaban chatbot ataupun capaian fungsional penelitian tanpa pelaksanaan kasus yang ditetapkan pada naskah.

## Konfigurasi efektif yang diperiksa

| Parameter | Nilai lokal |
| --- | --- |
| Model generasi | `gpt-6-luna` sesuai konfigurasi lokal |
| Model embedding | `text-embedding-3-large` |
| Dimensi embedding dalam implementasi | 2.000 |
| Top-k retrieval | 20 |
| Bobot pencarian teks dan dense | 0,3 dan 0,7 |
| Konstanta RRF dalam kode | 60 |
| Reranker | Nonaktif |
| Anggaran konteks dokumen | 12.000 token |
| Anggaran history dan ringkasan | 2.500 dan 500 token |
| Minimum giliran terbaru | 2 |
| Deadline pemrosesan | 30 detik |
| Waktu tunggu slot | 1 detik |
| Maksimum worker AI per proses | 10 |
| Kuota mahasiswa | 100 permintaan per hari per akun |
| Persistence sesi, request metrics, dan execution traces | Diaktifkan dalam konfigurasi |

Identitas model di atas merupakan nilai konfigurasi, bukan konfirmasi snapshot yang dilaporkan penyedia pada evaluasi utama. Identitas yang dilaporkan layanan perlu diarsipkan saat pengujian. Komponen reranker yang masih tersedia di kode tidak berarti digunakan pada pelaksanaan dengan konfigurasi ini.

## Pemeriksaan database sebelum evaluasi

Jalankan checker baru setelah koneksi Supabase dapat digunakan. Checker hanya membaca metadata korpus dan jumlah rekaman; tidak membaca percakapan mahasiswa atau menulis database. Pembacaan dilakukan bertahap dengan urutan kunci yang tetap.

```powershell
.\virtual_environment\Scripts\python.exe -m scripts.check_research_readiness --database --output results\readiness\20261010-with-database.json
```

Gunakan nama keluaran baru jika berkas tersebut sudah ada. Checker menolak menimpa arsip sebelumnya. Pemeriksaan tanpa `--database` hanya memeriksa sumber dan konfigurasi lokal.

Hasil metadata perlu ditinjau: distribusi empat domain, child tanpa parent yang cocok, ID child yang dirujuk parent tetapi tidak tersedia, metadata halaman/sumber yang kosong, embedding yang kosong, status embedding, serta keterbacaan tabel metrik dan jejak. Pemeriksaan metadata belum membuktikan kebenaran ekstraksi; isi bagian acuan tetap harus dicocokkan dengan PDF asli.

Setelah itu, verifikasi akses akun dan sesi, operasi dashboard, konsistensi edit/re-embedding, sumber PDF pada browser, serta penyimpanan metrik dan jejak melalui kasus fungsional yang ditetapkan. Migrasi tidak dijalankan otomatis oleh checker; kebutuhan penerapannya ditentukan dari kondisi database yang nyata.

## Persiapan pelaksanaan menurut Revisi 18

1. Selesaikan dan arsipkan instrumen sebelum melihat respons versi uji: 120 kasus, 24 sesi, lima giliran tiap sesi, unsur acuan, kategori, halaman tercetak/PDF, bagian panduan, dan kebutuhan konteks. Target kategori ialah 72 answerable, 24 informasi tidak tersedia, dan 24 ambigu; sedikitnya 60 giliran bergantung konteks.
2. Periksa kemiripan instrumen dengan data pengembangan. Regresi 163 kasus dipakai sebelum evaluasi utama. Regresi dan pemeriksaan teknis ini tidak menggantikan 120 kasus baru.
3. Jalankan BF01–BF18 dan simpan bukti hasil aktual. Akun, dokumen, dan sesi uji harus dapat dipisahkan dari data mahasiswa nyata; jangan menghapus atau mengubah data nyata untuk memudahkan pengujian.
4. Tetapkan versi sistem setelah perbaikan dan regresi selesai. Arsipkan kode beserta perubahan lokal, konfigurasi publik, versi dependensi, checksum PDF, serta kondisi perangkat, jaringan, dan cache. Hash commit saja tidak menggambarkan versi uji jika masih ada perubahan yang belum dicommit.
5. Atur kuota sebelum mengirim kasus utama. Dengan batas 100 per hari, satu akun tidak dapat menjalankan seluruh 120 kasus pada hari yang sama. Pilihan yang tidak mengubah batas layanan ialah membagi sesi utuh ke dua hari menggunakan akun khusus yang sama dan versi tetap; catat waktu serta kondisi setiap pelaksanaan. Uji fungsi dan regresi juga dapat memakai kuota. Pembagian tidak boleh memotong sesi di tengah lima giliran.
6. Simpan respons awal, status HTTP, request ID, sesi, urutan giliran, durasi, jejak, dan sumber. Diagnosis ulang memakai sesi terpisah. Jika gangguan menghentikan sesi, kasus tersisa diberi status belum dijalankan mengikuti naskah.
7. Lakukan penilaian manual menurut rubrik, lalu penilaian ulang sampel 24 kasus dan kasus meragukan sesuai rancangan. Siapkan persetujuan, tugas inti penggunaan website, formulir SUS, dan rekrutmen 30 responden. Tidak ada penilai kedua atau pengujian baru yang ditambahkan pada pemeriksaan ini.

## Hal yang perlu diperhatikan saat menafsirkan hasil

- Batas 30 detik pada server menyebabkan pemrosesan yang melampaui deadline menghasilkan error. Median/P95 respons berhasil harus dibaca bersama jumlah timeout dan error; jangan menggantikan durasi timeout dengan angka keberhasilan 30 detik.
- Penanda hasil terlambat dicek sebelum penyimpanan dimulai. Operasi model atau penulisan database yang sudah berlangsung tidak dapat dibatalkan atau dibatalkan balik hanya dengan penanda ini. Perubahan tersebut bukan transaksi terdistribusi.
- Perbaikan memory belum menjamin serialisasi dua permintaan simultan pada sesi yang sama atau konsistensi cache lintas banyak proses server. Evaluasi utama tetap dikirim berurutan sesuai naskah; kapasitas layanan serentak tidak disimpulkan dari pengujian tersebut.
- Jika layanan ringkasan gagal atau ringkasan tidak dapat dimuat, percakapan lama dipertahankan agar tidak hilang. Pada kondisi itu, jumlah token history dapat melebihi anggaran; anggaran history belum merupakan batas keras untuk seluruh kondisi kegagalan ringkasan.
- Pencarian bagian PDF dengan `#search` bergantung pada viewer. Pembukaan sumber harus diperiksa pada browser yang dipakai peserta. Pengaturan indeks halaman PDF memerlukan pemetaan nyata jika ingin navigasi tepat per halaman.
- Tes helper frontend belum merupakan pengujian antarmuka lengkap. Login, sesi, riwayat, sumber, dan dashboard masih memerlukan pemeriksaan pada layanan yang terhubung.
- Perbaikan kode belum dideploy. Lingkungan yang akan diuji harus menjalankan versi yang sudah ditetapkan dan konfigurasi yang dicatat.

## Bahan untuk Bab IV

Bagian implementasi dapat ditulis dari artefak aktual: perubahan cakupan PI/KKP menjadi empat domain, antarmuka Telegram menjadi layanan website mahasiswa beserta dashboard, alur retrieval dan generation, serta pengelolaan percakapan. Catatan perbaikan prapengujian dapat mendukung penjelasan penyempurnaan, dengan bukti kode dan tes regresi yang sesuai.

Bagian hasil fungsional, ketepatan jawaban/konteks, keberhasilan sesi, durasi backend, kegagalan teknis, dan SUS baru diisi setelah pelaksanaan. Kerangka pembahasannya mengikuti rancangan Revisi 18 dan lima rumusan masalah. Hasil dari dokumentasi eksperimen lama harus menyebut versi serta instrumennya sendiri; tidak dipindahkan sebagai hasil 120 kasus baru.

Screenshot website dan dashboard untuk Bab IV harus berasal dari aplikasi yang berjalan. Screenshot tersebut, matriks penilaian, log yang telah disamarkan, serta rekap SUS menjadi bahan pelaporan setelah tersedia. Belum ada klaim bahwa fungsi lulus evaluasi utama, latensi telah membaik dibanding PI, atau usabilitas telah mencapai target.
