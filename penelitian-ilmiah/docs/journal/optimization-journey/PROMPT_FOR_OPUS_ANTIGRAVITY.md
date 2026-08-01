# PROMPT FOR CLAUDE OPUS 4.6 (ANTIGRAVITY)

---

## CONTEXT

I'm working on a RAG (Retrieval-Augmented Generation) system for academic guidelines (PI/KKP) evaluation using RAGAS metrics without ground truth. The system has been through 3 phases of optimization and is very close to passing all thresholds, but **Answer Relevancy** remains stubbornly low.

---

## CURRENT EVALUATION RESULTS

**Latest Evaluation** (evaluation_results_no_gt_20260501_145309.json):
- ✅ **Faithfulness**: 0.9184 (threshold: 0.85) - **PASS** (+8.0% margin)
- ❌ **Answer Relevancy**: 0.7328 (threshold: 0.85) - **FAIL** (-13.8% gap)
- ✅ **Context Precision**: 0.8628 (threshold: 0.80) - **PASS** (+7.9% margin)
- ⚠️ **Overall**: 0.8380 (threshold: 0.85) - **FAIL** (-1.4% gap)

**Progress from initial evaluation**:
- Faithfulness: 0.8843 → 0.9184 (+3.9%)
- Answer Relevancy: 0.6335 → 0.7328 (+15.7%) ← biggest improvement but still not enough
- Context Precision: 0.7544 → 0.8628 (+14.4%)
- Overall: 0.7574 → 0.8380 (+10.6%)

---

## THE PROBLEM

### **Critical Issue: Inconsistent "Tidak Ditemukan" Answers**

**Test Script Results** (20 lowest AR questions):
- ✅ 'Tidak ditemukan' answers: **0/20 (0.0%)**
- ✅ All 3 critical questions **ANSWERED CORRECTLY**

**Full Evaluation Results** (94 questions):
- ❌ 'Tidak ditemukan' answers: **3/20 (15.0%)** in lowest AR questions
- ❌ Same 3 questions **STILL "TIDAK DITEMUKAN"**:
  1. "Apa saja elemen yang harus ada di halaman sampul depan PI?"
  2. "Berapa minimal halaman laporan KKP?"
  3. "Apa saja elemen yang harus ada di halaman sampul depan KKP?"

**The information EXISTS in the documents** - test script proves it can be found!

### **Secondary Issue: Low AR Scores on Correct Answers**

17 other questions in top-20 lowest AR have scores 0.44-0.63 despite being correct. Common patterns:
- **Unnecessary preambles**: "Format penulisan adalah sebagai berikut:"
- **Over-elaboration**: Adding info not asked (e.g., asked "Berapa IP minimal?" → answers with IP + SKS requirements)
- **List format for factual questions**: RAGAS penalizes lists for simple factual questions

---

## WHAT WE'VE TRIED (3 PHASES)

### **FASE 1: Quick Wins**
- Optimized prompt to reduce defensiveness
- Added query expansion (20 patterns for specific questions)
- Result: Fixed 5/10 failed questions

### **FASE 2: Medium Improvements**
- Aggressive prompt with specific keyword instructions
- Hybrid reranking (semantic + keyword boost)
- Result: Fixed 6/10 failed questions

### **FASE 3: Answer Format Optimization**
- Enhanced query expansion (removed overly strict conditions)
- Optimized prompt format (direct answers, no preambles, focus)
- Result: Test script shows 0/20 "tidak ditemukan", but full eval still has 3/20

---

## CURRENT IMPLEMENTATION

### **File: src/generation/chain.py**

**Key Settings**:
```python
llm = ChatOpenAI(
    model=settings.llm_model,  # gpt-4o-mini or gpt-4o
    temperature=0,
    max_tokens=1200,
)
```

**SYSTEM_PROMPT** (abbreviated):
```
Anda adalah asisten akademik yang menjawab berdasarkan dokumen panduan resmi.

ATURAN MEMBACA KONTEKS (SANGAT PENTING):
1. BACA SEMUA konteks dokumen dengan SANGAT TELITI sebelum menjawab.
2. Informasi mungkin tersebar di berbagai bagian konteks - cari di SEMUA bagian.
3. JANGAN terlalu cepat menyimpulkan informasi tidak ada.
4. Hanya jawab "tidak ditemukan" jika BENAR-BENAR sudah membaca SEMUA konteks.

ATURAN ANTI-HALUSINASI:
5. HANYA gunakan informasi yang ada dalam konteks dokumen.
6. DILARANG menambahkan informasi dari pengetahuan umum.

ATURAN FORMAT JAWABAN:
7. Jawab LANGSUNG dan FOKUS ke inti pertanyaan tanpa pembuka.
8. DILARANG menyebut "Dokumen 1", "Dokumen 2", nomor BAB, atau sumber.
9. Gunakan Bahasa Indonesia formal yang jelas, lengkap, dan informatif.

PENTING - KUALITAS JAWABAN:
- Jawaban harus AKURAT, LENGKAP, dan FOKUS pada yang ditanyakan.
- Untuk pertanyaan faktual: jawab langsung dengan detail penting (15-25 kata).
- Untuk pertanyaan prosedural: berikan tahapan lengkap (30-50 kata).
```

**HUMAN_PROMPT** (abbreviated):
```
KONTEKS DOKUMEN:
{context}

PERTANYAAN: {question}

INSTRUKSI PENCARIAN INFORMASI:
1. BACA SELURUH KONTEKS dari awal sampai akhir dengan SANGAT TELITI.
2. Cari kata kunci spesifik yang relevan dengan pertanyaan.
3. Jika menemukan kata kunci relevan, PASTI ada informasi yang dicari.
4. HANYA jawab "tidak ditemukan" jika BENAR-BENAR tidak ada kata kunci relevan.

INSTRUKSI FORMAT JAWABAN (FASE 3B - CRITICAL):
1. HINDARI frasa pembuka yang tidak perlu.
2. Jawab LANGSUNG dan FOKUS pada pertanyaan.
3. FOKUS KETAT - JANGAN elaborasi berlebihan.
4. Target panjang: 15-25 kata untuk pertanyaan faktual, 30-50 kata untuk kompleks.
```

---

## YOUR TASK

**I need you to design a solution that will:**

1. **Fix the inconsistency** - Ensure the 3 "tidak ditemukan" questions are answered correctly in full evaluation (not just test script)

2. **Improve AR scores** - Increase Answer Relevancy from 0.7328 to 0.85+ (need +11.7%)

3. **Maintain other metrics** - Don't break Faithfulness (0.9184) or Context Precision (0.8628)

---

## CONSTRAINTS

1. **Cannot change evaluation code** - RAGAS metrics are fixed
2. **Cannot change retrieval significantly** - Hybrid search + reranking is working well (Context Precision 0.8628)
3. **Must use existing LLM** - GPT-4o-mini or GPT-4o (OpenAI)
4. **Must maintain correctness** - Faithfulness must stay ≥ 0.85

---

## WHAT I NEED FROM YOU

Please provide:

### **1. ROOT CAUSE ANALYSIS**
- Why does test script succeed but full evaluation fail for the same 3 questions?
- Why do correct answers still get low AR scores (0.44-0.63)?
- What is RAGAS Answer Relevancy actually measuring that we're missing?

### **2. SPECIFIC SOLUTION**
Provide **exact code changes** for `src/generation/chain.py`:
- Modified SYSTEM_PROMPT (if needed)
- Modified HUMAN_PROMPT (if needed)
- Modified LLM parameters (temperature, max_tokens, etc.)
- Any other changes needed

### **3. IMPLEMENTATION STRATEGY**
- Should we try FASE 3C (ultra-aggressive prompt)?
- Should we try a completely different approach?
- Should we adjust max_tokens, temperature, or other parameters?
- Should we add post-processing to remove preambles?

### **4. EXPECTED IMPACT**
- Estimated AR improvement from your solution
- Risk assessment (could it break other metrics?)
- Confidence level (how sure are you this will work?)

---

## ADDITIONAL CONTEXT

### **Answer Relevancy Metric (RAGAS)**
From RAGAS documentation:
- Measures how focused the answer is on the question
- Uses LLM to generate questions from the answer
- Compares generated questions with original question
- Penalizes: redundancy, incomplete answers, off-topic content
- **Key insight**: AR measures FOCUS, not completeness or correctness

### **Example Low AR Answers**

**Question**: "Berapa IP Kumulatif minimal untuk mengambil PI?"
**Answer**: "IP Kumulatif minimal untuk mengambil PI adalah 2,00, dengan syarat mahasiswa telah menyelesaikan mata kuliah dengan jumlah SKS minimal 100 SKS."
**AR Score**: 0.4427
**Problem**: Added SKS requirement (not asked) → reduced focus

**Question**: "Bagaimana cara menulis referensi jurnal dalam daftar pustaka PI?"
**Answer**: "Format penulisan referensi jurnal dalam daftar pustaka adalah sebagai berikut: [format]. Contoh: [example]"
**AR Score**: 0.5494
**Problem**: Preamble "Format penulisan... adalah sebagai berikut:" → reduced focus

### **Example High AR Answer**

**Question**: "Apa syarat SKS minimal untuk mengambil PI?"
**Answer**: "100 SKS."
**AR Score**: 0.9713 (from earlier test)
**Success**: Direct, focused, exactly what was asked

---

## FILES FOR REFERENCE

**Main files**:
- `src/generation/chain.py` - LLM prompt and generation logic
- `src/retrieval/query_expansion.py` - Query expansion patterns
- `src/retrieval/reranker.py` - Hybrid reranking (semantic + keyword)

**Analysis files**:
- `ANALISIS_HASIL_FASE_3_FINAL.md` - Detailed analysis of current state
- `HASIL_FASE_3_ANSWER_RELEVANCY_FIX.md` - What we tried in FASE 3
- `test_low_ar_questions.py` - Test script that succeeds (0/20 "tidak ditemukan")

---

## QUESTION FOR YOU

**Given all this context, what is the BEST solution to:**
1. Eliminate the 3 "tidak ditemukan" answers consistently
2. Increase Answer Relevancy from 0.7328 to 0.85+
3. Maintain Faithfulness ≥ 0.85 and Context Precision ≥ 0.80

Please provide a detailed, actionable solution with exact code changes and reasoning.

---

## BONUS QUESTION

If you think reaching AR 0.85 is unrealistic given the constraints, please explain:
1. Why is it so hard to optimize AR without breaking other metrics?
2. What is a realistic target for AR in this use case?
3. Should we accept the current state (Overall 0.8380, only 1.4% from threshold)?

Thank you!
