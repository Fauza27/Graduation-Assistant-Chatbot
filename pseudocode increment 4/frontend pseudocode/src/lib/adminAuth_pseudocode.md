# Pseudocode: Admin Authentication Frontend

## File: `lib/adminAuth.ts`

```markdown
ALGORITMA ADMIN AUTHENTICATION FRONTEND (adminAuth.ts)

1. FUNGSI adminLogin(username: string, password: string, rememberMe: boolean)
   - Tujuan: Melakukan login admin ke backend dan menyimpan token
   - TAHAP 1: Prepare request
     - Build URL: `${NEXT_PUBLIC_API_BASE_URL}/api/admin/login`
     - Prepare body: JSON.stringify({username, password})
   - TAHAP 2: Send POST request
     - Headers: Content-Type: application/json
     - Handle different response status codes:
       - 401: Return {success: false, message: "Username atau password salah."}
       - Other errors: Return {success: false, message: "Gagal melakukan login. Silakan coba lagi."}
   - TAHAP 3: Process successful response
     - Extract access_token dan admin info dari response
     - Determine storage: rememberMe ? localStorage : sessionStorage
     - Store admin_access_token dan admin_info
   - TAHAP 4: Return success
     - Return {success: true}
   - ERROR HANDLING:
     - Catch network errors: Return {success: false, message: "Tidak bisa terhubung ke server."}

2. FUNGSI getAdminToken(): string | null
   - Check if running in browser (typeof window !== 'undefined')
   - JIKA server-side: return null
   - Try localStorage first, fallback to sessionStorage
   - Return admin_access_token atau null

3. FUNGSI getAdminInfo(): any | null
   - Check if running in browser
   - JIKA server-side: return null
   - Try localStorage first, fallback to sessionStorage untuk admin_info
   - JIKA ada raw data:
     - COBA parse JSON
     - JIKA parsing gagal: return null
     - JIKA berhasil: return parsed data
   - JIKA tidak ada data: return null

4. FUNGSI adminLogout(): void
   - Check if running in browser
   - JIKA server-side: return early
   - Remove tokens dari both storage untuk safety:
     - localStorage.removeItem('admin_access_token')
     - localStorage.removeItem('admin_info') 
     - sessionStorage.removeItem('admin_access_token')
     - sessionStorage.removeItem('admin_info')
   - Optional: Fire-and-forget POST to logout endpoint
     - Best-effort call ke `${NEXT_PUBLIC_API_BASE_URL}/api/admin/logout`
     - Ignore errors karena JWT stateless
```

**Security Features:**
- Dual storage support (localStorage vs sessionStorage) untuk "remember me"
- Client-side token cleanup pada logout
- Server-side rendering safe dengan window checks
- Secure token handling dengan fallback mechanisms