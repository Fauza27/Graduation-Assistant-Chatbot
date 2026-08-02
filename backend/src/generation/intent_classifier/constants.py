"""Constants for intent classification."""

TOPIC_SWITCH_SIGNALS = {
    "explicit": [
        "sekarang", "now", "bagaimana dengan", "how about", "kalau untuk", "what about",
        "lalu untuk", "then for", "selanjutnya", "next", "ganti topik", "change topic",
        "berbeda", "different", "lain", "other", "bukan", "not", "tapi", "but"
    ],
    "domain_keywords": {
        "pi": ["pi", "penulisan ilmiah", "penelitian", "skripsi", "thesis"],
        "kkp": ["kkp", "kuliah kerja praktik", "magang", "internship", "praktik"]
    }
}

CLARIFICATION_SIGNALS = [
    "lebih detail", "more detail", "jelaskan lagi", "explain again", 
    "elaborasi", "elaborate", "contoh", "example", "maksudnya", "meaning",
    "mengapa", "why", "kenapa", "bagaimana cara", "how to", "bisa dijelaskan",
    "can you explain", "apa maksud", "what does it mean"
]

CONVERSATIONAL_PATTERNS = [
    "halo", "hai", "hello", "hi", "hey",
    "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
    "terima kasih", "makasih", "thanks", "thank you",
    "oke", "ok", "baik", "siap", "mengerti", "paham",
    "sampai jumpa", "bye", "dadah",
]

QUESTION_KEYWORDS = [
    "apa", "bagaimana", "berapa", "kapan", "siapa", "kenapa", "mengapa", "dimana"
]

ASPECT_KEYWORDS = {
    "syarat": ["syarat", "requirement", "persyaratan", "kondisi", "minimal"],
    "format": ["format", "struktur", "template", "bentuk", "susunan", "penulisan"],
    "durasi": ["durasi", "lama", "waktu", "periode", "jangka"],
    "prosedur": ["prosedur", "tahap", "langkah", "proses", "cara", "tahapan"],
    "dosen": ["dosen", "pembimbing", "supervisor", "penguji"],
    "tempat": ["tempat", "lokasi", "instansi", "perusahaan"],
    "ujian": ["ujian", "seminar", "sidang", "presentasi"],
    "laporan": ["laporan", "bab", "halaman", "margin", "font"],
}

IMPLICIT_REFERENCE_SIGNALS = [
    "itu", "tersebut", "tadi", "yang itu", "hal itu",
    "lebih detail", "jelaskan lagi", "elaborasi", "lanjutkan",
    "bagaimana dengan", "kalau untuk", "dan untuk", "gimana kalau",
]

CLASSIFIER_SYSTEM_PROMPT = """Anda adalah classifier yang menganalisis pesan user \
dalam sistem Q&A Kuliah Kerja Praktek (KKP) dan Penelitian Ilmiah (PI) di STMIK Widya Cipta Dharma.

PENTING: Perhatikan context switching dan topic switching dengan cermat!

Tugas Anda: tentukan intent pesan user dan kembalikan HANYA JSON, tidak ada penjelasan lain.
 
Tiga kategori intent:
 
1. "needs_retrieval"
   → Pertanyaan spesifik yang butuh informasi dari dokumen pedoman
   → Pertanyaan tentang topik BARU yang berbeda dari history
   → Pertanyaan yang beralih domain (PI ↔ KKP)
   → Pertanyaan yang beralih aspek dalam domain yang sama
   → Mengandung signal switching: "sekarang", "bagaimana dengan", "kalau untuk", "lalu untuk"
   Contoh: "Berapa lama minimal KKP?", "Bagaimana dengan syarat PI?", "Sekarang tentang format laporan"
 
2. "conversational"
   → Sapaan, ucapan terima kasih, pertanyaan sangat umum
   → Perintah yang tidak butuh dokumen pedoman
   Contoh: "Halo", "Terima kasih", "Oke mengerti", "Apa itu PI secara umum?"
 
3. "clarification"
   → HANYA untuk elaborasi/penjelasan lebih lanjut dari jawaban yang SAMA PERSIS
   → Pertanyaan yang jawabannya sudah ada di konteks history
   → TIDAK untuk topic switching atau domain switching
   → Mengandung signal clarification: "lebih detail", "jelaskan lagi", "contoh", "maksudnya"
   Contoh: "Bisa jelaskan lebih detail tentang syarat yang tadi?", "Kasih contoh untuk hal yang sama"

ATURAN KHUSUS:
- Jika ada signal switching ("bagaimana dengan", "kalau untuk", "sekarang") → SELALU "needs_retrieval"
- Jika beralih domain (PI→KKP atau KKP→PI) → SELALU "needs_retrieval"  
- Jika beralih aspek (syarat→format, durasi→prosedur) → SELALU "needs_retrieval"
- Clarification HANYA untuk elaborasi topik yang SAMA PERSIS

Format output WAJIB (JSON saja, tidak ada teks lain):
{
  "intent": "needs_retrieval" | "conversational" | "clarification",
  "reason": "alasan singkat dalam 1 kalimat",
  "confidence": 0.0-1.0,
  "topic_switch_detected": true/false,
  "domain_switch_detected": true/false
}"""

REFORMULATION_PROMPT = """Anda membantu sistem pencarian dokumen internal.
 
Riwayat percakapan:
{history}
 
Pertanyaan terkini user: "{question}"
 
Tugas: Jika pertanyaan terkini menggunakan referensi implisit seperti "itu",
"tersebut", "yang tadi", "lebih detail tentang itu", maka tulis ulang menjadi
pertanyaan yang BERDIRI SENDIRI dan lengkap untuk digunakan sebagai query pencarian.
 
Jika pertanyaan sudah jelas dan mandiri, kembalikan persis sama.
 
Output: HANYA pertanyaan yang sudah ditulis ulang, tanpa penjelasan apapun."""