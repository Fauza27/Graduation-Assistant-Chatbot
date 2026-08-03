# Pseudocode untuk `src/generation/intent_classifier/classifier.py`

```markdown
ALGORITMA KLASIFIKASI INTENT (classifier.py)

> **⚠️ PERINGATAN ARSITEKTUR ⚠️**
> Modul `IntentClassifier` LLM ini **telah di-*bypass* secara praktis** pada pembaruan arsitektur terbaru aplikasi (menuju arsitektur murni *Retrieval-First / Evidence-Driven*). Berkas ini masih dipertahankan untuk referensi *fallback* dan kompatibilitas, namun *core flow* AI (`ai_services.py`) tidak lagi memanggil modul ini sebagai "satpam" (Gatekeeper) perantara utama.

1. IMPOR PUSTAKA
   - JSON, Typing, Langchain (HumanMessage, SystemMessage, ChatOpenAI).
   - loguru (logger).
   - Konfigurasi, Memori percakapan.
   - Konstanta dan Detektor (SwitchDetector, ClarificationDetector, ConversationalDetector).

2. FUNGSI _build_classifier_prompt(current_message, memory)
   - Ambil riwayat pertanyaan dan jawaban terakhir dari memori (jika ada).
   - Gabungkan histori tersebut dengan pesan user saat ini.
   - Tambahkan instruksi untuk LLM: "Tentukan intent pesan user sekarang. Output hanya JSON."
   - Kembalikan teks prompt.

3. KELAS IntentClassifier
   - `__init__()`:
     - Buat LLM (ChatOpenAI) dengan suhu=0, max_tokens=200.
     - Buat dictionary (kamus) kosong untuk *Cache* hasil klasifikasi agar hemat API.
     - Inisialisasi ketiga detektor (Switch, Clarification, Conversational).
   
   - `classify(message, memory)`:
     - TAHAP 1: Jalan pintas Obrolan Biasa.
       - Cek dengan `ConversationalDetector`. Jika "conversational", kembalikan (IntentType.CONVERSATIONAL, 0.95, alasan).
     - TAHAP 2: Jika ini pesan pertama (tidak ada histori).
       - Langsung kembalikan "NEEDS_RETRIEVAL" (pasti butuh pencarian).
     - TAHAP 3: Deteksi Perpindahan Topik (Switch).
       - Cek dengan `SwitchDetector`.
       - Jika terdeteksi pindah topik/domain/aspek, kembalikan "NEEDS_RETRIEVAL" karena pasti butuh mencari info baru.
     - TAHAP 4: Deteksi Permintaan Penjelasan (Clarification).
       - Cek dengan `ClarificationDetector`.
       - Jika terdeteksi user minta kejelasan dari topik yang SAMA PERSIS, kembalikan "CLARIFICATION".
     - TAHAP 5: Jika semua aturan gagal (Rule-based gagal).
       - Lempar ke LLM untuk diproses dengan memanggil `_classify_with_llm(message, memory)`.

   - `_classify_with_llm(message, memory)`:
     - Buat kunci cache dari 50 karakter pertama pesan + jumlah riwayat percakapan.
     - JIKA kunci ada di cache: kembalikan hasil cache tersebut (hemat pemanggilan LLM).
     - Bangun prompt dari `_build_classifier_prompt`.
     - Panggil API LLM (dengan `CLASSIFIER_SYSTEM_PROMPT` dan prompt yang dibuat).
     - Bersihkan teks respon dari LLM (hilangkan tanda blok kode markdown ` ```json `).
     - *Parse* string menjadi objek JSON.
     - Ambil `intent`, `confidence`, dan `reason` dari JSON tersebut.
     - Simpan hasil ke cache.
     - KEMBALIKAN (intent, confidence, reason).
     - JIKA ERROR (JSON invalid, gagal API, dll): Jatuh ke pilihan aman (Fallback) yaitu "NEEDS_RETRIEVAL".
```
