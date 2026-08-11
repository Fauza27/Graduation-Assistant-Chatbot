# Pseudocode: Admin Authentication System

## File: `src/admin/auth.py`

```markdown
ALGORITMA AUTENTIKASI ADMIN (auth.py)

1. IMPOR PUSTAKA
   - bcrypt untuk hashing dan verifikasi password
   - FastAPI (Header, HTTPException, Depends)
   - JWT utilities (create_access_token, verify_access_token)
   - Supabase Client, loguru logger
   - Konfigurasi aplikasi (get_settings)

2. EXCEPTION CLASS
   - ResourceNotFoundError: Exception khusus untuk resource yang tidak ditemukan

3. FUNGSI hash_password(plain_password: str) -> str
   - Generate salt menggunakan bcrypt.gensalt()
   - Hash password plain text dengan salt
   - KEMBALIKAN password hash sebagai string UTF-8

4. FUNGSI verify_password(plain_password: str, password_hash: str) -> bool
   - COBA verifikasi plain_password dengan password_hash menggunakan bcrypt.checkpw()
   - JIKA berhasil: KEMBALIKAN True
   - JIKA gagal (ValueError): KEMBALIKAN False

5. FUNGSI authenticate_admin(username: str, plain_password: str, supabase: Client) -> dict | None
   - Query database: SELECT * FROM admin_users WHERE username = ? LIMIT 1
   - JIKA tidak ditemukan: KEMBALIKAN None
   - Ambil password_hash dari hasil query
   - Verifikasi password menggunakan verify_password()
   - JIKA password salah: KEMBALIKAN None
   - JIKA password benar:
     - Update last_login dengan timestamp sekarang (fire-and-forget)
     - Buat admin profile tanpa password_hash (admin_id, username, full_name)
     - KEMBALIKAN admin profile

6. FUNGSI issue_admin_token(admin: dict) -> str
   - Buat payload JWT dengan:
     - sub: admin_id
     - username: admin username
     - role: "admin"
   - KEMBALIKAN JWT token menggunakan create_access_token()

7. FUNGSI get_current_admin(authorization: str = Header(None)) -> dict
   - DEPENDENCY untuk FastAPI endpoint yang memerlukan autentikasi admin
   - Cek header Authorization format "Bearer <token>"
   - JIKA header invalid: LEMPAR HTTPException 401
   - Extract token dari header
   - Verifikasi token menggunakan verify_access_token()
   - JIKA token invalid/expired: LEMPAR HTTPException 401
   - Cek role dalam payload
   - JIKA role bukan "admin": LEMPAR HTTPException 403
   - KEMBALIKAN payload token
```

**Keamanan Features:**
- bcrypt salt + hash untuk password storage
- JWT token dengan role-based access control
- Automatic last_login timestamp tracking
- Secure header validation