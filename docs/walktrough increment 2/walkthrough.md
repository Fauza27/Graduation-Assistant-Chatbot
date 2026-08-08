# Backend Increment 2: Autentikasi Mahasiswa & Modifikasi Chat

Semua perbaikan dan penambahan *backend* untuk menangani *Google OAuth* dan modifikasi alur *chat* sesuai Increment 2 sudah diimplementasikan!

## Fitur Utama

- **Google OAuth Login (GIS):** Sistem *backend* telah siap menerima token dari *Google Identity Services* (`id_token`) pada *endpoint* baru `POST /api/auth/google/verify`.
- **JSON Web Token (JWT):** *Backend* sekarang dapat menghasilkan token JWT (`Bearer`) yang berisi `mahasiswa_id` dan *role* yang kelak akan diverifikasi pada setiap panggilan API yang membutuhkan izin autentikasi (*chat website*).
- **Pemungutan Kuota Per Mahasiswa:** *Endpoint* `/api/ai/chat` sekarang mengidentifikasi pengguna Website melalui *token* tersebut dan melakukan pengecekan RPC harian (memanggil `increment_quota_if_under_limit` di dalam Supabase) berdasarkan `mahasiswa_id`.
- **Integrasi Log:** *Database Session Store* kini diperbarui agar memuat riwayat rekaman asalnya obrolan (*website* atau *telegram*). Selain itu, fungsi penulisan `chat_logs` kini telah digabungkan ke bagian pusat proses NLP sehingga *dashboard analytics* nanti akan tetap terisi.

## Verifikasi Mandiri

### 1. File Konfigurasi Lingkungan (`.env`)
Karena fitur-fitur ini membutuhkan konfigurasi tambahan, pastikan variabel berikut tersedia atau ditambahkan di *file* `.env` Anda (di dalam *folder* `backend/`):
```env
# JWT Settings (sudah saya berikan nilai bawaan, tapi lebih baik dikustomisasi di .env)
JWT_SECRET_KEY="super-secret-key-change-in-production"
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_MINUTES="4320"

# Google Auth (Diperlukan jika ingin tes frontend nanti)
GOOGLE_CLIENT_ID="<client-id-google-anda>"
```

### 2. Apa selanjutnya?
Karena *backend*-nya sudah rampung dan tidak ada masalah ketergantungan apa-apa lagi, Anda bisa lanjut meracik antarmuka *Website* (Frontend) atau mereviu *commit* perubahan *backend* ini. Jika Anda ingin mengetes API secara manual sebelum lanjut ke *frontend*, Anda bisa menggunakan *Swagger UI* bawaan FastAPI yang biasanya ada di rute `http://127.0.0.1:8000/docs`.
