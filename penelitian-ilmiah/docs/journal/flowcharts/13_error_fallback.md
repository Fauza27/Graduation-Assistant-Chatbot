# Peta Error & Fallback — Apa yang Terjadi Saat Ada Masalah?

---

## Peta Lengkap Error dan Penanganannya

```
SUMBER ERROR              YANG TERJADI                  DAMPAK KE USER
─────────────────────────────────────────────────────────────────────────
OpenAI API timeout/down
  ├─ Di embedding (hybrid_search) → Exception           → HTTP 500 (REST)
  │                                                     → Pesan error (TG)
  ├─ Di LLM generation (chain.py) → Exception           → HTTP 500 (REST)
  │                                                     → GENERIC_ERROR (TG)
  └─ Di intent classifier         → Fallback ke          → Sistem tetap jalan
                                    NEEDS_RETRIEVAL       dengan asumsi terburuk

Supabase timeout/down
  ├─ Di hybrid_search RPC         → Exception, propagate → HTTP 500 / Error TG
  ├─ Di fetch_parents             → Exception, propagate → HTTP 500 / Error TG
  └─ Di check_and_update_quota    → !! ALLOW request     → User tetap bisa tanya
                                    (fallback=True)        (sistem tidak blokir)

Cross-Encoder gagal load/error
  └─ Di reranker.rerank()         → Warning log          → Tetap dapat jawaban
                                    Fallback: top-N        (kualitas sedikit turun)
                                    tanpa rerank

Clarification: konteks tidak relevan (score < 0.3)
  └─ Di invoke_clarification()    → Fallback ke          → Jawaban tetap benar
                                    run_retrieval()        (ambil konteks baru)

Clarification: tidak ada last_docs
  └─ Di invoke_clarification()    → Fallback ke          → Jawaban tetap benar
                                    run_retrieval()

Hybrid search kosong (tidak ada hasil)
  └─ Di hybrid_search.search()    → Warning log          → Coba dense-only search
                                    Fallback ke
                                    match_child_documents

Dense-only search juga kosong
  └─ Di hybrid_search.search()    → Return []            → "Informasi tidak
                                                            ditemukan dalam panduan"

Intent classifier: LLM response tidak valid JSON
  └─ Di _classify_with_llm()      → Warning log          → Fallback ke
                                                            NEEDS_RETRIEVAL (0.5)

Query reformulation gagal
  └─ Di reformulate_query()       → Warning log          → Pakai query asli
                                    Return original         (tidak error)

Input kosong / terlalu pendek
  └─ Di chat()                    → Return error dict    → Pesan error spesifik
                                    {error: "empty_query"}

Session ID tidak valid
  └─ Di chat()                    → Return error dict    → Pesan error spesifik
```

---

## Detail: Error yang "Ditelan" vs Disebarkan

### ✅ Error yang DITANGANI (tidak crash ke user)

| Lokasi | Error | Penanganan |
|--------|-------|-----------|
| `check_and_update_quota` | DB error | Fallback: allow request |
| `_classify_with_llm` | JSON parse error | Fallback: NEEDS_RETRIEVAL |
| `reformulate_query` | LLM error | Pakai query asli |
| `reranker.rerank` | Model error | Top-N unranked |
| `hybrid_search` | Kosong | Fallback dense-only |
| `invoke_clarification` | Konteks tidak relevan | Fallback retrieval |
| `_fallback_to_retrieval` | Retrieval error | Jawaban "mohon maaf" |

### ❌ Error yang DISEBARKAN (bisa crash ke user)

| Lokasi | Error | Dampak |
|--------|-------|--------|
| `hybrid_search → embed_query` | OpenAI down | HTTP 500 |
| `hybrid_search → supabase RPC` | Supabase down | HTTP 500 |
| `parent_child → fetch_parents` | Supabase down | HTTP 500 |
| `chain.py → LLM invoke` | OpenAI down | HTTP 500 |

---

## Alur Error di Layer Telegram

```
handle_text_chat()
  try:
    ... proses normal ...
  except Exception:
    logger.exception(...)
    error_text = messages.GENERIC_ERROR

    if loading_message ada:
      loading_message.edit_text(error_text)  ← ganti loading dengan pesan error
    else:
      update.message.reply_text(error_text)  ← kirim pesan error baru
```

**User melihat:** `"Maaf, terjadi kesalahan. Silakan coba lagi."`

---

## Alur Error di Layer REST API

```
chat_endpoint() di api/ai.py
  try:
    result = chat_service(query, session_id)
    return ChatResponse(...)
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

**User menerima:**
```json
{
  "detail": "pesan error teknis"
}
```

---

## Skenario: Apa yang Terjadi Saat OpenAI Down?

```
User: "Apa syarat KKP?"
  │
  ▼
Intent Classification → LLM dipanggil untuk classify
  │
  ▼ LLM TIMEOUT/ERROR
  │
  Fallback: Return NEEDS_RETRIEVAL, confidence=0.5
  │
  ▼
Hybrid Search → embed_query() dipanggil
  │
  ▼ EMBED GAGAL (OpenAI down) → Exception disebarkan
  │
  ▼
_handle_retrieval() → Exception tidak ditangkap
  │
  ▼
chat() → outer try/except menangkap
  │
  ▼
Return {
  "answer": "Maaf, terjadi kesalahan saat memproses pertanyaan...",
  "error": "Connection timeout",
  "error_type": "TimeoutError"
}
```

---

## Skenario: Apa yang Terjadi Saat Reranker Gagal?

```
run_retrieval()
  │
  ▼
HybridSearcher.search() → 30 child results ✓
ParentChildFetcher.fetch_parents() → 12 parent docs ✓
  │
  ▼
CrossEncoderReranker.rerank() → GAGAL (model tidak bisa load)
  │
  ▼ Exception ditangkap di pipeline.py:
  │
  logger.warning("Reranking failed, using unranked top-N")
  reranked = parent_results[:settings.rerank_top_n]  ← ambil 8 pertama tanpa rerank
  │
  ▼
Sistem tetap jalan, user mendapat jawaban
(tapi kualitas ranking mungkin tidak optimal)
```

---

## Monitoring Error

Semua error dicatat dengan tingkat keparahan berbeda:
- `logger.debug(...)` — informasi detail untuk debugging
- `logger.info(...)` — operasi normal
- `logger.warning(...)` — ada yang tidak optimal tapi masih jalan
- `logger.error(...)` — ada masalah serius
- `logger.exception(...)` — error dengan stack trace lengkap

Slow request (>5 detik) juga dicatat otomatis oleh `MetricsMiddleware`.
