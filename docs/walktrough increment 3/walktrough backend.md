# Walkthrough: Backend Increment 3 (Admin Dashboard)

Pengembangan Backend untuk *Increment 3* (Admin Dashboard: Kelola Chunk & Autentikasi Admin) telah berhasil diselesaikan sesuai dengan rancangan *pseudocode* yang telah disetujui sebelumnya. 

Berikut adalah rangkuman dari seluruh perubahan yang telah ditambahkan ke dalam sistem:

## 1. Skrip Migrasi Database
Saya telah membuat skrip `backend/scripts/supabase_migration_admin_status.sql`.
Skrip ini bertugas menambahkan dua kolom penting:
- `embedding_status` pada `child_documents` (status default: `'success'`). Kolom ini merupakan representasi status *persisten* dari kondisi *embedding chunk* terbaru.
- `updated_at` pada `child_documents` dan `parent_documents` untuk keperluan statistik `last_updated_at` pada UI Admin.

> [!IMPORTANT]
> Anda harus menjalankan skrip ini secara manual di SQL Editor Supabase Anda sebelum menggunakan fitur Admin Dashboard.

## 2. Modul Autentikasi Admin (`src/admin/auth.py`)
Modul ini menangani:
- Hashing dan verifikasi *password* dengan menggunakan pustaka `bcrypt`.
- Autentikasi kredensial dari tabel `admin_users`.
- *Dependency* `get_current_admin` untuk FastAPI yang bertugas mengekstraksi dan memverifikasi token JWT bawaan.

## 3. Logika Pengelolaan Chunk (`src/admin/chunk_editor.py`)
Ini adalah *core service* untuk modul Admin, mencakup fungsionalitas berikut:
- Mengambil **Knowledge Tree** (Hierarki Dokumen -> Bab -> Parent -> Child) dalam sekali permintaan untuk UI *Sidebar*.
- Fitur **Simpan Perubahan** (Title, Pages, Content) secara cepat yang akan mengubah `embedding_status` menjadi `stale` ketika `content` ikut diubah.
- Fitur **Re-embed** asinkronus (menggunakan OpenAI API) yang secara otomatis akan:
  - Memperbarui vektor *embedding* pada *child chunk*.
  - Melakukan *replace* teks secara *best-effort* pada dokumen *parent* induknya, sehingga LLM akan menerima konteks teks terbaru dengan akurat.
- Fitur **Hapus Chunk** yang mengimplementasikan *housekeeping otomatis*: Menghapus dokumen *parent* yang bersangkutan apabila semua *child chunk* di dalamnya telah habis terhapus.

## 4. API Router (`src/api/admin.py`)
Seluruh jalur komunikasi dengan *Frontend* Next.js kini telah dibuka pada rute `/api/admin/*`:
- `POST /login`
- `GET /documents`
- `GET /chunks/{child_id}`
- `PUT /chunks/{child_id}`
- `POST /chunks/{child_id}/reembed`
- `DELETE /chunks/{child_id}`
- `GET /chunks/{child_id}/edit-status`

## 5. Tooling Tambahan
- **CLI Reset Password**: Saya membuatkan script `backend/scripts/reset_admin_password.py` yang bisa Anda gunakan kapan saja dari terminal (menggunakan argumen `--username` dan interaksi `getpass`) untuk membuat akun admin pertama kali atau mereset kata sandinya secara instan tanpa perlu repot menyimpan *hash* manual di Supabase.
- **Pembaruan Aplikasi**: Pustaka `bcrypt==4.1.3` telah ditambahkan ke `backend/requirements.txt`, dan *router* `/api/admin` telah diregistrasi ke `backend/application.py`.

> [!TIP]
> Jangan lupa untuk menginstal dependensi terbaru dengan menjalankan `pip install -r backend/requirements.txt` sebelum menyalakan server uvicorn Anda kembali.

Apakah Anda ingin saya melakukan uji coba pada endpoint tertentu, atau Anda akan melanjutkannya sendiri ke bagian Frontend?
