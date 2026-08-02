# Trace Nyata: "Apa syarat untuk mengambil KKP?"

Dokumen ini menelusuri **setiap langkah nyata** yang terjadi di sistem saat user mengirim pertanyaan tersebut untuk pertama kalinya.

---

## Skenario
- **User:** Pengguna Telegram baru, belum pernah tanya sebelumnya
- **Pertanyaan:** `"Apa syarat untuk mengambil KKP?"`
- **Session ID:** `"123456789"` (Telegram user ID)

---

## LANGKAH 1 — Telegram Menerima Pesan

```
Telegram Server
  → POST /api/telegram/webhook
  → Verifikasi X-Telegram-Bot-Api-Secret-Token ✓
  → Update.de_json(data)
  → bot_app.process_update(update)
  → handle_text_chat() dipanggil
```

**Data di titik ini:**
```python
text     = "Apa syarat untuk mengambil KKP?"
user_id  = "123456789"
chat_id  = 123456789
```

---

## LANGKAH 2 — Cek Kuota Harian

```sql
-- Supabase RPC dipanggil:
increment_quota_if_under_limit(
  p_user_id     = "123456789",
  p_date        = "2026-05-19",
  p_daily_limit = 13
)
-- Baris baru di user_quotas → message_count = 1
-- Return: TRUE (masih di bawah limit)
```

**Bot mengirim pesan loading:** `"⏳ Sedang mencari jawaban..."`

---

## LANGKAH 3 — Masuk ke ai_services.chat()

```python
chat(query="Apa syarat untuk mengambil KKP?", session_id="123456789")
```

- Query tidak kosong ✓
- Session ID ada ✓
- `get_or_create_memory("123456789")` → **buat** ConversationMemory baru
- `memory.add_user_turn("Apa syarat untuk mengambil KKP?")`
- `_turns = [Turn(role="user", content="Apa syarat...")]`

---

## LANGKAH 4 — Klasifikasi Intent

```python
_classifier.classify("Apa syarat untuk mengambil KKP?", memory)
```

**ConversationalDetector:**
- Panjang pesan = 33 karakter → bukan pesan pendek
- Tidak ada pola sapaan → bukan conversational
- → Lanjut

**memory.has_prior_context** = False (tidak ada assistant turn sebelumnya)
- → **Shortcut: NEEDS_RETRIEVAL, confidence=0.99**
- Alasan: "First question needs retrieval"

---

## LANGKAH 5 — Reformulasi Query

```python
reformulate_query("Apa syarat untuk mengambil KKP?", memory)
```

- `memory.is_empty` = False (ada 1 user turn)
- `has_implicit_references("Apa syarat untuk mengambil KKP?")` → cek kata "itu", "tadi", "tersebut", dll.
- **Tidak ada referensi implisit** → **Return pesan asli tanpa perubahan**

`search_query = "Apa syarat untuk mengambil KKP?"`

---

## LANGKAH 6 — Self-Query Parsing

```python
extract_query_components("Apa syarat untuk mengambil KKP?")
```

**Deteksi source:**
- Cek `" kkp "` → ✓ ditemukan di "mengambil KKP?"
- Tidak ada keyword PI
- → `filter["source"] = "Panduan Penyusunan Kuliah Kerja Praktik (KKP) Cetak"`

**Deteksi section:**
- Scan YAML: keyword "syarat" cocok dengan section "BAB II"
- Hitung: 1 keyword cocok → **< 2, tidak cukup** → tidak ada filter section

**Hasil:**
```python
ParsedQuery(
  semantic_query = "Apa syarat untuk mengambil KKP?",
  filters        = {"source": "Panduan KKP Cetak"},
  confidence     = "low"
)
```

---

## LANGKAH 7 — Query Expansion

```python
expand_query_smart("Apa syarat untuk mengambil KKP?")
```

- Scan UPPERCASE: `KKP` ditemukan sebagai token uppercase
- Tambahkan: `"Kuliah Kerja Praktik"` dan `"Kuliah Kerja Praktek"`
- → `"Apa syarat untuk mengambil KKP? Kuliah Kerja Praktik Kuliah Kerja Praktek"`

---

## LANGKAH 8 — Hybrid Search

**Embed query:**
```
OpenAI text-embedding-3-large
Input:  "Apa syarat untuk mengambil KKP? Kuliah Kerja Praktik..."
Output: [0.023, -0.041, 0.187, ...] ← vektor 2000 dimensi
```

**Supabase RPC `hybrid_search`:**
```sql
-- Sub-query FTS:
SELECT id, ROW_NUMBER() AS rank_ix
FROM child_documents
WHERE to_tsvector('indonesian', content)
      @@ websearch_to_tsquery('indonesian', 'Apa syarat KKP Kuliah Kerja Praktik')
ORDER BY ts_rank DESC
LIMIT 60

-- Sub-query Vector:
SELECT id, ROW_NUMBER() AS rank_ix
FROM child_documents
WHERE embedding IS NOT NULL
ORDER BY embedding <=> [0.023, -0.041, ...] ASC
LIMIT 60

-- RRF Fusion:
rrf_score = 0.4 × 1/(60 + rank_fts) + 0.6 × 1/(60 + rank_vec)
```

**Hasil:** 30 child chunks terurut by rrf_score, contoh:
```
child_id="kkp-015" | rrf_score=0.0142 | "Syarat mengambil KKP..."
child_id="kkp-016" | rrf_score=0.0138 | "Mahasiswa harus memenuhi..."
child_id="kkp-003" | rrf_score=0.0091 | "Prosedur pendaftaran KKP..."
...
```

---

## LANGKAH 9 — Parent Fetching

```python
ParentChildFetcher.fetch_parents(30 child results)
```

**De-duplikasi:**
```
kkp-015 → parent_id = "parent-kkp-004"
kkp-016 → parent_id = "parent-kkp-004"  ← sama!
kkp-003 → parent_id = "parent-kkp-001"
...
30 children → 12 unique parent IDs
```

**Query ke Supabase:**
```sql
SELECT * FROM parent_documents
WHERE parent_id IN ('parent-kkp-004', 'parent-kkp-001', ...)
```

**Enrichment:**
```python
parent["best_child_score"] = 0.0142
parent["matched_children"] = ["kkp-015", "kkp-016"]
```

**Sort:** 12 parent diurutkan by best_child_score DESC

---

## LANGKAH 10 — Cross-Encoder Reranking

```python
CrossEncoderReranker.rerank(
  query="Apa syarat untuk mengambil KKP?",
  documents=12_parent_docs
)
```

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Scoring 12 pasangan:**
```
[query, parent-kkp-004 content] → score = 8.73
[query, parent-kkp-001 content] → score = 7.21
[query, parent-kkp-007 content] → score = 4.15
...
```

**Hasil:** Top 8 parent berdasarkan cross-encoder score

---

## LANGKAH 11 — Format Konteks

```python
_format_context(top_8_parents)
```

**Output string:**
```
[Sumber: Buku Panduan KKP] — BAB II — Syarat dan Ketentuan KKP | Relevansi: 8.73

Mahasiswa yang ingin mengambil KKP harus memenuhi syarat berikut:
1. Telah menempuh minimal 100 SKS
2. IPK minimal 2.00
...

---

[Sumber: Buku Panduan KKP] — BAB II — Prosedur Pendaftaran | Relevansi: 7.21

Untuk mendaftar KKP, mahasiswa harus...
```

---

## LANGKAH 12 — LLM Generation

```python
RAGChain.invoke_with_history(
  question="Apa syarat untuk mengambil KKP?",
  context_documents=top_8_parents,
  conversation_history=[]  ← kosong (pertanyaan pertama)
)
```

**Pesan ke LLM:**
```
[SystemMessage] "Anda adalah asisten akademik resmi STMIK..."
[HumanMessage]  "KONTEKS DOKUMEN:\n[Sumber: Buku Panduan KKP]...\n
                 PERTANYAAN: Apa syarat untuk mengambil KKP?\n
                 JAWABAN:"
```

**Jawaban LLM:**
```
Berdasarkan BAB II Ketentuan Umum Buku Panduan KKP, syarat untuk mengambil
Kuliah Kerja Praktik (KKP) di STMIK Widya Cipta Dharma adalah:

1. Telah menempuh minimal 100 SKS
2. IPK minimal 2.00
3. Tidak sedang dalam masa cuti
...
```

---

## LANGKAH 13 — Update Memory & Kirim ke User

```python
memory.add_assistant_turn(
  content=answer,
  retrieved_doc_contents=["isi parent-kkp-004", "isi parent-kkp-001", ...]
)
# _turns sekarang: [Turn(user), Turn(assistant, retrieved_docs=[...])]
```

**Format Telegram:**
```html
🤖 Berdasarkan BAB II Ketentuan Umum Buku Panduan KKP, syarat untuk mengambil
Kuliah Kerja Praktik (KKP) di STMIK Widya Cipta Dharma adalah:

1. Telah menempuh minimal 100 SKS
...

📚 Sumber:
  • BAB II — Syarat dan Ketentuan KKP (Buku Panduan KKP)
  • BAB II — Prosedur Pendaftaran (Buku Panduan KKP)
```

**Bot edit pesan loading** → tampilkan jawaban final

**Background task:** `log_chat_to_db(user_id, username, question, answer)` → tabel `chat_logs`

---

## Ringkasan Timeline

```
0ms    → Telegram webhook diterima
5ms    → Kuota dicek & diincrement
10ms   → Session dibuat, intent = NEEDS_RETRIEVAL
15ms   → Query expansion: tambah "Kuliah Kerja Praktik"
800ms  → OpenAI embed query (network call)
900ms  → Supabase hybrid_search RPC (network call)
950ms  → Supabase fetch parent documents (network call)
1100ms → CrossEncoder rerank (local ML model)
1150ms → Format context string
3500ms → OpenAI LLM generate answer (network call ← paling lama)
3520ms → Memory update
3530ms → Telegram edit_text (network call)
3535ms → Background: log to DB
```
