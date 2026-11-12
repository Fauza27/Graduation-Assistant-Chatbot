# Lembar Verifikasi Increment 7

Lingkungan: [ISI] · Versi kode dan migrasi: [ISI] · Tanggal: [ISI] · Pemeriksa: [ISI]

Jalankan skenario dengan dua akun mahasiswa uji, satu akun admin uji, dan pertanyaan buatan. Kasus ini melengkapi BF12 untuk peninjauan rekaman dan KS02 untuk otorisasi admin. Isikan keluaran aktual, status, dan ID bukti dari versi yang diuji.

| ID | Kebutuhan | Langkah | Hasil yang Diharapkan | Aktual / Status / Bukti |
|---|---|---|---|---|
| TEL01 | FR-TEL-01 | Buat pesan sebelum akun didaftarkan. Daftarkan satu akun, lalu kirim pesan dari kedua akun. | Hanya pesan akun terdaftar setelah pendaftaran yang muncul. Pendaftaran ulang kode/akun ditolak tanpa mengganti waktu awal. | [ISI] |
| TEL02 | FR-TEL-02 | Kirim pertanyaan dan pertanyaan lanjutan dalam satu sesi serta pesan di sesi lain. Pilih kode peserta dan periode WITA yang sesuai. Buka detail pertanyaan lanjutan. | Detail memuat pesan pendahulu dalam sesi yang sama, pertanyaan, jawaban, sumber, dan ID permintaan yang sesuai. | [ISI] |
| TEL03 | FR-TEL-02 | Simulasikan kegagalan pemrosesan pada jalur chat menggunakan data uji. | Rekaman menunjukkan status pemrosesan dan durasi yang tersedia tanpa menampilkan jawaban yang tidak diterima. | [ISI] |
| TEL04 | FR-TEL-03 | Masukkan pertanyaan buatan yang memuat nama atau email contoh. Samarkan salinan untuk ekspor, lalu tandai pesan lain sebagai latihan, pengujian, dan belum ditelaah. | Berkas hanya memuat salinan yang ditelaah dan tidak memuat ketiga kelompok pesan yang dikecualikan. Teks asli masih dapat ditelusuri oleh admin berwenang. | [ISI] |
| TEL05 | FR-TEL-04 | Gunakan lebih dari 50 pesan yang ditandai masuk penelitian. Ekspor periode yang dipilih dan cocokkan ID setiap baris dengan data asal. | Seluruh ID pada filter muncul sekali. Kolom memakai kode peserta dan sesi serta tidak menyertakan nama atau email akun. | [ISI] |
| TEL06 | FR-TEL-01 | Tarik akun peserta uji, periksa ulang daftar, lalu kirim satu pesan lagi dari akun tersebut. | Salinan penelitian peserta hilang dan tidak ada rekaman penelaahan baru setelah penarikan. | [ISI] |
| TEL07 | FR-TEL-01–04 | Akses API daftar, detail, ekspor, dan perubahan status tanpa autentikasi serta dengan akun mahasiswa. | Permintaan tanpa autentikasi dan akun tanpa peran admin ditolak. | [ISI] |

Simpan tangkapan layar dan contoh keluaran CSV buatan untuk pemeriksaan. Catat koreksi serta hasil uji ulang di bawah kasus yang gagal. Data formal peserta dikumpulkan sesudah verifikasi dan penetapan versi uji.

## Pemeriksaan Pengembangan Lokal

| Lingkungan | Pemeriksaan | Hasil |
|---|---|---|
| PostgreSQL 18 terisolasi, akun buatan | Migrasi dijalankan dua kali. Perekaman diuji untuk akun belum terdaftar, pesan sebelum pendaftaran, ID yang sama, kegagalan pemrosesan, syarat persetujuan ekspor, dan penarikan peserta. Hak akses SQL juga diperiksa. | Pemeriksaan lulus. |
| Backend dengan layanan eksternal dimock | Akses peran mahasiswa, filter dan halaman ekspor, syarat salinan telaah, serta pengiriman jawaban dan sumber ke perekam. | Suite 313 tes lulus. |
| Frontend dengan data simulasi | Tes pembentukan CSV, termasuk formula pada masukan. Browser membuka filter, konteks pertanyaan lanjutan, dan tautan sumber, menyimpan salinan telaah, serta mengunduh ekspor dari dua halaman data. | Suite 5 tes dan alur browser lulus. |

Hasil lokal ini menjadi bukti pengembangan. Kolom hasil aktual TEL01–TEL07 diisi saat alur dijalankan pada lingkungan dan akun uji yang ditetapkan.

## Uji Integrasi Sebelum Evaluasi — 6 November 2026

Migrasi 2026110601 berhasil diterapkan pada Supabase yang dipakai aplikasi. Uji integrasi memakai backend dan layanan model yang aktif, dengan dua akun sintetis. Respons identitas Google untuk kedua akun tersebut disimulasikan. Backend berhasil mendaftarkan akun, memperbarui token, membuka riwayat milik akun, dan menolak akses lintas akun serta akses mahasiswa ke penelaahan.

Pertanyaan awal dan lanjutan KKP menghasilkan jawaban dan tautan sumber. Pemeriksaan terpisah pada PI, Skripsi, dan Non-Skripsi juga menghasilkan sumber dari panduan yang sesuai. Dua permintaan KKP dicocokkan dengan jawaban, sumber, dan konteks pada dashboard berdasarkan ID permintaan. Ekspor hanya memuat salinan yang ditandai masuk penelitian. Penghapusan pendaftaran menghapus salinan penelaahan akun sintetis. Keempat PDF publik cocok dengan berkas lokal berdasarkan SHA-256.

Pada pelaksanaan awal, format sitasi “Menurut **Buku Panduan …**” belum dikenali oleh kode. Pemeriksaan ulang berhasil setelah pola pembacaan sitasi diperbaiki. Suite terbaru mencatat 314 tes backend dan 5 tes frontend lulus. Uji integrasi ini memakai pertanyaan pengembangan yang terpisah dari evaluasi utama.

Pemilik proyek juga mengonfirmasi berhasil masuk dengan akun Google melalui [halaman login lokal](http://localhost:3001/login) dan mencapai halaman chat. Konfirmasi ini melengkapi pemeriksaan kesiapan sebelum pengujian formal.
