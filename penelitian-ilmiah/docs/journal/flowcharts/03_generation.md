# Flowchart: `src/generation/`

## `memory.py` — Memori Percakapan

Menyimpan riwayat percakapan user dalam satu sesi, dengan batas sliding window.

```
ConversationMemory(max_turns=5)
  _turns = [ Turn(role, content, intent, retrieved_docs) ]

Tambah pesan:
  add_user_turn(content)
    └─ append Turn(role="user")
    └─ _enforce_window() → potong jika > max_turns * 2

  add_assistant_turn(content, retrieved_doc_contents)
    └─ append Turn(role="assistant", retrieved_docs=docs)
    └─ _enforce_window()

Baca riwayat:
  get_history_for_llm()        → semua turn KECUALI yang terakhir
  get_last_retrieved_docs()    → scan mundur, ambil docs dari assistant terakhir
  get_last_question()          → user turn terakhir
  get_previous_question()      → user turn ke-2 dari belakang
  has_prior_context            → ada minimal 1 assistant turn?
```

**Mengapa penting?** Memungkinkan bot "mengingat" konteks percakapan sebelumnya dalam satu sesi.

---

## `chain.py` — RAG Chain & Pembuatan Jawaban

File ini bertugas **membangun prompt dan memanggil LLM** untuk menghasilkan jawaban.

```
RAGChain
  │
  ├─ invoke(question, context_docs)
  │    ├─ _format_context(docs) → susun string konteks berformat
  │    ├─ chain.invoke({context, question})
  │    │    └─ SYSTEM_PROMPT + HUMAN_PROMPT → LLM → StrOutputParser
  │    ├─ _postprocess_answer() → bersihkan whitespace
  │    └─ _build_sources() → ambil 3 sumber teratas
  │
  ├─ invoke_with_history(question, context_docs, history)
  │    ├─ _format_context(docs)
  │    ├─ Bangun messages: SystemMsg + HistoryMsgs + HumanMsg
  │    └─ llm.invoke(messages)
  │
  ├─ invoke_conversational(question, history)
  │    ├─ Format history text
  │    ├─ CONVERSATIONAL_PROMPT + LLM
  │    └─ Return {answer, sources=[]}
  │
  └─ invoke_clarification(question, history, last_docs)
       ├─ Tidak ada last_docs? → _fallback_to_retrieval()
       ├─ _check_context_relevance() (keyword overlap)
       │    └─ score < 0.3? → _fallback_to_retrieval()
       ├─ CLARIFICATION_PROMPT + LLM
       └─ Return {answer}

_fallback_to_retrieval():
  run_retrieval(query) → invoke_with_history()
```

---

## `intent_classifier/models.py` — Data Models

```
SwitchType (Enum):
  NONE | TOPIC | DOMAIN | ASPECT

SwitchDetectionResult:
  has_switch: bool
  switch_type: SwitchType
  reason: str

ClassificationResult:
  intent: IntentType
  confidence: float
  reason: str
  switch_type: SwitchType
```

---

## `intent_classifier/detectors.py` — Detektor Pola

### SwitchDetector
```
detect_switch(message, memory)
  │
  ├─ detect_explicit_switch()
  │    → cari sinyal "ganti topik" (mis. "sekarang tanya tentang...")
  │    → Ada? Return has_switch=True, type=TOPIC
  │
  ├─ detect_domain_switch()
  │    → Bandingkan domain pesan saat ini vs jawaban sebelumnya
  │    → PI ↔ KKP berbeda? Return has_switch=True, type=DOMAIN
  │
  └─ detect_aspect_switch()
       → Bandingkan aspek topik (syarat/format/prosedur/dll)
       → Aspek baru dan tidak ada di jawaban lama?
         Return has_switch=True, type=ASPECT
```

### ClarificationDetector
```
is_true_clarification(message, memory)
  ├─ Tidak ada prior context? → False
  ├─ Ada sinyal klarifikasi? (mis. "maksudnya?", "jelaskan lebih")
  │    → Tidak ada? → False
  └─ Jalankan SwitchDetector
       → Ada switch? → False (bukan klarifikasi, ini topik baru)
       → Tidak ada switch? → True (ini klarifikasi sejati)
```

### ConversationalDetector
```
is_conversational(message)
  ├─ Pesan ≤ 9 karakter dan tidak ada kata tanya? → True
  └─ Ada pola sapaan (halo, terima kasih, dll) dan tidak ada kata tanya? → True
```

---

## `intent_classifier/classifier.py` — Klasifikasi Intent

```
IntentClassifier.classify(message, memory)
       │
       ▼
ConversationalDetector.is_conversational()
       │
  Conversational? ──Yes──► Return CONVERSATIONAL (conf=0.95)
       │No
       ▼
has_prior_context? ──No──► Return NEEDS_RETRIEVAL (conf=0.99)
  "Pertanyaan pertama"
       │Yes
       ▼
SwitchDetector.detect_switch()
       │
  Ada switch? ──Yes──► Return NEEDS_RETRIEVAL (conf=0.95)
       │No
       ▼
ClarificationDetector.is_true_clarification()
       │
  Klarifikasi? ──Yes──► Return CLARIFICATION (conf=0.90)
       │No
       ▼
_classify_with_llm()
  ├─ Cek cache (key = pesan[:50] + turn_count)
  ├─ Build prompt dengan riwayat percakapan
  ├─ LLM.invoke → JSON {intent, confidence, reason}
  ├─ Override ke NEEDS_RETRIEVAL jika switch terdeteksi
  └─ Return IntentType, confidence, reason
```

---

## `intent_classifier/reformulator.py` — Penyederhanaan Query

```
QueryReformulator.reformulate_query(message, memory)
       │
  memory kosong? ──Yes──► Return pesan asli
       │No
       ▼
has_implicit_references()
  Cek kata: "itu", "tadi", "tersebut", "di atas", dll.
       │
  Tidak ada referensi? ──Yes──► Return pesan asli
       │Ada
       ▼
  Format REFORMULATION_PROMPT
  dengan riwayat percakapan + pesan saat ini
       │
       ▼
  LLM.invoke → pesan baru yang mandiri
  Contoh: "jelaskan lebih lanjut" 
       → "Jelaskan lebih lanjut tentang syarat KKP"
```
