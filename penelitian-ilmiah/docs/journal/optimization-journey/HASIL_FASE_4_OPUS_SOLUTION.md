# ✅ HASIL FASE 4: OPUS 4.6 SOLUTION IMPLEMENTATION

**Tanggal**: 2026-05-01 15:00
**Source**: Claude Opus 4.6 via Antigravity
**Target**: Increase Answer Relevancy from 0.7328 → 0.85+ (+11.7%)

---

## 🔑 CRITICAL DISCOVERIES BY OPUS

### **1. Pipeline Inconsistency Bug** 🐛

**Root Cause Found**:
- **Test script** (`test_low_ar_questions.py`): Uses `HybridSearcher.search(question)` with **NO FILTERS**
- **Full evaluation** (`main.py`): Uses `extract_query_components()` which applies **SECTION FILTERS**

**Why this matters**:
- Questions like "Apa saja elemen sampul depan PI?" get filtered to wrong section (e.g., BAB IV instead of Lampiran)
- Retrieval misses the relevant chunks
- LLM answers "tidak ditemukan" even though info exists

**This explains the inconsistency**: Same 3 questions pass in test but fail in full evaluation!

---

### **2. Data-Driven AR Insights** 📊

Opus analyzed the evaluation results and found clear patterns:

**Word Count vs AR**:
| Word Range | Count | Avg AR | Insight |
|---|---|---|---|
| 0-10 words | 3 | **1.0000** | Ultra-short = perfect AR |
| 10-20 words | 36 | 0.6974 | Sweet spot |
| 20-30 words | 32 | 0.7759 | Still good |
| 30-50 words | 18 | 0.7053 | Getting verbose |
| 50-100 words | 5 | 0.6509 | Too long |

**Question Type vs AR**:
| Question Type | Count | Avg AR | Insight |
|---|---|---|---|
| "Berapa..." | 33 | **0.8729** | Factual questions score high |
| "Siapa..." | 2 | 0.8445 | Identity questions good |
| "Apa yang..." | 12 | 0.7448 | Moderate |
| "Apa isi..." | 5 | 0.6693 | Content questions harder |
| "Bagaimana..." | 10 | 0.5734 | Procedural questions hard |
| "Apa saja..." | 8 | **0.5114** | List questions worst |

**Format vs AR**:
| Format | Count | Avg AR | Insight |
|---|---|---|---|
| Paragraph | 90 | **0.7410** | Preferred format |
| List (starts with `-` or `1.`) | 4 | 0.5493 | RAGAS penalizes lists |

**Preamble Impact**:
| Pattern | Avg AR With | Avg AR Without | Impact |
|---|---|---|---|
| Contains "BAB " | 0.6700 | 0.7403 | -9.5% |
| Contains "sesuai dengan" | 0.6810 | 0.7345 | -7.3% |

---

### **3. The "Echo Principle"** 🔄

**How RAGAS AR works**:
1. Generate N questions FROM the answer using LLM
2. Compute cosine similarity between generated questions and original question
3. Average these similarities

**Key insight**: Answer MUST contain question's key terms to score well!

**Examples**:
- ❌ Question: "Berapa spasi?" → Answer: "1,5 spasi" → AR: 0.52 (missing "naskah utama PI")
- ✅ Question: "Berapa spasi?" → Answer: "**Spasi naskah utama PI** adalah 1,5" → AR: 0.85+ (echoes key terms)

- ❌ Question: "Bagaimana cara menulis referensi buku?" → Answer: "Penulis, A. A. (Tahun)..." → AR: 0.44 (template doesn't echo "buku")
- ✅ Question: "Bagaimana cara menulis referensi buku?" → Answer: "**Referensi buku** ditulis: Penulis, A. A. (Tahun)..." → AR: 0.70+ (echoes "referensi buku")

---

## 📋 IMPLEMENTED CHANGES

### **Part 1: Prompt Redesign** ✅

**File**: `src/generation/chain.py`

#### **New SYSTEM_PROMPT** (Simplified & Focused):
```python
SYSTEM_PROMPT = """Anda adalah asisten akademik STMIK Widya Cipta Dharma.

ATURAN UTAMA:
1. Jawab HANYA berdasarkan konteks dokumen yang diberikan.
2. DILARANG menambahkan informasi dari pengetahuan umum.
3. Jawab LANGSUNG tanpa pembuka ("Berdasarkan...", "Menurut...", "Sesuai...").
4. DILARANG menyebut "Dokumen 1", "BAB II", atau sumber apapun.
5. BACA SELURUH konteks dengan teliti sebelum menyimpulkan tidak ada.
6. Informasi PASTI ada jika kata kunci relevan ditemukan di konteks.

ATURAN FOKUS JAWABAN (SANGAT PENTING):
7. Jawaban HARUS mengandung kata kunci utama dari pertanyaan.
8. JANGAN menambahkan informasi yang TIDAK ditanyakan.
9. Untuk pertanyaan faktual: jawab dalam 1-2 kalimat (10-20 kata).
10. Untuk pertanyaan daftar: gunakan poin (-) tanpa pengantar.
11. Untuk pertanyaan format/cara: sertakan JENIS SPESIFIK yang ditanya."""
```

**Key changes**:
- ✅ Removed verbose anti-"tidak ditemukan" instructions
- ✅ Added explicit "echo principle" (rule #7)
- ✅ Simplified format rules
- ✅ Reduced target word counts (10-20 vs 15-25)

#### **New HUMAN_PROMPT** (Echo-Focused):
```python
HUMAN_PROMPT = """KONTEKS DOKUMEN:
{context}

---

PERTANYAAN: {question}

ATURAN MENJAWAB:
1. Jawab LANGSUNG - kalimat pertama harus langsung menjawab pertanyaan.

2. ULANGI kata kunci pertanyaan di jawaban agar fokus.
   Contoh: "Berapa spasi naskah PI?" → "Spasi naskah utama PI adalah 1,5."
   Contoh: "Bagaimana cara menulis referensi buku?" → "Referensi buku ditulis: Penulis, A. A. (Tahun)..."
   Contoh: "Apa saja elemen sampul depan PI?" → "Elemen sampul depan PI meliputi: ..."

3. JANGAN tambahkan info yang tidak ditanyakan.

4. JANGAN gunakan frasa "adalah sebagai berikut:", "berdasarkan", "sesuai dengan".

5. Jika informasi ada di konteks, JAWAB. Hanya jawab "tidak ditemukan" jika konteks BENAR-BENAR tidak mengandung informasi relevan.

JAWABAN:"""
```

**Key changes**:
- ✅ Removed massive keyword search instructions (belong in retrieval)
- ✅ Added explicit "echo principle" with 3 concrete examples
- ✅ Simplified to 5 core rules
- ✅ Much shorter and more focused

---

### **Part 2: Post-Processing** ✅

**File**: `src/generation/chain.py`

Added `_postprocess_answer()` function:
```python
def _postprocess_answer(answer: str) -> str:
    """Remove preambles and meta-references that hurt Answer Relevancy."""
    
    # Remove common preamble patterns
    preamble_patterns = [
        r'^Berdasarkan (?:dokumen|panduan|konteks)[^,]*,\s*',
        r'^Menurut (?:dokumen|panduan)[^,]*,\s*',
        r'^Sesuai dengan (?:dokumen|panduan)[^,]*,\s*',
        r'^Dalam (?:dokumen|panduan)[^,]*,\s*',
    ]
    
    # Remove "adalah sebagai berikut:" and keep content after it
    answer = re.sub(r'^[^:]*adalah sebagai berikut\s*:\s*\n?', '', answer, flags=re.IGNORECASE)
    
    # Remove BAB/Dokumen references inline
    answer = re.sub(r'\b(?:BAB\s+[IVX]+|Dokumen\s+\d+)\b', '', answer)
    
    # Clean up extra whitespace
    answer = re.sub(r'\n{3,}', '\n\n', answer)
    answer = re.sub(r'  +', ' ', answer)
    
    return answer.strip()
```

**Applied to**:
- `RAGChain.invoke()` - after LLM generation
- `generate_answer()` - after LLM generation

**Impact**: Safety net to catch preambles that slip through prompt

---

### **Part 3: Pipeline Consistency Fix** ✅

**File**: `main.py`

**Changed**:
```python
# OLD (FASE 3):
context_str = fetcher.format_context(reranked_parents)

# NEW (FASE 4):
from src.generation.chain import _format_context
context_str = _format_context(reranked_parents)
```

**Why**:
- `fetcher.format_context()` adds metadata like `"── Dokumen 1 ──\nBagian: BAB V\n..."`
- This metadata **leaks into LLM's answer** as "BAB V" references
- "BAB V" references reduce AR (data shows -9.5% impact)
- `_format_context()` has cleaner formatting without metadata leakage

---

### **Part 4: max_tokens Reduction** ✅

**File**: `src/generation/chain.py`

**Changed**:
```python
# OLD (FASE 3):
max_tokens=1200

# NEW (FASE 4):
max_tokens=600  # Force conciseness
```

**Reasoning**:
- Current avg answer: 24.7 words ≈ ~50 tokens
- 600 tokens is still generous (allows up to ~300 words)
- But prevents rambling and forces LLM to be concise
- Data shows: shorter answers = higher AR

---

## 📊 EXPECTED IMPACT

### **Opus's Estimates**:

| Change | Expected AR Gain | Confidence | Risk |
|---|---|---|---|
| Prompt redesign (echo principle) | +4-6% | Medium-High | Low |
| Post-processing (preamble removal) | +2-3% | High | Very Low |
| Pipeline consistency fix | +1-2% | Medium | Low |
| max_tokens reduction | +1-2% | Medium | Low |
| **Total estimated** | **+8-13%** | | |

### **Projected Results**:

| Metric | Current | Projected | Threshold | Status |
|---|---|---|---|---|
| Faithfulness | 0.9184 | 0.90-0.92 | 0.85 | ✅ PASS |
| Answer Relevancy | 0.7328 | **0.81-0.86** | 0.85 | ⚠️ BORDERLINE to ✅ |
| Context Precision | 0.8628 | 0.86-0.87 | 0.80 | ✅ PASS |
| Overall | 0.8380 | **0.86-0.88** | 0.85 | ✅ PASS |

---

## ⚠️ KNOWN LIMITATIONS

### **The 4 Reference-Format Questions**

Opus identified that these 4 questions have **structural AR problems**:
1. "Bagaimana cara menulis referensi buku dalam daftar pustaka PI?" (AR: 0.43)
2. "Bagaimana cara menulis referensi jurnal dalam daftar pustaka PI?" (AR: 0.47)
3. "Bagaimana cara menulis referensi website dalam daftar pustaka PI?" (AR: 0.46)
4. "Bagaimana cara menulis referensi yang tidak dipublikasikan dalam daftar pustaka PI?" (AR: 0.44)

**Why they're hard**:
- Answer is a template: `"Penulis, A. A. (Tahun). Judul..."`
- Template could answer ANY "how to cite" question
- RAGAS generates questions from template that don't specifically match "buku" vs "jurnal"
- Even with perfect prompting, these will likely stay at 0.55-0.70 AR

**Mitigation**:
- Echo principle helps: `"Referensi **buku** ditulis: Penulis, A. A. (Tahun)..."`
- But still structurally challenging for RAGAS

---

## 🚀 NEXT STEPS

### **1. Test with 20 Lowest AR Questions**
```bash
python test_low_ar_questions.py
```

**Expected**:
- 'Tidak ditemukan' answers: 0/20 (maintain)
- Average word count: 15-25 words (down from 31.1)
- Answers echo question key terms

### **2. Run Full Evaluation**
```bash
python main.py --evaluate-no-gt --dataset both
```

**Expected**:
- AR: 0.81-0.86 (up from 0.7328)
- Overall: 0.86-0.88 (up from 0.8380)
- Faithfulness: 0.90-0.92 (maintain ≥0.85)

### **3. Analyze Results**
- Check if 3 "tidak ditemukan" are fixed
- Check AR distribution (should shift higher)
- Check answer lengths (should be shorter)
- Check for "echo principle" in answers

---

## 💡 KEY INSIGHTS FROM OPUS

1. **Pipeline bugs matter** - Test script vs full eval inconsistency was a real bug, not just randomness

2. **Data-driven optimization** - Opus analyzed actual evaluation data to find patterns we missed

3. **The echo principle** - RAGAS AR is about whether answer contains question's key terms, not just focus

4. **Shorter is better** - 0-10 words = AR 1.0, 50-100 words = AR 0.65

5. **Question type matters** - "Berapa..." = AR 0.87, "Apa saja..." = AR 0.51

6. **Structural limitations exist** - Some questions (reference formats) are inherently hard for RAGAS

---

## 🎯 CONFIDENCE LEVEL

**Opus's assessment**: Medium-High confidence for +8-13% AR improvement

**Realistic target**: AR 0.81-0.86 (borderline to pass)

**Honest assessment**: Even with all optimizations, reaching AR 0.85 consistently is challenging due to:
- 4 reference-format questions (structural AR floor)
- RAGAS's sensitivity to answer format
- Trade-off between AR and Faithfulness

**But**: Overall score should comfortably pass 0.85 threshold! 🎉

---

## 📝 FILES MODIFIED

1. ✅ `src/generation/chain.py` - New prompts, post-processing, max_tokens reduction
2. ✅ `main.py` - Pipeline consistency fix (use `_format_context`)

---

## 🙏 THANK YOU OPUS 4.6!

Opus provided:
- ✅ Deep root cause analysis (pipeline bug)
- ✅ Data-driven insights (word count, question type, format patterns)
- ✅ The "echo principle" (key breakthrough)
- ✅ Specific, actionable code changes
- ✅ Realistic expectations (structural limitations)

**Ready to test!** 🚀
