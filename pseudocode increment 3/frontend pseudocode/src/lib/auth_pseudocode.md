ALGORITMA OTENTIKASI & TOKEN

1. FUNGSI handleGoogleLogin(credentialResponse)
   - Terima token dari Google Identity Services (dari komponen `<GoogleLogin />`).
   - PANGGIL POST `NEXT_PUBLIC_API_BASE_URL/api/auth/google/verify` ke backend dengan body `{ id_token: credentialResponse.credential }`.
   - JIKA sukses:
     - Simpan `access_token` ke dalam `localStorage.setItem('access_token', token)`.
     - Arahkan pengguna ke halaman `/chat`.
   - JIKA gagal: Tampilkan pesan error (alert).

2. FUNGSI getAuthToken()
   - KEMBALIKAN `localStorage.getItem('access_token')`.

3. FUNGSI logout()
   - Hapus token dari `localStorage`.
   - Arahkan pengguna ke `/login`.
