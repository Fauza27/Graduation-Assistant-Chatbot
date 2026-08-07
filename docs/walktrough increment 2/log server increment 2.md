# Log Server Backend & Frontend

Berikut adalah isi *log* lengkap dan belum terpotong dari eksekusi server yang terakhir berjalan.

## Backend Log (FastAPI + Uvicorn)
```log
15:49:43 | INFO     | Settings loaded: LLM=gpt-4o-mini, Embedding=text-embedding-3-large
15:49:43 | INFO     | Starting FastAPI server on port 8000
15:49:43 | INFO     | Environment: development
15:49:43 | INFO     | Reload mode: enabled
INFO:     Will watch for changes in these directories: ['C:\Users\Muhammad Fauza\SKRIPSI\backend']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [10576] using StatReload
2026-08-07 15:50:09.436 | INFO     | src.services.session_store:_test_connection:51 - Database session store initialized successfully
2026-08-07 15:50:09.437 | INFO     | src.services.ai_services:<module>:26 - Using database-backed session storage
INFO:     Started server process [27600]
INFO:     Waiting for application startup.
2026-08-07 15:50:10.763 | INFO     | src.services.ai_services:preload_models:279 - Pre-warming AI models...
2026-08-07 15:50:19.550 | INFO     | src.services.ai_services:preload_models:287 - Pre-warming: CrossEncoder
2026-08-07 15:50:19.550 | INFO     | src.retrieval.reranker:_get_model:45 - Loading cross-encoder model: cross-encoder/ms-marco-MiniLM-L-6-v2...
Loading weights:   0%|          | 0/105 [00:00<?, ?it/s]Loading weights: 100%|##########| 105/105 [00:00<00:00, 2637.00it/s]
BertForSequenceClassification LOAD REPORT from: cross-encoder/ms-marco-MiniLM-L-6-v2
Key                          | Status     |  | 
-----------------------------+------------+--+-
bert.embeddings.position_ids | UNEXPECTED |  | 

Notes:
- UNEXPECTED:	can be ignored when loading from different task/architecture; not ok if you expect identical arch.
2026-08-07 15:50:29.522 | INFO     | src.retrieval.reranker:_get_model:48 - Cross-encoder model loaded.
2026-08-07 15:50:29.522 | INFO     | src.services.ai_services:preload_models:292 - Pre-warming: Embedding Model
2026-08-07 15:50:30.449 | INFO     | src.services.ai_services:preload_models:297 - ✅ AI models pre-warmed successfully in 19.68s
INFO:     Application startup complete.
C:\Users\Muhammad Fauza\SKRIPSI\backend\.venv\lib\site-packages\jwt\api_jwt.py:365: InsecureKeyLengthWarning: The HMAC key is 25 bytes long, which is below the minimum recommended length of 32 bytes for SHA256. See RFC 7518 Section 3.2.
  decoded = self.decode_complete(
INFO:     127.0.0.1:61238 - "GET /api/sessions/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:60455 - "GET /api/sessions/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:60455 - "GET /api/sessions/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:61238 - "GET /api/sessions/ HTTP/1.1" 200 OK
2026-08-07 15:50:46.214 | INFO     | src.services.ai_services:chat:159 - [session=11fab726-8e85-4fdb-acdb-14f6903ac755] Question: apa syarat untuk mengambil non skripsi
2026-08-07 15:50:46.216 | INFO     | src.services.ai_services:chat:190 - 🔍 [Cache Miss] Running retrieval for: 'apa syarat untuk mengambil non skripsi'
2026-08-07 15:50:46.264 | INFO     | src.retrieval.self_query:_load_section_keywords:73 - Loaded section keywords from section_keywords.yaml: 8 sections, 314 keywords total
2026-08-07 15:50:46.265 | DEBUG    | src.retrieval.self_query:extract_query_components:241 - Menganalisis query: 'apa syarat untuk mengambil non skripsi'
2026-08-07 15:50:46.269 | INFO     | src.retrieval.self_query:extract_query_components:254 - Query dianalisis » semantic: 'apa syarat untuk mengambil non skripsi' | filters: {} | confidence: low
2026-08-07 15:50:46.320 | INFO     | src.retrieval.hybrid_search:search:83 - Hybrid search: 'apa syarat untuk mengambil non skripsi' | filters: {} | top_k: 20
2026-08-07 15:50:47.061 | INFO     | src.retrieval.hybrid_search:search:88 -   [Profile] Query Embedding: 0.74s
2026-08-07 15:50:47.424 | INFO     | src.retrieval.hybrid_search:search:104 -   [Profile] Supabase Hybrid RPC: 0.36s
2026-08-07 15:50:47.424 | INFO     | src.retrieval.hybrid_search:search:159 - Hybrid search selesai: 20 results
2026-08-07 15:50:47.424 | INFO     | src.retrieval.hybrid_search:search:161 -   Top: non-skripsi-031 | hybrid=0.0115
2026-08-07 15:50:47.440 | INFO     | src.retrieval.parent_child:fetch_parents:47 - De-duplikasi: 20 children → 16 unique parents
2026-08-07 15:50:47.680 | INFO     | src.retrieval.parent_child:fetch_parents:60 -   [Profile] Supabase Parent Fetch: 0.24s
2026-08-07 15:50:47.681 | INFO     | src.retrieval.parent_child:fetch_parents:78 - Fetched 16 parent chunks. Top parent: '2.5 SYARAT DAN KETENTUAN TUGAS AKHIR NON SKRIPSI' (score=0.0115)
2026-08-07 15:50:47.681 | INFO     | src.retrieval.reranker:rerank:78 - Cross-encoder scoring 8 pairs...
2026-08-07 15:50:48.926 | INFO     | src.retrieval.reranker:rerank:88 - Reranking done: 8 → 5 documents. Top score: 2.1473, Bottom score: -2.7620
2026-08-07 15:50:48.927 | INFO     | src.retrieval.pipeline:run_retrieval:136 - 
========== Retrieval Summary ==========
Retrieved Parents : 8
After Threshold   : 3
Top Score         : 2.15
Reason            : Adaptive Relative Gap
LLM Mode          : RAG
=======================================
2026-08-07 15:50:48.927 | INFO     | src.retrieval.pipeline:run_retrieval:138 - ⏱️ [Retrieval Pipeline] Total: 2.66s | Parse: 0.00s | Search: 1.15s | Fetch: 0.26s | Rerank: 1.25s
2026-08-07 15:50:49.153 | WARNING  | src.services.session_store:load_memory:113 - Failed to load session 11fab726-8e85-4fdb-acdb-14f6903ac755 from database: {'message': 'Cannot coerce the result to a single JSON object', 'code': 'PGRST116', 'hint': None, 'details': 'The result contains 0 rows'}
2026-08-07 15:50:49.870 | INFO     | src.generation.chain:invoke_with_history:201 - Generating answer for: 'apa syarat untuk mengambil non skripsi' (history: 0 messages)
2026-08-07 15:50:53.707 | INFO     | src.generation.chain:invoke_with_history:253 - 
========== PROMPT PROFILE ==========
System Prompt     : 246 tokens
History           : 0 tokens
Retrieved Context : 1790 tokens
User Query        : 9 tokens
------------------------------------
Total Input       : 2045 tokens (approx)
Output            : 159 tokens
====================================
2026-08-07 15:50:53.707 | SUCCESS  | src.generation.chain:invoke_with_history:260 - Generation complete: 621 chars
2026-08-07 15:50:53.708 | INFO     | src.services.ai_services:chat:210 - [session=11fab726-8e85-4fdb-acdb-14f6903ac755] Generation time [⏱️ 4.45s]
2026-08-07 15:50:53.886 | DEBUG    | src.services.session_store:save_memory:155 - Session 11fab726-8e85-4fdb-acdb-14f6903ac755 saved with 2 turns
2026-08-07 15:50:53.886 | INFO     | src.services.ai_services:chat:238 - [session=11fab726-8e85-4fdb-acdb-14f6903ac755] Total process time [⏱️ 7.67s]
INFO:     127.0.0.1:59369 - "POST /api/ai/chat HTTP/1.1" 200 OK
2026-08-07 15:51:19.869 | INFO     | src.services.ai_services:chat:159 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Question: apa syarat untuk bisa mengambil skripsi?
2026-08-07 15:51:19.869 | INFO     | src.services.ai_services:chat:190 - 🔍 [Cache Miss] Running retrieval for: 'apa syarat untuk bisa mengambil skripsi?'
2026-08-07 15:51:19.869 | DEBUG    | src.retrieval.self_query:extract_query_components:241 - Menganalisis query: 'apa syarat untuk bisa mengambil skripsi?'
2026-08-07 15:51:19.869 | INFO     | src.retrieval.self_query:extract_query_components:254 - Query dianalisis » semantic: 'apa syarat untuk bisa mengambil skripsi?' | filters: {'source': 'Panduan Penyusunan Skripsi Cetak'} | confidence: low
2026-08-07 15:51:19.939 | INFO     | src.retrieval.hybrid_search:search:83 - Hybrid search: 'apa syarat untuk bisa mengambil skripsi?' | filters: {'source': 'Panduan Penyusunan Skripsi Cetak'} | top_k: 20
2026-08-07 15:51:20.633 | INFO     | src.retrieval.hybrid_search:search:88 -   [Profile] Query Embedding: 0.69s
2026-08-07 15:51:21.057 | INFO     | src.retrieval.hybrid_search:search:104 -   [Profile] Supabase Hybrid RPC: 0.42s
2026-08-07 15:51:21.058 | INFO     | src.retrieval.hybrid_search:search:159 - Hybrid search selesai: 20 results
2026-08-07 15:51:21.058 | INFO     | src.retrieval.hybrid_search:search:161 -   Top: skripsi-028 | hybrid=0.0115
2026-08-07 15:51:21.136 | INFO     | src.retrieval.parent_child:fetch_parents:47 - De-duplikasi: 20 children → 17 unique parents
2026-08-07 15:51:21.429 | INFO     | src.retrieval.parent_child:fetch_parents:60 -   [Profile] Supabase Parent Fetch: 0.29s
2026-08-07 15:51:21.429 | INFO     | src.retrieval.parent_child:fetch_parents:78 - Fetched 17 parent chunks. Top parent: '2.5 Syarat dan Awal Pengajuan Proposal' (score=0.0115)
2026-08-07 15:51:21.430 | INFO     | src.retrieval.reranker:rerank:78 - Cross-encoder scoring 8 pairs...
2026-08-07 15:51:22.891 | INFO     | src.retrieval.reranker:rerank:88 - Reranking done: 8 → 5 documents. Top score: 2.0236, Bottom score: -4.1601
2026-08-07 15:51:22.892 | INFO     | src.retrieval.pipeline:run_retrieval:136 - 
========== Retrieval Summary ==========
Retrieved Parents : 8
After Threshold   : 4
Top Score         : 2.02
Reason            : Adaptive Relative Gap
LLM Mode          : RAG
=======================================
2026-08-07 15:51:22.893 | INFO     | src.retrieval.pipeline:run_retrieval:138 - ⏱️ [Retrieval Pipeline] Total: 3.02s | Parse: 0.00s | Search: 1.19s | Fetch: 0.37s | Rerank: 1.46s
2026-08-07 15:51:23.139 | WARNING  | src.services.session_store:load_memory:113 - Failed to load session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b from database: {'message': 'Cannot coerce the result to a single JSON object', 'code': 'PGRST116', 'hint': None, 'details': 'The result contains 0 rows'}
2026-08-07 15:51:23.228 | INFO     | src.generation.chain:invoke_with_history:201 - Generating answer for: 'apa syarat untuk bisa mengambil skripsi?' (history: 0 messages)
2026-08-07 15:51:27.168 | INFO     | src.generation.chain:invoke_with_history:253 - 
========== PROMPT PROFILE ==========
System Prompt     : 246 tokens
History           : 0 tokens
Retrieved Context : 2150 tokens
User Query        : 10 tokens
------------------------------------
Total Input       : 2406 tokens (approx)
Output            : 218 tokens
====================================
2026-08-07 15:51:27.169 | SUCCESS  | src.generation.chain:invoke_with_history:260 - Generation complete: 927 chars
2026-08-07 15:51:27.169 | INFO     | src.services.ai_services:chat:210 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Generation time [⏱️ 3.94s]
2026-08-07 15:51:27.256 | DEBUG    | src.services.session_store:save_memory:155 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b saved with 2 turns
2026-08-07 15:51:27.256 | INFO     | src.services.ai_services:chat:238 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Total process time [⏱️ 7.39s]
INFO:     127.0.0.1:50060 - "POST /api/ai/chat HTTP/1.1" 200 OK
INFO:     127.0.0.1:50203 - "OPTIONS /api/ai/chat HTTP/1.1" 200 OK
2026-08-07 15:52:13.755 | INFO     | src.services.ai_services:chat:159 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Question: kalau ipk saya dibawah 3,25 bagaimana?
2026-08-07 15:52:13.755 | INFO     | src.services.ai_services:chat:190 - 🔍 [Cache Miss] Running retrieval for: 'kalau ipk saya dibawah 3,25 bagaimana?'
2026-08-07 15:52:13.755 | DEBUG    | src.retrieval.self_query:extract_query_components:241 - Menganalisis query: 'kalau ipk saya dibawah 3,25 bagaimana?'
2026-08-07 15:52:13.755 | INFO     | src.retrieval.self_query:extract_query_components:254 - Query dianalisis » semantic: 'kalau ipk saya dibawah 3,25 bagaimana?' | filters: {} | confidence: low
2026-08-07 15:52:13.805 | INFO     | src.retrieval.hybrid_search:search:83 - Hybrid search: 'kalau ipk saya dibawah 3,25 bagaimana?' | filters: {} | top_k: 20
2026-08-07 15:52:15.185 | INFO     | src.retrieval.hybrid_search:search:88 -   [Profile] Query Embedding: 1.38s
2026-08-07 15:52:15.626 | INFO     | src.retrieval.hybrid_search:search:104 -   [Profile] Supabase Hybrid RPC: 0.44s
2026-08-07 15:52:15.627 | INFO     | src.retrieval.hybrid_search:search:159 - Hybrid search selesai: 20 results
2026-08-07 15:52:15.627 | INFO     | src.retrieval.hybrid_search:search:161 -   Top: pi-026 | hybrid=0.0115
2026-08-07 15:52:15.650 | INFO     | src.retrieval.parent_child:fetch_parents:47 - De-duplikasi: 20 children → 16 unique parents
2026-08-07 15:52:15.889 | INFO     | src.retrieval.parent_child:fetch_parents:60 -   [Profile] Supabase Parent Fetch: 0.24s
2026-08-07 15:52:15.889 | INFO     | src.retrieval.parent_child:fetch_parents:78 - Fetched 16 parent chunks. Top parent: 'BAB II Sistem Penilaian dan Kelulusan' (score=0.0115)
2026-08-07 15:52:15.889 | INFO     | src.retrieval.reranker:rerank:78 - Cross-encoder scoring 8 pairs...
2026-08-07 15:52:17.232 | INFO     | src.retrieval.reranker:rerank:88 - Reranking done: 8 → 5 documents. Top score: -4.2245, Bottom score: -6.9653
2026-08-07 15:52:17.232 | INFO     | src.retrieval.pipeline:run_retrieval:136 - 
========== Retrieval Summary ==========
Retrieved Parents : 8
After Threshold   : 0
Top Score         : -4.22
Reason            : Minimum Evidence Triggered
LLM Mode          : Conversation (Empty Context)
=======================================
2026-08-07 15:52:17.233 | INFO     | src.retrieval.pipeline:run_retrieval:138 - ⏱️ [Retrieval Pipeline] Total: 3.48s | Parse: 0.00s | Search: 1.87s | Fetch: 0.26s | Rerank: 1.34s
2026-08-07 15:52:17.233 | DEBUG    | src.services.session_store:load_memory:76 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b loaded from cache
2026-08-07 15:52:17.233 | INFO     | src.generation.chain:invoke_with_history:201 - Generating answer for: 'kalau ipk saya dibawah 3,25 bagaimana?' (history: 2 messages)
2026-08-07 15:52:17.233 | INFO     | src.generation.chain:invoke_with_history:209 - Minimum Evidence Triggered. Continuing to LLM with empty context for conversation handling.
2026-08-07 15:52:19.305 | INFO     | src.generation.chain:invoke_with_history:253 - 
========== PROMPT PROFILE ==========
System Prompt     : 246 tokens
History           : 228 tokens
Retrieved Context : 128 tokens
User Query        : 13 tokens
------------------------------------
Total Input       : 615 tokens (approx)
Output            : 64 tokens
====================================
2026-08-07 15:52:19.305 | SUCCESS  | src.generation.chain:invoke_with_history:260 - Generation complete: 311 chars
2026-08-07 15:52:19.305 | INFO     | src.services.ai_services:chat:210 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Generation time [⏱️ 2.07s]
2026-08-07 15:52:19.513 | DEBUG    | src.services.session_store:save_memory:155 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b saved with 4 turns
2026-08-07 15:52:19.514 | INFO     | src.services.ai_services:chat:238 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Total process time [⏱️ 5.76s]
INFO:     127.0.0.1:50203 - "POST /api/ai/chat HTTP/1.1" 200 OK
2026-08-07 15:52:36.715 | INFO     | src.services.ai_services:chat:159 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Question: bedanya sempro dengan semhas apa?
2026-08-07 15:52:36.716 | INFO     | src.services.ai_services:chat:190 - 🔍 [Cache Miss] Running retrieval for: 'bedanya sempro dengan semhas apa?'
2026-08-07 15:52:36.716 | DEBUG    | src.retrieval.self_query:extract_query_components:241 - Menganalisis query: 'bedanya sempro dengan semhas apa?'
2026-08-07 15:52:36.716 | INFO     | src.retrieval.self_query:extract_query_components:254 - Query dianalisis » semantic: 'bedanya sempro dengan semhas apa?' | filters: {} | confidence: low
2026-08-07 15:52:36.750 | INFO     | src.retrieval.hybrid_search:search:83 - Hybrid search: 'bedanya sempro dengan semhas apa?' | filters: {} | top_k: 20
2026-08-07 15:52:37.265 | INFO     | src.retrieval.hybrid_search:search:88 -   [Profile] Query Embedding: 0.51s
2026-08-07 15:52:37.606 | INFO     | src.retrieval.hybrid_search:search:104 -   [Profile] Supabase Hybrid RPC: 0.34s
2026-08-07 15:52:37.606 | INFO     | src.retrieval.hybrid_search:search:159 - Hybrid search selesai: 20 results
2026-08-07 15:52:37.606 | INFO     | src.retrieval.hybrid_search:search:161 -   Top: non-skripsi-230 | hybrid=0.0115
2026-08-07 15:52:37.623 | INFO     | src.retrieval.parent_child:fetch_parents:47 - De-duplikasi: 20 children → 17 unique parents
2026-08-07 15:52:37.885 | INFO     | src.retrieval.parent_child:fetch_parents:60 -   [Profile] Supabase Parent Fetch: 0.26s
2026-08-07 15:52:37.885 | INFO     | src.retrieval.parent_child:fetch_parents:78 - Fetched 17 parent chunks. Top parent: 'SIMBOL:' (score=0.0115)
2026-08-07 15:52:37.886 | INFO     | src.retrieval.reranker:rerank:78 - Cross-encoder scoring 8 pairs...
2026-08-07 15:52:39.305 | INFO     | src.retrieval.reranker:rerank:88 - Reranking done: 8 → 5 documents. Top score: -6.1379, Bottom score: -10.3904
2026-08-07 15:52:39.305 | INFO     | src.retrieval.pipeline:run_retrieval:136 - 
========== Retrieval Summary ==========
Retrieved Parents : 8
After Threshold   : 0
Top Score         : -6.14
Reason            : Minimum Evidence Triggered
LLM Mode          : Conversation (Empty Context)
=======================================
2026-08-07 15:52:39.306 | INFO     | src.retrieval.pipeline:run_retrieval:138 - ⏱️ [Retrieval Pipeline] Total: 2.59s | Parse: 0.00s | Search: 0.89s | Fetch: 0.28s | Rerank: 1.42s
2026-08-07 15:52:39.306 | DEBUG    | src.services.session_store:load_memory:76 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b loaded from cache
2026-08-07 15:52:39.307 | INFO     | src.generation.chain:invoke_with_history:201 - Generating answer for: 'bedanya sempro dengan semhas apa?' (history: 4 messages)
2026-08-07 15:52:39.307 | INFO     | src.generation.chain:invoke_with_history:209 - Minimum Evidence Triggered. Continuing to LLM with empty context for conversation handling.
2026-08-07 15:52:43.512 | INFO     | src.generation.chain:invoke_with_history:253 - 
========== PROMPT PROFILE ==========
System Prompt     : 246 tokens
History           : 77 tokens
Retrieved Context : 128 tokens
User Query        : 9 tokens
------------------------------------
Total Input       : 460 tokens (approx)
Output            : 74 tokens
====================================
2026-08-07 15:52:43.512 | SUCCESS  | src.generation.chain:invoke_with_history:260 - Generation complete: 355 chars
2026-08-07 15:52:43.512 | INFO     | src.services.ai_services:chat:210 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Generation time [⏱️ 4.20s]
2026-08-07 15:52:43.710 | DEBUG    | src.services.session_store:save_memory:155 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b saved with 6 turns
2026-08-07 15:52:43.710 | INFO     | src.services.ai_services:chat:238 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Total process time [⏱️ 7.00s]
INFO:     127.0.0.1:53438 - "POST /api/ai/chat HTTP/1.1" 200 OK
2026-08-07 15:52:56.794 | INFO     | src.services.ai_services:chat:159 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Question: sempro itu apa?
2026-08-07 15:52:56.794 | DEBUG    | src.services.session_store:load_memory:76 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b loaded from cache
2026-08-07 15:53:17.642 | INFO     | src.generation.intent_classifier.reformulator:reformulate_query:129 - 🔄 [Rewrite] LLM: 'sempro itu apa?' → 'Apa yang dimaksud dengan sempro?'
2026-08-07 15:53:17.642 | INFO     | src.services.ai_services:chat:180 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] [Rewrite] LLM: 'sempro itu apa?' → 'Apa yang dimaksud dengan sempro?' [⏱️ 20.85s]
2026-08-07 15:53:17.642 | INFO     | src.services.ai_services:chat:190 - 🔍 [Cache Miss] Running retrieval for: 'Apa yang dimaksud dengan sempro?'
2026-08-07 15:53:17.642 | DEBUG    | src.retrieval.self_query:extract_query_components:241 - Menganalisis query: 'Apa yang dimaksud dengan sempro?'
2026-08-07 15:53:17.643 | INFO     | src.retrieval.self_query:extract_query_components:254 - Query dianalisis » semantic: 'Apa yang dimaksud dengan sempro?' | filters: {} | confidence: low
2026-08-07 15:53:17.700 | INFO     | src.retrieval.hybrid_search:search:83 - Hybrid search: 'Apa yang dimaksud dengan sempro?' | filters: {} | top_k: 20
2026-08-07 15:53:18.564 | INFO     | src.retrieval.hybrid_search:search:88 -   [Profile] Query Embedding: 0.86s
2026-08-07 15:53:18.889 | INFO     | src.retrieval.hybrid_search:search:104 -   [Profile] Supabase Hybrid RPC: 0.32s
2026-08-07 15:53:18.890 | INFO     | src.retrieval.hybrid_search:search:159 - Hybrid search selesai: 20 results
2026-08-07 15:53:18.890 | INFO     | src.retrieval.hybrid_search:search:161 -   Top: non-skripsi-230 | hybrid=0.0115
2026-08-07 15:53:18.909 | INFO     | src.retrieval.parent_child:fetch_parents:47 - De-duplikasi: 20 children → 17 unique parents
2026-08-07 15:53:19.147 | INFO     | src.retrieval.parent_child:fetch_parents:60 -   [Profile] Supabase Parent Fetch: 0.24s
2026-08-07 15:53:19.148 | INFO     | src.retrieval.parent_child:fetch_parents:78 - Fetched 17 parent chunks. Top parent: 'SIMBOL:' (score=0.0115)
2026-08-07 15:53:19.148 | INFO     | src.retrieval.reranker:rerank:78 - Cross-encoder scoring 8 pairs...
2026-08-07 15:53:20.569 | INFO     | src.retrieval.reranker:rerank:88 - Reranking done: 8 → 5 documents. Top score: -8.9222, Bottom score: -9.7654
2026-08-07 15:53:20.569 | INFO     | src.retrieval.pipeline:run_retrieval:136 - 
========== Retrieval Summary ==========
Retrieved Parents : 8
After Threshold   : 0
Top Score         : -8.92
Reason            : Minimum Evidence Triggered
LLM Mode          : Conversation (Empty Context)
=======================================
2026-08-07 15:53:20.570 | INFO     | src.retrieval.pipeline:run_retrieval:138 - ⏱️ [Retrieval Pipeline] Total: 2.93s | Parse: 0.00s | Search: 1.25s | Fetch: 0.26s | Rerank: 1.42s
2026-08-07 15:53:20.570 | INFO     | src.generation.chain:invoke_with_history:201 - Generating answer for: 'sempro itu apa?' (history: 6 messages)
2026-08-07 15:53:20.570 | INFO     | src.generation.chain:invoke_with_history:209 - Minimum Evidence Triggered. Continuing to LLM with empty context for conversation handling.
2026-08-07 15:53:22.736 | INFO     | src.generation.chain:invoke_with_history:253 - 
========== PROMPT PROFILE ==========
System Prompt     : 246 tokens
History           : 83 tokens
Retrieved Context : 128 tokens
User Query        : 5 tokens
------------------------------------
Total Input       : 462 tokens (approx)
Output            : 59 tokens
====================================
2026-08-07 15:53:22.737 | SUCCESS  | src.generation.chain:invoke_with_history:260 - Generation complete: 300 chars
2026-08-07 15:53:22.737 | INFO     | src.services.ai_services:chat:210 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Generation time [⏱️ 2.17s]
2026-08-07 15:53:22.923 | DEBUG    | src.services.session_store:save_memory:155 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b saved with 8 turns
2026-08-07 15:53:22.923 | INFO     | src.services.ai_services:chat:238 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Total process time [⏱️ 26.13s]
INFO:     127.0.0.1:60996 - "POST /api/ai/chat HTTP/1.1" 200 OK
2026-08-07 15:53:41.536 | INFO     | src.services.ai_services:chat:159 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Question: tujuan dari skripsi apa?
2026-08-07 15:53:41.536 | INFO     | src.services.ai_services:chat:190 - 🔍 [Cache Miss] Running retrieval for: 'tujuan dari skripsi apa?'
2026-08-07 15:53:41.537 | DEBUG    | src.retrieval.self_query:extract_query_components:241 - Menganalisis query: 'tujuan dari skripsi apa?'
2026-08-07 15:53:41.537 | INFO     | src.retrieval.self_query:extract_query_components:254 - Query dianalisis » semantic: 'tujuan dari skripsi apa?' | filters: {'source': 'Panduan Penyusunan Skripsi Cetak'} | confidence: low
2026-08-07 15:53:41.576 | INFO     | src.retrieval.hybrid_search:search:83 - Hybrid search: 'tujuan dari skripsi apa?' | filters: {'source': 'Panduan Penyusunan Skripsi Cetak'} | top_k: 20
2026-08-07 15:53:42.196 | INFO     | src.retrieval.hybrid_search:search:88 -   [Profile] Query Embedding: 0.62s
2026-08-07 15:53:42.536 | INFO     | src.retrieval.hybrid_search:search:104 -   [Profile] Supabase Hybrid RPC: 0.34s
2026-08-07 15:53:42.536 | INFO     | src.retrieval.hybrid_search:search:159 - Hybrid search selesai: 20 results
2026-08-07 15:53:42.536 | INFO     | src.retrieval.hybrid_search:search:161 -   Top: skripsi-054 | hybrid=0.0115
2026-08-07 15:53:42.551 | INFO     | src.retrieval.parent_child:fetch_parents:47 - De-duplikasi: 20 children → 16 unique parents
2026-08-07 15:53:42.757 | INFO     | src.retrieval.parent_child:fetch_parents:60 -   [Profile] Supabase Parent Fetch: 0.21s
2026-08-07 15:53:42.757 | INFO     | src.retrieval.parent_child:fetch_parents:78 - Fetched 16 parent chunks. Top parent: '3.2 Bentuk Laporan Tugas Akhir Skripsi' (score=0.0115)
2026-08-07 15:53:42.757 | INFO     | src.retrieval.reranker:rerank:78 - Cross-encoder scoring 8 pairs...
2026-08-07 15:53:44.021 | INFO     | src.retrieval.reranker:rerank:88 - Reranking done: 8 → 5 documents. Top score: 1.4173, Bottom score: -0.9119
2026-08-07 15:53:44.021 | INFO     | src.retrieval.pipeline:run_retrieval:136 - 
========== Retrieval Summary ==========
Retrieved Parents : 8
After Threshold   : 5
Top Score         : 1.42
Reason            : Adaptive Relative Gap
LLM Mode          : RAG
=======================================
2026-08-07 15:53:44.022 | INFO     | src.retrieval.pipeline:run_retrieval:138 - ⏱️ [Retrieval Pipeline] Total: 2.48s | Parse: 0.00s | Search: 1.00s | Fetch: 0.22s | Rerank: 1.26s
2026-08-07 15:53:44.022 | DEBUG    | src.services.session_store:load_memory:76 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b loaded from cache
2026-08-07 15:53:44.022 | INFO     | src.generation.chain:invoke_with_history:201 - Generating answer for: 'tujuan dari skripsi apa?' (history: 6 messages)
2026-08-07 15:53:50.104 | INFO     | src.generation.chain:invoke_with_history:253 - 
========== PROMPT PROFILE ==========
System Prompt     : 246 tokens
History           : 224 tokens
Retrieved Context : 2707 tokens
User Query        : 8 tokens
------------------------------------
Total Input       : 3185 tokens (approx)
Output            : 207 tokens
====================================
2026-08-07 15:53:50.104 | SUCCESS  | src.generation.chain:invoke_with_history:260 - Generation complete: 892 chars
2026-08-07 15:53:50.104 | INFO     | src.services.ai_services:chat:210 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Generation time [⏱️ 6.08s]
2026-08-07 15:53:50.390 | DEBUG    | src.services.session_store:save_memory:155 - Session 8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b saved with 10 turns
2026-08-07 15:53:50.390 | INFO     | src.services.ai_services:chat:238 - [session=8e6b3bd7-bdc0-4bfc-8ad0-650957834f5b] Total process time [⏱️ 8.85s]
INFO:     127.0.0.1:50965 - "POST /api/ai/chat HTTP/1.1" 200 OK
INFO:     127.0.0.1:61588 - "OPTIONS /api/sessions/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:56169 - "OPTIONS /api/sessions/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:61588 - "GET /api/sessions/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:56169 - "GET /api/sessions/ HTTP/1.1" 200 OK
```

## Frontend Log (Next.js Turbopack)
```log
> frontend@0.1.0 dev
> next dev

⚠ Port 3000 is in use by process 15220, using available port 3001 instead.
▲ Next.js 16.2.12 (Turbopack)
- Local:         http://localhost:3001
- Network:       http://192.168.156.1:3001
- Environments: .env.local, .env
✓ Ready in 3.3s

 GET /chat 200 in 916ms (next.js: 502ms, application-code: 414ms)
 GET /riwayat 200 in 127ms (next.js: 66ms, application-code: 61ms)
 GET /riwayat 200 in 118ms (next.js: 7ms, application-code: 112ms)
 GET /chat 200 in 48ms (next.js: 5ms, application-code: 43ms)
 GET /chat 200 in 42ms (next.js: 6ms, application-code: 36ms)
 GET /riwayat 200 in 47ms (next.js: 7ms, application-code: 40ms)
 GET /riwayat 200 in 16ms (next.js: 4ms, application-code: 11ms)
 GET /riwayat 200 in 39ms (next.js: 4ms, application-code: 35ms)
```
