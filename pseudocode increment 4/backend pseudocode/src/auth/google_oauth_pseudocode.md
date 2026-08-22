# Pseudocode untuk `src/auth/google_oauth.py`

```markdown
ALGORITMA VERIFIKASI GOOGLE OAUTH (google_oauth.py)

1. IMPOR PUSTAKA
   - `id_token` dari `google.oauth2`.
   - `requests` dari `google.auth.transport`.
   - Konfigurasi untuk mendapatkan GOOGLE_CLIENT_ID.

2. FUNGSI verify_google_id_token(token_string)
   - Tujuan: Memastikan token dari Google Identity Services (Frontend) adalah sah.
   - COBA (Try):
     - Panggil `id_token.verify_oauth2_token` dengan token, request Google, dan Client ID.
     - KEMBALIKAN profil pengguna (idinfo) yang memuat sub, email, nama, dll.
   - JIKA GAGAL (ValueError):
     - Token tidak valid atau sudah kedaluwarsa.
     - Lempar pengecualian (raise ValueError) dengan pesan error spesifik.
```
