ALGORITMA HALAMAN PROFIL

1. INISIALISASI
   - Lakukan GET request ke `NEXT_PUBLIC_API_BASE_URL/api/auth/me` dengan Bearer token.
   - Ambil data `avatar_url`, `nama`, dan `email` dari respons database (jangan andalkan payload JWT untuk avatar).
2. RENDER TAMPILAN
   - Tampilkan Avatar (dari URL yang didapat), Nama, dan Email.
   - Tampilkan tombol opsi "Riwayat Chat Saya", "Dokumen Panduan".
   - Tampilkan tombol "Logout".
   - Ketika tombol Logout di-klik, panggil `logout()` dari `lib/auth.ts`.
