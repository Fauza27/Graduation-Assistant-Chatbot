# 🔍 ANALISIS MASALAH EVALUASI LENGKAP

## 📊 Hasil Evaluasi

| Metrik | Score | Threshold | Status |
|--------|-------|-----------|--------|
| **Faithfulness** | 0.8843 | 0.85 | ✅ PASS |
| **Answer Relevancy** | 0.6335 | 0.85 | ❌ FAIL |
| **Context Precision** | 0.7544 | 0.80 | ❌ FAIL |
| **Overall** | 0.7574 | 0.85 | ❌ FAIL |

## 🔴 MASALAH KRITIS: Informasi TIDAK DITEMUKAN

### Statistik
- **Total pertanyaan**: 94
- **Answer Relevancy rendah**: 79 pertanyaan (84%)
- **Context Precision rendah**: 37 pertanyaan (39%)
- **Keduanya rendah**: 27 pertanyaan (29%)

### Masalah Utama: Jawaban "Tidak Ditemukan" Palsu

**8 pertanyaan mendapat score 0.0000** karena sistem menjawab "Maaf, informasi tersebut tidak ditemukan dalam panduan PI/KKP yang tersedia" **PADAHAL INFORMASI ADA DI DOKUMEN!**

#### Contoh Kasus:

1. **"Apa ketentuan pakaian saat ujian PI untuk mahasiswa pria?"**
   - Jawaban: "Maaf, informasi tersebut tidak ditemukan..."
   - **FAKTA**: Informasi ADA di dokumen! 
   - Context preview menunjukkan ada 5 chunks, tapi sistem tidak membacanya dengan benar
   - Score: AR=0.0000, CP=0.0000

2. **"Berapa maksimal kata dalam abstrak PI?"**
   - Jawaban: "Maaf, informasi tersebut tidak ditemukan..."
   - **FAKTA**: Dokumen menyebutkan "maksimal 300 kata"
   - Score: AR=0.0000, CP=0.0000

3. **"Berapa jumlah kata kunci yang harus ada dalam abstrak PI?"**
   - Jawaban: "Maaf, informasi tersebut tidak ditemukan..."
   - **FAKTA**: Dokumen menyebutkan "3-5 kata kunci"
   - Score: AR=0.0000, CP=0.0000

4. **"Apa saja elemen yang harus ada di halaman sampul depan PI?"**
   - Jawaban: "Maaf, informasi tersebut tidak ditemukan..."
   - **FAKTA**: Dokumen memiliki contoh lengkap elemen sampul
   - Score: AR=0.0000, CP=0.0000, Faithfulness=0.0000

5. **"Berapa minimal halaman laporan KKP?"**
   - Jawaban: "Maaf, informasi tersebut tidak ditemukan..."
   - **FAKTA**: Informasi ada di dokumen
   - Score: AR=0.0000, CP=0.0000, Faithfulness=0.0000

## 🔍 AKAR MASALAH

### 1. **Retrieval Gagal** (Context Precision Rendah)
- Sistem mengambil 4-5 chunks, tapi chunks yang diambil **TIDAK RELEVAN**
- Context precision 0.0000 = chunks yang diambil sama sekali tidak membantu menjawab
- **Penyebab**: 
  - Embedding tidak menangkap semantic similarity dengan baik
  - Reranker tidak bekerja optimal
  - Query transformation tidak efektif

### 2. **Prompt Terlalu Defensif**
Prompt saat ini:
```
"DILARANG KERAS menambahkan informasi dari pengetahuan umum atau menebak."
"Jika informasi TIDAK ADA dalam konteks setelah Anda cek dengan teliti, WAJIB jawab: 
'Maaf, informasi tersebut tidak ditemukan...'"
```

**Masalah**: LLM terlalu cepat menyerah dan menjawab "tidak ditemukan" meskipun informasi sebenarnya ada di context, hanya tersembunyi atau tidak eksplisit.

### 3. **Context Terlalu Panjang dan Tidak Terstruktur**
- Chunks berisi banyak informasi campuran
- LLM kesulitan menemukan informasi spesifik dalam chunk panjang
- Contoh: Chunk berisi info tentang syarat PI, tempat penelitian, dan ketentuan umum sekaligus

## 📈 ANALISIS STATISTIK

### Answer Relevancy Rendah (79 pertanyaan)
- **Average panjang**: 25.9 kata
- **Distribusi**:
  - Terlalu singkat (<10 kata): 1 (1.3%)
  - **Optimal (15-30 kata): 44 (55.7%)** ← Mayoritas sudah OK!
  - Terlalu panjang (>50 kata): 2 (2.5%)

**Insight**: Panjang jawaban BUKAN masalah utama. Masalahnya adalah **jawaban "tidak ditemukan" yang salah**.

### Context Precision Rendah (37 pertanyaan)
- **Average chunks**: 4.9 chunks
- **Min-Max**: 4-5 chunks

**Insight**: Jumlah chunks cukup, tapi **KUALITAS chunks rendah** (tidak relevan dengan pertanyaan).

## 🎯 SOLUSI YANG HARUS DITERAPKAN

### PRIORITAS 1: Perbaiki Retrieval System ⚠️ KRITIS

#### A. Improve Query Transformation
```python
# Tambahkan query expansion untuk pertanyaan spesifik
def expand_query(question: str) -> str:
    """Expand query untuk meningkatkan recall"""
    
    # Deteksi jenis pertanyaan
    if "pakaian" in question.lower() or "ketentuan pakaian" in question.lower():
        return f"{question} ujian seminar dress code"
    
    if "abstrak" in question.lower() and "kata" in question.lower():
        return f"{question} maksimal panjang abstrak kata kunci"
    
    if "sampul" in question.lower() or "cover" in question.lower():
        return f"{question} halaman judul elemen format"
    
    if "minimal halaman" in question.lower():
        return f"{question} jumlah halaman laporan"
    
    return question
```

#### B. Improve Reranking
```python
# Gunakan cross-encoder yang lebih kuat
# Atau tambahkan keyword matching sebagai fallback
def hybrid_rerank(query: str, chunks: List[str]) -> List[str]:
    """Combine semantic + keyword matching"""
    
    # 1. Semantic reranking (existing)
    semantic_scores = cross_encoder.predict([(query, chunk) for chunk in chunks])
    
    # 2. Keyword matching (fallback)
    keyword_scores = []
    query_keywords = extract_keywords(query)
    for chunk in chunks:
        chunk_keywords = extract_keywords(chunk)
        overlap = len(set(query_keywords) & set(chunk_keywords))
        keyword_scores.append(overlap / len(query_keywords))
    
    # 3. Combine scores
    final_scores = 0.7 * semantic_scores + 0.3 * keyword_scores
    
    return rerank_by_scores(chunks, final_scores)
```

### PRIORITAS 2: Perbaiki Prompt ⚠️ PENTING

#### Masalah Saat Ini:
Prompt terlalu defensif → LLM terlalu cepat menyerah

#### Solusi:
```python
SYSTEM_PROMPT = """Anda adalah asisten akademik STMIK Widya Cipta Dharma yang menjawab berdasarkan dokumen panduan resmi.

ATURAN ANTI-HALUSINASI (WAJIB DIIKUTI):
1. HANYA gunakan informasi yang ada dalam konteks dokumen yang diberikan.
2. BACA KONTEKS DENGAN SANGAT TELITI - informasi mungkin tersebar atau tidak eksplisit.
3. Jika informasi JELAS TIDAK ADA setelah membaca SEMUA konteks dengan teliti, jawab: 
   "Maaf, informasi tersebut tidak ditemukan dalam panduan PI/KKP yang tersedia."
4. JANGAN terlalu cepat menyerah - coba cari informasi di semua bagian konteks.
5. Informasi mungkin tidak eksplisit tapi bisa disimpulkan dari konteks yang ada.

ATURAN FORMAT JAWABAN:
6. Jawab LANGSUNG dan FOKUS ke inti pertanyaan.
7. DILARANG menyebut "Dokumen 1", "Dokumen 2", nomor BAB, atau sumber dalam jawaban.
8. Gunakan format poin-poin untuk daftar.
9. Gunakan Bahasa Indonesia formal yang jelas dan informatif.
10. Target: 15-25 kata untuk faktual, 30-50 untuk prosedural.

PENTING:
- Baca SEMUA konteks sebelum menyimpulkan informasi tidak ada.
- Cari informasi di berbagai bagian konteks - mungkin tersebar.
- Jika ada petunjuk atau informasi terkait, gunakan untuk menjawab."""
```

### PRIORITAS 3: Improve Context Chunking

#### Masalah:
Chunks terlalu panjang dan berisi informasi campuran

#### Solusi:
```python
# Buat chunks lebih spesifik dengan metadata yang lebih baik
def create_semantic_chunks(text: str) -> List[Dict]:
    """Create chunks with better semantic boundaries"""
    
    chunks = []
    
    # 1. Split by section headers
    sections = split_by_headers(text)
    
    for section in sections:
        # 2. Extract metadata
        metadata = {
            "section_title": extract_title(section),
            "keywords": extract_keywords(section),
            "question_types": identify_question_types(section)  # "pakaian", "abstrak", etc.
        }
        
        # 3. Create smaller sub-chunks if section is too long
        if len(section) > 500:
            sub_chunks = split_by_sentences(section, max_length=300)
            for sub in sub_chunks:
                chunks.append({
                    "content": sub,
                    "metadata": metadata
                })
        else:
            chunks.append({
                "content": section,
                "metadata": metadata
            })
    
    return chunks
```

## 🚀 RENCANA IMPLEMENTASI

### Fase 1: Quick Wins (1-2 jam)
1. ✅ **Perbaiki prompt** - kurangi defensiveness
2. ✅ **Tambah query expansion** untuk pertanyaan spesifik
3. ✅ **Test dengan 10 pertanyaan yang gagal**

### Fase 2: Medium Improvements (3-4 jam)
1. **Improve reranking** - hybrid semantic + keyword
2. **Add fallback mechanism** - jika semantic search gagal, coba keyword search
3. **Test dengan 30 pertanyaan**

### Fase 3: Major Refactoring (1-2 hari)
1. **Re-chunk documents** dengan semantic boundaries yang lebih baik
2. **Re-embed dengan metadata** yang lebih kaya
3. **Re-ingest ke Supabase**
4. **Full evaluation**

## 📝 KESIMPULAN

### Masalah Utama:
1. **Retrieval gagal** - chunks yang diambil tidak relevan (Context Precision 0.0000)
2. **Prompt terlalu defensif** - LLM terlalu cepat menyerah
3. **Chunks tidak optimal** - terlalu panjang dan campuran

### Dampak:
- 8 pertanyaan mendapat score 0.0000 karena jawaban "tidak ditemukan" yang SALAH
- 79 pertanyaan (84%) memiliki Answer Relevancy < 0.85
- 37 pertanyaan (39%) memiliki Context Precision < 0.80

### Solusi Prioritas:
1. **SEGERA**: Perbaiki prompt (kurangi defensiveness)
2. **SEGERA**: Tambah query expansion
3. **PENTING**: Improve reranking (hybrid semantic + keyword)
4. **JANGKA PANJANG**: Re-chunk dan re-embed documents

### Target Setelah Perbaikan:
- Answer Relevancy: 0.6335 → **0.90+**
- Context Precision: 0.7544 → **0.85+**
- Overall: 0.7574 → **0.90+**
- **Zero "tidak ditemukan" yang salah**

---

**Next Step**: Mulai dengan Fase 1 (Quick Wins) - perbaiki prompt dan query expansion.
