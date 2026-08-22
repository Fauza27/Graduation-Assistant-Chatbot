ALGORITMA OTENTIKASI & TOKEN UTILITIES

1. FUNGSI getAuthToken(): string | null
   - Check if running in browser (typeof window !== 'undefined')
   - JIKA server-side: return null
   - KEMBALIKAN localStorage.getItem('access_token')

2. FUNGSI setAuthToken(token: string): void
   - Check if running in browser
   - JIKA server-side: return early
   - Simpan token: localStorage.setItem('access_token', token)

3. FUNGSI logout(): void
   - Check if running in browser
   - JIKA server-side: return early
   - Hapus token: localStorage.removeItem('access_token')
   - Redirect: window.location.href = '/login'

CATATAN: Fungsi login sebenarnya (handleGoogleSuccess) berada di app/login/page.tsx, bukan di file ini.
