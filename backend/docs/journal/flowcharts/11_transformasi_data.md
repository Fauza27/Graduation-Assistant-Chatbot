# Transformasi Data per Tahap Pipeline

Dokumen ini menunjukkan **seperti apa bentuk data** di setiap tahap, menggunakan pertanyaan contoh: `"Apa syarat KKP?"`

---

## Tahap 0 — Input Mentah

```python
query      = "Apa syarat untuk mengambil KKP?"
session_id = "123456789"
```

---

## Tahap 1 — Setelah Self-Query Parsing

Data berubah dari string biasa menjadi objek terstruktur dengan filter:

```python
ParsedQuery(
    original_query  = "Apa syarat untuk mengambil KKP?",
    semantic_query  = "Apa syarat untuk mengambil KKP?",  # tidak berubah
    filters         = {
        "source": "Panduan Penyusunan Kuliah Kerja Praktik (KKP) Cetak"
    },
    detected_source  = "Panduan KKP Cetak",
    detected_section = None,   # tidak cukup keyword
    confidence       = "low"
)
```

---

## Tahap 2 — Setelah Query Expansion

```python
# Sebelum:
"Apa syarat untuk mengambil KKP?"

# Sesudah:
"Apa syarat untuk mengambil KKP? Kuliah Kerja Praktik Kuliah Kerja Praktek"
```

---

## Tahap 3 — Setelah Embedding

```python
# Sebelum: string teks
"Apa syarat untuk mengambil KKP? Kuliah Kerja Praktik..."

# Sesudah: vektor 2000 dimensi (representasi semantik)
query_embedding = [0.0231, -0.0412, 0.1874, 0.0093, -0.2341, ...]
#                  ^--- 2000 angka float, merepresentasikan makna kalimat
```

---

## Tahap 4 — Setelah Hybrid Search (Child Results)

```python
# List of HybridSearchResult — potongan kecil dokumen
[
    HybridSearchResult(
        child_id    = "kkp-015",
        parent_id   = "parent-kkp-004",
        hybrid_score = 0.0142,
        document    = Document(
            page_content = "Syarat-syarat untuk mengambil KKP adalah...",
            metadata     = {
                "child_id":  "kkp-015",
                "parent_id": "parent-kkp-004",
                "title":     "Syarat KKP",
                "section":   "BAB II",
                "pages":     ["12", "13"],
                "source":    "Panduan Penyusunan Kuliah Kerja Praktik (KKP) Cetak"
            }
        )
    ),
    HybridSearchResult(
        child_id    = "kkp-016",
        parent_id   = "parent-kkp-004",  # ← parent sama!
        hybrid_score = 0.0138,
        ...
    ),
    # ... 28 child lainnya
]
```

---

## Tahap 5 — Setelah Parent Fetching (De-duplikasi)

```python
# 30 child → 12 unique parent (teks LENGKAP, bukan potongan)
[
    {
        "parent_id":        "parent-kkp-004",
        "title":            "Syarat dan Ketentuan KKP",
        "content":          """BAB II - KETENTUAN UMUM KKP

                              2.1 Syarat Mengambil KKP
                              Mahasiswa yang akan mengambil KKP harus memenuhi
                              persyaratan berikut ini:
                              1. Telah menempuh minimal 100 SKS yang dibuktikan
                                 dengan transkrip nilai.
                              2. IPK kumulatif minimal 2.00
                              3. Tidak sedang dalam masa cuti akademik
                              4. Telah menyelesaikan mata kuliah prasyarat...
                              [teks panjang ~800 kata]""",
        "section":          "BAB II",
        "child_ids":        ["kkp-015", "kkp-016", "kkp-017"],
        "best_child_score": 0.0142,           # ← ditambahkan saat enrichment
        "matched_children": ["kkp-015", "kkp-016"]  # ← yang ditemukan
    },
    {
        "parent_id": "parent-kkp-001",
        "title":     "Prosedur Pendaftaran KKP",
        "content":   "...",
        "best_child_score": 0.0091,
        ...
    },
    # ... 10 parent lainnya
]
```

---

## Tahap 6 — Setelah Cross-Encoder Reranking

```python
# 12 parent → 8 parent terbaik, diurutkan ulang
[
    {
        "parent_id":            "parent-kkp-004",
        "title":                "Syarat dan Ketentuan KKP",
        "content":              "...",
        "cross_encoder_score":  8.73,   # ← skor relevansi dari ML model
        "best_child_score":     0.0142,
        "matched_children":     ["kkp-015", "kkp-016"],
        ...
    },
    {
        "parent_id":           "parent-kkp-001",
        "cross_encoder_score": 7.21,
        ...
    },
    # ... 6 parent lainnya (total 8)
]
```

---

## Tahap 7 — Setelah Format Konteks (Input ke LLM)

```python
context_string = """
[Sumber: Buku Panduan KKP] — BAB II — Syarat dan Ketentuan KKP | Relevansi: 8.73 | Child Chunks: 2

BAB II - KETENTUAN UMUM KKP

2.1 Syarat Mengambil KKP
Mahasiswa yang akan mengambil KKP harus memenuhi persyaratan berikut ini:
1. Telah menempuh minimal 100 SKS yang dibuktikan dengan transkrip nilai.
2. IPK kumulatif minimal 2.00
3. Tidak sedang dalam masa cuti akademik
4. Telah menyelesaikan mata kuliah prasyarat...

---

[Sumber: Buku Panduan KKP] — BAB II — Prosedur Pendaftaran KKP | Relevansi: 7.21 | Child Chunks: 1

Untuk mendaftarkan diri mengikuti KKP, mahasiswa harus:
1. Mengisi formulir pendaftaran di BAAK
2. Melampirkan transkrip nilai terbaru
...

---

[... 6 sumber lainnya ...]
"""
```

---

## Tahap 8 — Output LLM (Jawaban Final)

```python
answer = """Berdasarkan BAB II Ketentuan Umum Buku Panduan KKP, syarat untuk
mengambil Kuliah Kerja Praktik (KKP) di STMIK Widya Cipta Dharma adalah:

1. **Telah menempuh minimal 100 SKS** yang dibuktikan dengan transkrip nilai
2. **IPK kumulatif minimal 2.00**
3. Tidak sedang dalam masa cuti akademik
4. Telah menyelesaikan mata kuliah prasyarat yang ditetapkan

Selain itu, mahasiswa juga perlu mempersiapkan dokumen-dokumen berikut untuk
proses pendaftaran KKP..."""
```

---

## Tahap 9 — Response ke User (API / Telegram)

**REST API Response:**
```json
{
    "answer": "Berdasarkan BAB II Ketentuan Umum...",
    "num_docs": 8,
    "session_id": "123456789",
    "intent": "needs_retrieval",
    "confidence": 0.99,
    "reasoning": "First question needs retrieval",
    "sources": [
        {
            "section":    "BAB II",
            "title":      "Syarat dan Ketentuan KKP",
            "parent_id":  "parent-kkp-004",
            "score":      8.73
        },
        {
            "section":    "BAB II",
            "title":      "Prosedur Pendaftaran KKP",
            "parent_id":  "parent-kkp-001",
            "score":      7.21
        },
        {
            "section":    "BAB III",
            "title":      "...",
            "parent_id":  "parent-kkp-007",
            "score":      4.15
        }
    ]
}
```

---

## Ringkasan Transformasi

```
Input string
    ↓ self_query.py
ParsedQuery + filters
    ↓ query_expansion.py
String diperkaya akronim
    ↓ OpenAI Embeddings
Vektor 2000 dimensi
    ↓ hybrid_search.py (Supabase RPC)
30 HybridSearchResult (child chunks kecil)
    ↓ parent_child.py
12 parent dict (teks lengkap, de-duplikasi)
    ↓ reranker.py
8 parent dict + cross_encoder_score
    ↓ chain.py _format_context()
1 string konteks terformat
    ↓ OpenAI LLM
1 string jawaban
    ↓ _postprocess_answer()
1 string jawaban bersih
    ↓ API / Telegram formatter
JSON response / pesan HTML Telegram
```
