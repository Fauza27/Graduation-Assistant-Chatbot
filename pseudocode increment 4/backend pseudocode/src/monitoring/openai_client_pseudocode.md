# Pseudocode untuk `src/monitoring/openai_client.py`

```markdown
ALGORITMA HTTP CLIENT INSTRUMENTED UNTUK OPENAI (openai_client.py)

Membuat httpx.Client kustom yang menghitung jumlah retry ke OpenAI
lewat event hook pada setiap HTTP response — termasuk response yang
di-retry secara internal oleh OpenAI SDK sebelum akhirnya sukses/gagal.

1. KONSTANTA
   - _RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)
   - HTTP status codes yang menandakan retry oleh SDK.

2. FUNGSI _on_response(response: httpx.Response) -> None
   - JIKA response.status_code ada di _RETRYABLE_STATUS_CODES:
     - Panggil add_retry() dari monitoring.context.
     - Ini menambah openai_retry_count di collector aktif.
   - Event hook ini TIDAK mempengaruhi flow request, hanya mencatat.

3. FUNGSI build_instrumented_http_client() -> httpx.Client
   - Buat httpx.Client baru dengan event_hooks={"response": [_on_response]}.
   - Kembalikan client ini.
   
   CARA PAKAI:
   - Dipakai sebagai parameter http_client= saat membuat ChatOpenAI/OpenAIEmbeddings:
     ```python
     ChatOpenAI(model="gpt-4o-mini", http_client=build_instrumented_http_client())
     ```
   - Dipasang di SEMUA 4 titik panggilan OpenAI:
     * RAGChain.__init__ (generation)
     * build_rag_chain() (generation)
     * IntentClassifier.__init__ (classifier)
     * QueryReformulator.__init__ (reformulator)
     * HybridSearcher.__init__ (embedder)

CATATAN TEKNIS:
   - OpenAI Python SDK v1.x berjalan di atas httpx.
   - httpx.Client mendukung event_hooks yang terpanggil di SETIAP response.
   - Ini memungkinkan penghitungan retry tanpa monkey-patching SDK.
   - Setiap panggilan build_instrumented_http_client() membuat CLIENT BARU
     (bukan singleton) — ini disengaja agar setiap komponen punya client sendiri.
```
