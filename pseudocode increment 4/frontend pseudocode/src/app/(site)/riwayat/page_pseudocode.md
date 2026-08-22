ALGORITMA HALAMAN RIWAYAT

1. INISIALISASI
   - Panggil GET `NEXT_PUBLIC_API_BASE_URL/api/sessions` untuk mendapatkan histori seluruh percakapan pengguna (mengembalikan daftar sesi beserta timestamp dan preview pesan pertama).

2. RENDER TAMPILAN
   - Kelompokkan hasil respon API berdasarkan tanggal ("Hari ini", "Kemarin", "Minggu lalu").
   - Tampilkan daftar percakapan sebelumnya.
   - Ketika item di-klik, panggil GET `NEXT_PUBLIC_API_BASE_URL/api/sessions/{id}` dan set hasilnya ke global state `messages` dan `session_id`, lalu pindah ke halaman `/chat`.
