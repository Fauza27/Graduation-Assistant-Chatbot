# Pseudocode untuk `src/api/auth.py`

```markdown
ALGORITMA ROUTER API AUTHENTICATION (auth.py)

1. IMPOR PUSTAKA
   - FastAPI (APIRouter, Request, Depends, HTTPException, status)
   - Pydantic (BaseModel) untuk skema request.
   - Modul `verify_google_id_token` dari `src.auth.google_oauth`.
   - Modul `create_access_token`, `verify_access_token` dari `src.auth.jwt_utils`.
   - Konfigurasi aplikasi dan klien Supabase.

2. INISIALISASI
   - Buat `APIRouter` dengan prefix "/auth" dan tag "Auth".
   - Buat koneksi `supabase`.

3. DEFINISI SKEMA
   - `GoogleAuthRequest`: Memiliki atribut `id_token` berupa teks.

4. ENDPOINT POST "/google/verify"
   - Tujuan: Memverifikasi token login Google dan mengembalikan JWT lokal.
   - ALGORITMA:
     - TAHAP 1: Verifikasi Google Token
       - Panggil `verify_google_id_token(id_token)`
       - Ambil `google_sub`, `email`, `name`, `picture`.
       - Jika data tidak valid, lempar HTTP 400.
     - TAHAP 2: Upsert ke Database
       - Lakukan penyisipan atau pembaruan (upsert) ke tabel `mahasiswa_accounts` berdasarkan `google_sub`.
       - Simpan data `google_sub`, `email`, `nama`, `avatar_url`.
       - Ambil `mahasiswa_id` dari hasil upsert.
     - TAHAP 3: Buat JWT
       - Siapkan payload berisi `sub` (mahasiswa_id), `name`, `email`, dan `role` = "mahasiswa".
       - Panggil `create_access_token(payload)`.
       - KEMBALIKAN token beserta informasi profil.
     - PENANGANAN KESALAHAN:
       - Tangkap error verifikasi token (401 Unauthorized) atau error internal (500).

5. ENDPOINT GET "/me"
   - Tujuan: Mengambil data profil dari token JWT yang aktif.
   - ALGORITMA:
     - Ambil header "Authorization".
     - Jika kosong atau tidak valid (tidak diawali "Bearer "), lempar HTTP 401.
     - Pisahkan "Bearer" dan "token".
     - Panggil `verify_access_token(token)` untuk mendapatkan payload.
     - Ambil `mahasiswa_id` dari payload (sub).
     - Tarik detail profil dari tabel `mahasiswa_accounts` di Supabase.
     - KEMBALIKAN data profil. Jika gagal tarik DB, kembalikan dari payload JWT.

6. ENDPOINT POST "/logout"
   - Tujuan: Endpoint log out (frontend akan menghapus token secara lokal).
   - ALGORITMA:
     - KEMBALIKAN pesan sukses "Logout sukses".
```
