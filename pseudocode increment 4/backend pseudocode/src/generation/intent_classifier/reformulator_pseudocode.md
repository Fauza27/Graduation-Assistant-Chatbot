# Pseudocode untuk `src/generation/intent_classifier/reformulator.py` (Updated with Monitoring)

```markdown
ALGORITMA REFORMULASI PERTANYAAN (reformulator.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA - UPDATED
   - Langchain (HumanMessage, ChatOpenAI).
   - Logger, Pengaturan, Memori.
   - Konstanta (IMPLICIT_REFERENCE_SIGNALS, REFORMULATION_PROMPT).
   - MONITORING (NEW — lazy import di dalam __init__):
     import build_instrumented_http_client dari monitoring.openai_client

2. FUNGSI normalize_query(query) — tidak berubah
   - Normalisasi KKP/PI aliases via Regex.
   - "apa itu X" → "Apa yang dimaksud dengan X".

3. FUNGSI needs_rewrite(query) — tidak berubah
   - Cek implicit reference signals dengan Regex word boundary.
   - KEMBALIKAN True/False.

4. KELAS QueryReformulator

   __init__(llm=None) - UPDATED:
   - JIKA llm tidak diberikan:
     - LAZY IMPORT (NEW): from src.monitoring.openai_client import build_instrumented_http_client
     - Buat LLM dengan INSTRUMENTED HTTP CLIENT (NEW):
       ```
       self._llm = ChatOpenAI(
           model=settings.llm_model,
           http_client=build_instrumented_http_client(),  ← NEW
           temperature=0,
           api_key=settings.open_api_key,
           max_tokens=100,
       )
       ```
   - JIKA llm diberikan (injection): pakai llm yang diberikan.
     NOTE: Jika llm di-inject dari luar, http_client instrumentation bergantung
     pada implementasi llm yang diinjeksikan.
   
   _extract_last_topic(memory) — tidak berubah:
   - Baca memori mundur untuk menemukan topik terakhir (KKP atau PI).
   
   _apply_rule_rewrite(message, last_topic) — tidak berubah:
   - Penulisan ulang instan via Rule/Regex tanpa panggil LLM.
   
   reformulate_query(message, memory) — tidak berubah:
   - JIKA memori kosong: return (pesan asli, "None").
   - JIKA rule rewrite berhasil: return (pesan diperbaiki, "Rule").
   - FALLBACK ke LLM Reformulator.
   - return (pesan dari LLM, "LLM") atau (pesan asli, "None") jika error.

5. FUNGSI reformulate_query(message, memory, llm) — tidak berubah
   - Wrapper kompatibilitas yang mengembalikan tuple (teks, metode).

6. MENGAPA http_client PERLU DIPASANG DI SINI:
   - Reformulator adalah salah satu dari 4 titik panggilan OpenAI di sistem.
   - Titik lain: RAGChain._llm, IntentClassifier._llm, HybridSearcher._embedder.
   - Semua 4 titik harus memakai instrumented http_client agar openai_retry_count
     di request_metrics mencerminkan total retry dari SEMUA OpenAI calls dalam satu
     request, bukan hanya dari generation.
   - Ini memastikan akurasi metrik B3 (retry rate ke OpenAI).

7. CATATAN LAZY IMPORT:
   - Import dilakukan di dalam __init__ (bukan di top-level file) untuk menghindari
     circular import antara modul generation dan monitoring.
```
