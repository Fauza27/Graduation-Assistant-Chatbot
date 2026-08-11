# Pseudocode untuk `scripts/reset_admin_password.py`

```markdown
ALGORITMA RESET/BUAT PASSWORD ADMIN (reset_admin_password.py)

1. IMPOR PUSTAKA
   - Impor pustaka bawaan (os, sys, argparse, getpass) untuk CLI argumen dan input password.
   - Impor pustaka pihak ketiga (bcrypt) untuk hashing password.
   - Impor konfigurasi (get_settings) dan Supabase client (create_client).

2. FUNGSI hash_password(plain_password: String) -> String
   - Buat `salt` menggunakan `bcrypt.gensalt()`.
   - Lakukan hashing pada password (di-encode ke UTF-8) menggunakan `salt`.
   - Kembalikan hash dalam bentuk string (decode UTF-8).

3. FUNGSI UTAMA main()
   - INISIALISASI PARSER ARGUMEN CLI (argparse):
     - `--username` (Wajib): Username admin.
     - `--new-password` (Opsional): Password baru (jika tidak diisi akan ditanyakan secara interaktif).
     - `--full-name` (Opsional): Nama lengkap (hanya dipakai saat membuat admin baru).

   - PENGECEKAN PASSWORD:
     - JIKA argumen password kosong:
       - Minta user memasukkan password secara tersembunyi (`getpass`).
       - Minta konfirmasi password ulang.
       - JIKA kedua input tidak cocok, cetak pesan error dan HENTIKAN program.
     - JIKA panjang password kurang dari 8 karakter, cetak pesan error dan HENTIKAN program.

   - KONEKSI DATABASE:
     - Ambil pengaturan dari `get_settings()`.
     - Inisialisasi klien Supabase menggunakan `supabase_url` dan `supabase_service_key`.

   - PROSES HASHING:
     - Hash password baru menggunakan `hash_password`.

   - UPDATE / INSERT ADMIN:
     - Cari akun admin di tabel `admin_users` berdasarkan `username`.
     - JIKA admin ditemukan:
       - Update baris tersebut: ubah kolom `password_hash` menjadi nilai hash yang baru.
       - Cetak "Successfully updated password for existing admin".
     - JIKA admin TIDAK ditemukan:
       - Buat dictionary admin baru berisi: `username`, `password_hash`, dan `full_name`.
       - Masukkan (insert) data baru ke tabel `admin_users`.
       - Cetak "Successfully created new admin".

4. EKSEKUSI UTAMA (if __name__ == "__main__")
   - Panggil fungsi `main()`.
```
