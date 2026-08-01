# Flowchart: `src/retrieval/`

## `pipeline.py` — Koordinator Retrieval

File ini adalah **satu pintu masuk** untuk semua proses pencarian dokumen.

```
run_retrieval(query, rerank_query=None)
       │
       ▼
extract_query_components(query)    ← self_query.py
  Hasil: ParsedQuery {
    semantic_query, filters{source, section}
  }
       │
       ▼
HybridSearcher.search(             ← hybrid_search.py
  query=parsed.semantic_query,
  filters=parsed.filters
)
       │
  Hasil kosong? ──Yes──► Return RetrievalResult(is_empty=True)
       │No
       ▼
ParentChildFetcher.fetch_parents(  ← parent_child.py
  search_results
)
       │
       ▼
CrossEncoderReranker.rerank(       ← reranker.py
  query=rerank_query,
  documents=parent_results
)
       │
  Rerank gagal? ──Yes──► Fallback: ambil top-N tanpa rerank
       │No
       ▼
Return RetrievalResult(
  parent_documents=reranked,
  is_empty=False
)
```

---

## `self_query.py` — Parser Filter Otomatis

Menganalisis pertanyaan untuk menentukan **filter pencarian** (dari buku KKP atau PI? bab apa?).

```
extract_query_components(query)
       │
       ▼
Lowercase query
       │
       ├──► _detect_source()
       │      Cek keyword PI: "penulisan ilmiah", " pi ", dll.
       │      Cek keyword KKP: "kuliah kerja praktik", " kkp ", dll.
       │      ├─ Hanya PI → filter source = Panduan PI
       │      ├─ Hanya KKP → filter source = Panduan KKP
       │      └─ Keduanya / Tidak ada → Tanpa filter source
       │
       └──► _detect_section()
              Load SECTION_KEYWORDS dari config/section_keywords.yaml
              Hitung berapa keyword per section yang cocok di query
              ├─ Best match ≥ 2 keyword → filter section = section tersebut
              └─ < 2 keyword → Tanpa filter section (pencarian luas)
       │
       ▼
Return ParsedQuery(
  semantic_query=query,
  filters={source?, section?},
  confidence="high"/"low"
)
```

---

## `query_expansion.py` — Ekspansi Akronim

Memperluas akronim akademik agar pencarian lebih akurat.

```
expand_query(question)
       │
  Kosong? ──Yes──► Return as-is
       │
       ▼
Scan UPPERCASE_ACRONYMS (case-sensitive):
  PI → Penulisan Ilmiah
  KKP → Kuliah Kerja Praktik
  SKS → Satuan Kredit Semester
  IPK → Indeks Prestasi Kumulatif
  dst.
       │
Scan LONG_FORM_TO_ACRONYM (case-insensitive):
  "penulisan ilmiah" → PI
  "kuliah kerja praktik" → KKP
       │
Ada tambahan? ──Yes──► "PI apa?" → "PI apa? Penulisan Ilmiah"
              ──No───► Return pesan asli
```

---

## `hybrid_search.py` — Pencarian Hybrid BM25 + Vector

```
HybridSearcher.search(query, filters, top_k)
       │
       ▼
expand_query_smart(query)          ← tambah akronim
       │
       ▼
OpenAIEmbeddings.embed_query()     ← ubah teks → vektor 2000 dimensi
       │
       ▼
Supabase RPC: hybrid_search(
  query_embedding,  ← vektor query
  query_text,       ← teks untuk BM25 FTS (bahasa Indonesia)
  match_count=top_k,
  fts_weight=0.4,   ← bobot BM25
  vector_weight=0.6,← bobot vector
  rrf_k=60,         ← parameter Reciprocal Rank Fusion
  filter_section
)
       │
  Hasil kosong? ──Yes──► Fallback: match_child_documents (dense-only)
       │                       │
       │                  Masih kosong? ──Yes──► Return []
       │No
       ▼
Bangun list HybridSearchResult:
  {document, hybrid_score, child_id, parent_id}
       │
Return list hasil pencarian anak (child chunks)
```

> **Cara kerja RRF:** Gabungkan ranking BM25 dan vector secara adil menggunakan formula 1/(k+rank).

---

## `parent_child.py` — Fetch Dokumen Parent

Child chunks hanya potongan kecil. File ini mengambil dokumen **parent** (teks lengkap) yang sesuai.

```
ParentChildFetcher.fetch_parents(search_results)
       │
  Kosong? ──Yes──► Return []
       │
       ▼
Group by parent_id:
  Untuk setiap child result:
    parent_scores[parent_id] = {
      best_score: max hybrid_score,
      matched_children: [child_id, ...]
    }
  (De-duplikasi: N child → M parent unik, M < N)
       │
       ▼
Supabase query:
  SELECT * FROM parent_documents
  WHERE parent_id IN [list parent_id unik]
       │
       ▼
Enrichment setiap parent:
  parent["best_child_score"] = best_score
  parent["matched_children"] = [child_ids]
       │
       ▼
Sort by best_child_score DESC
       │
Return list parent documents
```

---

## `reranker.py` — Pemeringkatan Ulang dengan Cross-Encoder

Memilih dokumen yang **paling relevan** dengan pertanyaan user menggunakan model ML khusus.

```
CrossEncoderReranker.rerank(query, documents)
       │
  Kosong? ──Yes──► Return []
       │
       ▼
_get_model() → load CrossEncoder
  (ms-marco-MiniLM-L-6-v2, lazy-load, shared instance)
       │
       ▼
Bangun pasangan [query, doc_content]:
  Truncate konten ke 2000 karakter
       │
       ▼
model.predict(pairs) → skor relevansi per dokumen
       │
       ▼
Assign doc["cross_encoder_score"] = skor
Sort DESC by skor
Ambil top_n dokumen (default 8)
       │
Return reranked documents
```

> **Mengapa perlu rerank?** Hybrid search mengambil 30 kandidat, tapi LLM hanya butuh 8 terbaik. Cross-encoder lebih akurat menilai relevansi dibanding BM25/vector.

---

## `source_utils.py` — Deteksi Tipe Panduan

```
detect_panduan_type(meta)
  ├─ Tidak ada meta? → Return "PI" (default)
  │
  ├─ Cek field "source":
  │    "kkp" atau "kuliah kerja" dalam source → Return "KKP"
  │    "pi" atau "penulisan ilmiah" dalam source → Return "PI"
  │
  └─ Cek prefix ID:
       parent_id/id mulai "parent-kkp-" atau "kkp-" → Return "KKP"
       parent_id/id mulai "parent-" atau "pi-" → Return "PI"
```

**Peran:** Dipakai `chain.py` dan `chat_handler.py` untuk menampilkan label "Buku Panduan KKP" atau "Buku Panduan PI" di jawaban.
