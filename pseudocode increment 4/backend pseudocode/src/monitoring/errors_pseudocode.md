# Pseudocode untuk `src/monitoring/errors.py`

```markdown
ALGORITMA TAKSONOMI ERROR (errors.py)

Modul ini mendefinisikan hierarki exception kustom untuk memastikan klasifikasi
`error_source` di request_metrics akurat dan konsisten di seluruh codebase.

1. HIERARKI EXCEPTION:

   CLASS ChatError(Exception)
   - Base exception untuk semua error di alur chat.
   - Atribut kelas: error_source = "unknown"

   CLASS ValidationServiceError(ChatError)
   - Dipakai untuk error validasi input/auth.
   - error_source = "validation"

   CLASS OpenAIServiceError(ChatError)
   - Dipakai untuk error dari panggilan OpenAI API.
   - error_source = "openai"

   CLASS SupabaseServiceError(ChatError)
   - Dipakai untuk error dari operasi database Supabase.
   - error_source = "supabase"

   CLASS RetrievalError(ChatError)
   - Kompatibilitas mundur dengan RetrievalError lama di ai_services.py.
   - error_source = "supabase"

   CLASS RateLimitServiceError(ChatError)
   - Dipakai untuk error rate limiting.
   - error_source = "rate_limit"

2. FUNGSI classify_exception(exc) -> tuple[str, str]
   - INPUT: exception APA PUN (ChatError turunan maupun exception library pihak ketiga)
   - OUTPUT: tuple (error_source, error_type)
   
   ALGORITMA:
   - JIKA exc adalah instance ChatError:
     - Kembalikan (exc.error_source, type(exc).__name__)
   
   - Ambil nama modul dari type(exc).__module__
   
   - JIKA "openai" ada di nama modul:
     - Kembalikan ("openai", type(exc).__name__)
   
   - JIKA "postgrest", "supabase", atau "httpx" ada di nama modul:
     - Kembalikan ("supabase", type(exc).__name__)
   
   - JIKA exc adalah ValueError:
     - Kembalikan ("validation", type(exc).__name__)
   
   - DEFAULT: Kembalikan ("unknown", type(exc).__name__)

CARA PAKAI:
   Cara 1 (PALING AKURAT) — raise exception spesifik di titik yang dikontrol:
   ```python
   raise OpenAIServiceError("Rate limit exceeded")
   ```
   
   Cara 2 (FALLBACK) — untuk exception dari library pihak ketiga:
   ```python
   error_source, error_type = classify_exception(exc)
   ```
```
