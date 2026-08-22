# Pseudocode untuk `src/app/login/page.tsx`

```markdown
ALGORITMA HALAMAN LOGIN

1. INISIALISASI
   - Gunakan `useRouter` untuk navigasi.
   - Siapkan state `isLoading` (boolean) dan `errorMsg` (string).
   - Dapatkan `API_BASE_URL` dari environment variable.

2. FUNGSI handleGoogleSuccess(credentialResponse)
   - Set `isLoading` menjadi true dan bersihkan pesan error.
   - Kirim `id_token` dari Google ke endpoint API backend (`/api/auth/google/verify`) menggunakan metode POST.
   - JIKA respons gagal: Lemparkan error.
   - JIKA berhasil:
     - Dapatkan `access_token` dari respons JSON.
     - Simpan token menggunakan `setAuthToken(access_token)` dari `lib/auth`.
     - Arahkan (redirect) pengguna ke halaman `/chat` menggunakan `router.replace`.
   - JIKA terjadi error (Catch):
     - Tangkap error, log ke console, dan set `errorMsg` untuk ditampilkan di antarmuka pengguna.
     - Matikan status `isLoading`.

3. FUNGSI handleGoogleError()
   - Set pesan error bahwa login Google dibatalkan atau gagal.
   - Matikan status `isLoading`.

4. RENDER TAMPILAN
   - Tampilkan elemen dekoratif (blob) dan logo.
   - Tampilkan teks sambutan "Asisten WCD" dan deskripsinya.
   - JIKA ada `errorMsg`: Tampilkan teks error berwarna merah.
   - JIKA `isLoading` true: Tampilkan animasi loading (spinner).
   - JIKA `isLoading` false: Tampilkan tombol `<GoogleLogin />` dengan prop onSuccess dan onError yang mengarah ke fungsi penanganan di atas.
```
