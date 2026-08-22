# Pseudocode untuk `src/auth/jwt_utils.py`

```markdown
ALGORITMA MANAJEMEN JWT (jwt_utils.py)

1. IMPOR PUSTAKA
   - `jwt` (PyJWT) untuk encode/decode token.
   - datetime untuk manajemen waktu kedaluwarsa.
   - HTTPException untuk penanganan error.

2. FUNGSI create_access_token(data)
   - Terima kamus data payload.
   - Set waktu kedaluwarsa (expire) = Waktu Sekarang + JWT_EXPIRATION_MINUTES.
   - Tambahkan 'exp' ke dalam data.
   - ENCODE data menjadi token string menggunakan JWT_SECRET_KEY dan JWT_ALGORITHM.
   - KEMBALIKAN token string.

3. FUNGSI verify_access_token(token)
   - COBA decode token menggunakan JWT_SECRET_KEY dan JWT_ALGORITHM.
   - KEMBALIKAN hasil decode (payload).
   - JIKA kedaluwarsa (ExpiredSignatureError):
     - Lempar HTTPException 401 (Token has expired).
   - JIKA error lainnya (PyJWTError):
     - Lempar HTTPException 401 (Could not validate credentials).
```
