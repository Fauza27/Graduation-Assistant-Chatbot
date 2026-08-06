# Pseudocode untuk `src/api/sessions.py`

```markdown
ALGORITMA ROUTER SESSIONS (sessions.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, Depends, HTTPException, Request)
   - Konfigurasi aplikasi dan Supabase client.
   - Modul auth `verify_access_token`.

2. INISIALISASI ROUTER
   - Buat `APIRouter` dengan prefix "/sessions" dan tag "Sessions".
   - Buat koneksi Supabase.

3. ENDPOINT GET "/"
   - Path: `/sessions`
   - Tujuan: Mengambil riwayat percakapan pengguna (dikelompokkan berdasarkan sesi).
   - ALGORITMA:
     - TAHAP 1: Otorisasi
       - Ambil header "Authorization: Bearer <token>".
       - Ekstrak token, verifikasi via `verify_access_token`.
       - Ambil `mahasiswa_id` dari payload token.
     - TAHAP 2: Query Database
       - Panggil Supabase: `SELECT session_id, last_access, turns FROM conversation_sessions WHERE mahasiswa_id = ? ORDER BY last_access DESC`.
     - TAHAP 3: Pemrosesan Data
       - Loop melalui data hasil kueri.
       - Ekstrak pertanyaan pertama (cari pesan dengan `role=="user"`) dari array `turns` sebagai "judul" sesi (potong max 40 karakter).
       - KEMBALIKAN daftar sesi berupa array JSON dengan format `[{session_id, title, last_access}]`.

4. ENDPOINT GET "/{session_id}"
   - Path: `/sessions/{session_id}`
   - Tujuan: Memuat seluruh isi pesan dari satu sesi spesifik.
   - ALGORITMA:
     - TAHAP 1: Otorisasi
       - Sama seperti di atas, dapatkan `mahasiswa_id`.
     - TAHAP 2: Query Database
       - Panggil Supabase: `SELECT turns FROM conversation_sessions WHERE session_id = ? AND mahasiswa_id = ?`.
       - Jika tidak ditemukan, kembalikan HTTP 404 (Not Found).
     - TAHAP 3: Pemrosesan Data
       - Format ulang `turns` agar sesuai dengan yang diharapkan oleh frontend (ganti nama field: `content` menjadi `text`, dan `role: "assistant"` menjadi `role: "bot"`).
       - KEMBALIKAN daftar pesan lengkap untuk ditampilkan di UI percakapan.

5. ENDPOINT DELETE "/{session_id}"
   - Path: `/sessions/{session_id}`
   - Tujuan: Menghapus sesi percakapan dari database.
   - ALGORITMA:
     - TAHAP 1: Otorisasi
       - Ambil `mahasiswa_id` dari token.
     - TAHAP 2: Query Database
       - Panggil Supabase: `DELETE FROM conversation_sessions WHERE session_id = ? AND mahasiswa_id = ?`.
       - Cek jumlah baris yang berhasil dihapus (row count).
     - TAHAP 3: Respons
       - JIKA row count == 0: Kembalikan HTTP 404 (Not Found).
       - JIKA BERHASIL: KEMBALIKAN pesan sukses.
```
