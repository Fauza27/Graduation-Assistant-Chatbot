# Flowchart: `src/middleware/`

## `security.py` — Keamanan & Validasi Input

### RateLimitMiddleware
Membatasi jumlah request per IP/session dalam jangka waktu tertentu.

```
Setiap HTTP Request masuk
       │
  Path /health? ──Yes──► Lewati (tidak dibatasi)
       │No
       ▼
_get_client_id(request)
  ├─ Ada session_id di state? → "session:xxx"
  └─ Tidak ada? → ambil IP dari X-Forwarded-For atau request.client
       │
       ▼
_check_rate_limit(client_id)
  ├─ Bersihkan entri lama (di luar jendela waktu)
  ├─ Hitung total request dalam window
  ├─ Total ≥ limit? → Return (False, 0, reset_time)
  └─ Masih OK? → catat request, Return (True, remaining, reset_time)
       │
  Melebihi limit? ──Yes──► HTTP 429 Too Many Requests
       │No
       ▼
Lanjutkan request + tambahkan header:
  X-RateLimit-Limit, X-RateLimit-Remaining,
  X-RateLimit-Reset, X-RateLimit-Window
```

### SecurityHeadersMiddleware
```
Setiap response ditambahkan header keamanan:
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  X-XSS-Protection: 1; mode=block
  Referrer-Policy: strict-origin-when-cross-origin
  [Production only] Strict-Transport-Security: max-age=31536000
```

### sanitize_input(text, max_length=1000)
```
Input teks dari user
  ├─ Potong ke max_length karakter
  ├─ Hapus control characters Unicode (Cc) kecuali \t \n \r
  ├─ Normalisasi whitespace berlebih
  └─ Return teks bersih
```

### validate_chat_input(question, session_id)
```
  ├─ validate_session_id: panjang 3-100, hanya alphanumeric/_/-
  ├─ Tidak valid? → InputValidationError
  ├─ sanitize_input(question, max_length=500)
  ├─ Kosong atau < 3 karakter? → InputValidationError
  └─ Return (sanitized_question, session_id)
```

---

## `monitoring.py` — Monitoring Performa

### MetricsMiddleware
```
Setiap HTTP Request
       │
       ▼
Catat waktu mulai
       │
  Request ke /chat? → Coba ekstrak session_id dari body JSON
       │
       ▼
Proses request (call_next)
       │
       ▼
Hitung duration_ms = (selesai - mulai) × 1000
       │
       ▼
Buat RequestMetrics {timestamp, method, path, status, duration, session_id}
       │
       ▼
_system_metrics.add_request(metrics)
  ├─ total_requests += 1
  ├─ successful/failed_requests += 1
  ├─ Simpan ke recent_requests (maks 1000 entri)
  └─ Update avg_response_time (rolling 100 terakhir)
       │
  duration > 5000ms? ──Yes──► Log WARNING "Slow request"
       │
Add header: X-Response-Time: NNNms
```

### PerformanceTracker (Context Manager)
```
with PerformanceTracker("nama_operasi"):
    lakukan_sesuatu()
    # Otomatis log durasi saat selesai
    # Jika > 1 detik → WARNING
    # Jika ada error → ERROR log
```

### SystemMetrics.get_stats(window_minutes=60)
```
  Ambil semua request dalam N menit terakhir
  Hitung: total, successful, failed, avg_time, error_rate
  Return dict statistik
```
