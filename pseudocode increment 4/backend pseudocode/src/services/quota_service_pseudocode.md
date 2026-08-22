# Pseudocode untuk `src/services/quota_service.py` (NEW SHARED SERVICE)

```markdown
ALGORITMA SHARED QUOTA MANAGEMENT SERVICE (quota_service.py)

1. IMPOR PUSTAKA
   - datetime (untuk format tanggal YYYY-MM-DD)
   - loguru.logger (untuk error logging)
   - supabase client dengan functools.lru_cache
   - config.settings untuk pengaturan aplikasi

2. FUNGSI _get_supabase_client() -> Client
   - @lru_cache(maxsize=1) untuk singleton pattern
   - Ambil settings dan create_client dengan supabase_url + service_key
   - KEMBALIKAN client instance yang di-cache

3. FUNGSI check_and_update_quota(user_id, daily_limit=None) -> bool
   - INPUT:
     - user_id: ID unik pengguna (mahasiswa_id atau telegram user_id)
     - daily_limit: Batas harian (opsional, default dari settings)
   - PROSES:
     - today = datetime.now().strftime("%Y-%m-%d")
     - limit = daily_limit or settings.RATE_LIMIT_REQUESTS
     - TRY:
       - Panggil supabase.rpc("increment_quota_if_under_limit", params)
       - response.data berisi boolean: True = allowed, False = limit reached
       - KEMBALIKAN bool(response.data)
     - EXCEPT Exception:
       - Log error dengan detail user_id
       - KEMBALIKAN True (FAIL-OPEN behavior untuk tidak block user)

4. FUNGSI get_quota_status(user_id) -> dict
   - INPUT: user_id untuk query status
   - PROSES:
     - Query tabel user_quotas untuk user_id + today's date
     - Ambil message_count saat ini (default: 0)
     - Hitung remaining = max(0, limit - current_count)
   - OUTPUT: Dictionary dengan:
     - user_id, date, current_count, limit, remaining
     - error field jika ada exception
   - EXCEPT Exception:
     - Log error dan return dict dengan error info

5. DESIGN PRINCIPLES:
   - ✅ SINGLE SOURCE OF TRUTH: Logic quota hanya di satu tempat
   - ✅ FAIL-OPEN: Return True pada DB errors (user experience priority)
   - ✅ ATOMIC OPERATIONS: Menggunakan RPC untuk thread-safe increment
   - ✅ CONFIGURABLE: Support custom daily limits dengan fallback
   - ✅ OBSERVABILITY: Error logging untuk monitoring issues

6. CLIENT INTEGRATION:
   - api/ai.py: Menggunakan check_and_update_quota() untuk website users
   - bot/chat_handler.py: Menggunakan check_and_update_quota() untuk telegram users  
   - ELIMINASI: Code duplication antara 2 endpoints
   - KONSISTENSI: Same behavior dan error handling di semua clients
```