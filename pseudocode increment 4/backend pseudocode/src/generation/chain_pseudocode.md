# Pseudocode untuk `src/generation/chain.py` (Updated with Monitoring)

```markdown
ALGORITMA GENERASI JAWABAN CHATBOT (chain.py) - UPDATED WITH MONITORING

1. IMPOR PUSTAKA - UPDATED
   - Langchain (Dokumen, Parser Output, Prompt Template, ChatOpenAI).
   - loguru (logger), modul konfigurasi, deteksi panduan.
   - MONITORING (NEW): import set_field dari monitoring.context
   - MONITORING (NEW): import calculate_llm_cost dari monitoring.pricing
   - MONITORING (NEW): import build_instrumented_http_client dari monitoring.openai_client

2. KONSTANTA PROMPT — tidak berubah
   - SYSTEM_PROMPT, HUMAN_PROMPT, HUMAN_PROMPT_WITH_HISTORY, dll.

3. FUNGSI _format_context(documents) — tidak berubah
4. FUNGSI _postprocess_answer(answer) — tidak berubah
5. FUNGSI _build_sources(context_documents, limit=3) — tidak berubah

6. FUNGSI build_rag_chain(streaming) - UPDATED
   - Buat ChatOpenAI dengan INSTRUMENTED HTTP CLIENT (NEW):
     ```
     llm = ChatOpenAI(
         model=..., api_key=..., temperature=0, max_tokens=1200,
         streaming=streaming,
         http_client=build_instrumented_http_client()  ← NEW
     )
     ```
   - Sisa logika chain tidak berubah.

7. KELAS RAGChain

   __init__ - UPDATED:
   - Buat _chain via build_rag_chain(streaming=False).
   - Buat _llm dengan INSTRUMENTED HTTP CLIENT (NEW):
     ```
     self._llm = ChatOpenAI(
         model=..., api_key=..., temperature=0,
         http_client=build_instrumented_http_client()  ← NEW
     )
     ```

   METHOD invoke_with_history(question, context_documents, history) - UPDATED:
   
   PERSIAPAN (tidak berubah):
   - Setup tiktoken encoder untuk profiling estimasi.
   - Log informasi pemrosesan.
   - Adaptive History: jika dokumen kosong, potong histori ke 1 turn terakhir.
   - Format context_str.
   - Profiling token INPUT (estimasi dengan tiktoken — masih dipakai untuk log).
   - Susun messages array (SystemMessage, HumanMessage, AIMessage).
   
   PANGGIL LLM:
   - response = self._llm.invoke(messages)
   - answer = _postprocess_answer(response.content)
   
   ACTUAL TOKEN USAGE (NEW — menggantikan estimasi tiktoken untuk metrics):
   - usage = getattr(response, "usage_metadata", None)
   - JIKA usage ada (langchain-openai versi baru):
     - actual_input_tokens = usage.get("input_tokens")
     - actual_output_tokens = usage.get("output_tokens")
   - JIKA usage tidak ada (fallback ke estimasi tiktoken):
     - actual_input_tokens = system_tokens + history_tokens + context_tokens + query_tokens
     - actual_output_tokens = count_tokens(answer)
     - Log warning bahwa fallback dipakai.
   
   HITUNG COST & KIRIM KE METRICS (NEW):
   - llm_cost = calculate_llm_cost(settings.llm_model, actual_input_tokens, actual_output_tokens)
   - set_field(
       input_tokens=actual_input_tokens,
       output_tokens=actual_output_tokens,
       llm_cost_usd=llm_cost
     )
   
   LOG PROFIL (UPDATED — menampilkan actual vs estimasi):
   ```
   ========== PROMPT PROFILE ==========
   System Prompt      : {system_tokens} tokens (estimasi)
   History            : {history_tokens} tokens (estimasi)
   Retrieved Context  : {context_tokens} tokens (estimasi)
   User Query         : {query_tokens} tokens (estimasi)
   ------------------------------------
   Input Aktual (API) : {actual_input_tokens} tokens
   Output Aktual (API): {actual_output_tokens} tokens
   Cost               : ${llm_cost:.6f}
   =====================================
   ```
   
   - Kembalikan {answer, sources}.

   METHOD invoke_conversational — tidak berubah
   METHOD invoke_clarification — tidak berubah

8. FUNGSI generate_answer(question, context) — tidak berubah

9. CATATAN TEKNIS:
   - response.usage_metadata adalah field resmi dari langchain-openai yang berisi
     {"input_tokens": int, "output_tokens": int, "total_tokens": int}.
   - Ini adalah token AKTUAL yang ditagihkan OpenAI, bukan estimasi tiktoken.
   - Estimasi tiktoken tetap dipakai untuk LOG PROFIL (untuk debug prompt size),
     tapi untuk metrics yang disimpan ke database, pakai nilai aktual.
   - http_client instrumented di _llm menghitung RETRY untuk generation calls.
```
