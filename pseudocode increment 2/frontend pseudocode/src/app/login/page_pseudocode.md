ALGORITMA HALAMAN LOGIN

1. RENDER TAMPILAN
   - Tampilkan logo kampus.
   - Tampilkan judul "Selamat datang di Asisten WICIDA".
   - Tampilkan komponen `<GoogleLogin />` (menggunakan pustaka `@react-oauth/google`).
2. EVENT onSuccess (Google Sign-In)
   - Panggil fungsi `handleGoogleLogin(credentialResponse)` dari `lib/auth.ts`.
3. EVENT onError
   - Tampilkan pesan error login gagal.
