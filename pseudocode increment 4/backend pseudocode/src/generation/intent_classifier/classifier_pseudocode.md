# Pseudocode untuk `src/generation/intent_classifier/classifier.py` (Updated with Monitoring)

```markdown
ALGORITMA KLASIFIKASI INTENT (classifier.py) - UPDATED WITH MONITORING

> **⚠️ PERINGATAN ARSITEKTUR ⚠️**
> Modul IntentClassifier LLM ini **telah di-bypass secara praktis** pada arsitektur
> Retrieval-First / Evidence-Driven. File ini masih dipertahankan untuk referensi
> fallback dan kompatibilitas, namun core flow AI (ai_services.py) tidak lagi
> memanggil modul ini sebagai gatekeeper utama.

1. IMPOR PUSTAKA - UPDATED
   - JSON, Typing, Langchain (HumanMessage, SystemMessage, ChatOpenAI).
   - loguru (logger).
   - Konfigurasi, Memori percakapan.
   - Konstanta dan Detektor (SwitchDetector, ClarificationDetector, ConversationalDetector).
   - MONITORING (NEW — lazy import di dalam __init__):
     import build_instrumented_http_client dari monitoring.openai_client

2. FUNGSI _build_classifier_prompt(current_message, memory) — tidak berubah

3. KELAS IntentClassifier

   __init__ - UPDATED:
   - Inisialisasi settings.
   - LAZY IMPORT (NEW): from src.monitoring.openai_client import build_instrumented_http_client
   - Buat LLM dengan INSTRUMENTED HTTP CLIENT (NEW):
     ```
     self._llm = ChatOpenAI(
         model=settings.llm_model,
         http_client=build_instrumented_http_client(),  ← NEW
         temperature=0,
         api_key=settings.open_api_key,
         max_tokens=200,
     )
     ```
   - Inisialisasi cache dict kosong.
   - Inisialisasi SwitchDetector, ClarificationDetector, ConversationalDetector.
   
   classify(message, memory) — tidak berubah:
   - Tahap 1: Cek ConversationalDetector → shortcut CONVERSATIONAL.
   - Tahap 2: Jika pesan pertama → NEEDS_RETRIEVAL.
   - Tahap 3: Cek SwitchDetector → NEEDS_RETRIEVAL jika pindah topik.
   - Tahap 4: Cek ClarificationDetector → CLARIFICATION.
   - Tahap 5: Fallback ke LLM via _classify_with_llm().
   
   _classify_with_llm(message, memory) — tidak berubah:
   - Cache check.
   - Build prompt → panggil LLM → parse JSON response.
   - Simpan ke cache.
   - Fallback ke NEEDS_RETRIEVAL jika error.

4. MENGAPA http_client PERLU DIPASANG DI SINI:
   - Walau IntentClassifier jarang dipakai di core flow saat ini, jika dipanggil
     ia tetap memakai OpenAI API.
   - Tanpa instrumented http_client, retry dari classifier ini TIDAK dihitung
     di openai_retry_count di request_metrics.
   - Ini memastikan metrik B3 (retry rate ke OpenAI) AKURAT dari SEMUA sumber,
     bukan hanya dari generation.

5. CATATAN LAZY IMPORT:
   - Import dilakukan di dalam __init__ (bukan di top-level file) untuk menghindari
     circular import antara modul generation dan monitoring.
```
