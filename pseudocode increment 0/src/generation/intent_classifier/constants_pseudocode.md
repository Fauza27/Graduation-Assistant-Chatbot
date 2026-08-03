# Pseudocode untuk `src/generation/intent_classifier/constants.py`

```markdown
ALGORITMA KONSTANTA KLASIFIKASI INTENT (constants.py)

1. DEKLARASI DAFTAR KATA KUNCI (SIGNALS)
   - `TOPIC_SWITCH_SIGNALS`:
     - Tanda Eksplisit: "sekarang", "bagaimana dengan", "kalau untuk", "ganti topik", dll.
     - Tanda Domain: 
       - PI: ["pi", "penulisan ilmiah", "penelitian", "skripsi", "thesis"]
       - KKP: ["kkp", "kuliah kerja praktik", "magang", "internship", "praktik"]
   
   - `CLARIFICATION_SIGNALS`:
     - Tanda Minta Kejelasan: "lebih detail", "jelaskan lagi", "elaborasi", "contoh", "maksudnya", "mengapa", dll.
   
   - `CONVERSATIONAL_PATTERNS`:
     - Tanda Obrolan Biasa: "halo", "hai", "selamat pagi", "terima kasih", "oke", "sampai jumpa", dll.
   
   - `QUESTION_KEYWORDS`:
     - Tanda Pertanyaan: "apa", "bagaimana", "berapa", "kapan", "siapa", "kenapa", "mengapa", "dimana".
   
   - `ASPECT_KEYWORDS`:
     - Tanda Aspek (Sub-topik): syarat, format, durasi, prosedur, dosen, tempat, ujian, laporan.
   
   - `IMPLICIT_REFERENCE_SIGNALS`:
     - Tanda Referensi Implisit (menunjuk objek sebelumnya): "itu", "tersebut", "tadi", "hal itu", "dan untuk", dll.

2. PROMPT SISTEM (System Prompts)
   - `CLASSIFIER_SYSTEM_PROMPT`:
     - Prompt instruksi untuk LLM saat menjadi Classifier.
     - Menjelaskan aturan 3 Intent (needs_retrieval, conversational, clarification).
     - Memberikan contoh kapan harus memakai intent yang mana (terutama bedanya topic switch vs clarification).
     - Memaksa keluaran dalam bentuk JSON wajib (`{"intent": "...", "reason": "...", "confidence": 1.0}`).
   
   - `REFORMULATION_PROMPT`:
     - Prompt instruksi untuk LLM saat menjadi Reformulator (Penulis ulang pertanyaan).
     - Mengubah pertanyaan yang tidak jelas (seperti "Bagaimana dengan syaratnya?") menjadi pertanyaan lengkap ("Bagaimana dengan syarat KKP?") dengan melihat riwayat percakapan.
```
