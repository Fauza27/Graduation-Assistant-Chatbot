# Perbandingan Intent — Kapan CONVERSATIONAL vs CLARIFICATION vs NEEDS_RETRIEVAL?

---

## Tabel Keputusan

| Kondisi | Intent | Confidence | Contoh Pesan |
|---------|--------|-----------|-------------|
| Pesan ≤ 9 karakter, tanpa kata tanya | CONVERSATIONAL | 0.95 | "Halo", "Ok", "Oke" |
| Ada pola sapaan, tanpa kata tanya | CONVERSATIONAL | 0.95 | "Terima kasih!", "Selamat pagi" |
| Pertanyaan pertama (belum ada riwayat) | NEEDS_RETRIEVAL | 0.99 | Pertanyaan apa saja |
| Ada kata "ganti topik", "sekarang tanya" | NEEDS_RETRIEVAL | 0.95 | "Sekarang tanya soal PI" |
| Beralih dari topik PI ke KKP (atau sebaliknya) | NEEDS_RETRIEVAL | 0.95 | Tanya KKP setelah membahas PI |
| Aspek berbeda & belum ada di jawaban lama | NEEDS_RETRIEVAL | 0.95 | Tanya format setelah bahas syarat |
| Ada sinyal "jelaskan", konteks masih relevan | CLARIFICATION | 0.90 | "Bisa jelaskan lebih detail?" |
| Ada sinyal "maksudnya", tidak ada switch | CLARIFICATION | 0.90 | "Maksud poin 2 itu gimana?" |
| Kasus ambigu | LLM Decide | variabel | Kasus lainnya |

---

## Daftar Sinyal per Intent

### CONVERSATIONAL — Pola Sapaan
```
"halo", "hai", "hello", "hi"
"selamat pagi", "selamat siang", "selamat malam"
"terima kasih", "makasih", "thanks"
"oke", "ok", "baik", "siap"
"sampai jumpa", "bye", "dadah"
```

### NEEDS_RETRIEVAL — Sinyal Ganti Topik (Explicit)
```
"sekarang tanya", "ganti topik", "beralih ke"
"satu lagi", "pertanyaan lain", "topik berbeda"
"nah kalau", "bagaimana dengan", "lalu bagaimana"
```

### NEEDS_RETRIEVAL — Domain Switch
```
Konteks sebelumnya: PI
Pesan baru mengandung: "kkp", "kuliah kerja praktik"
→ Domain switch terdeteksi → NEEDS_RETRIEVAL
```

### CLARIFICATION — Sinyal Klarifikasi
```
"jelaskan", "jelaskan lebih", "elaborasi"
"maksudnya", "maksud", "artinya"
"lebih detail", "lebih lanjut", "lebih jelas"
"contohnya", "misalnya", "seperti apa"
"apa itu", "apa maksud"
```

### KATA TANYA (mencegah salah klasifikasi sebagai CONVERSATIONAL)
```
"apa", "bagaimana", "kenapa", "mengapa"
"siapa", "dimana", "kapan", "berapa"
"apakah", "bolehkah", "bisakah"
```
> Jika ada kata tanya → pesan **tidak bisa** diklasifikasi sebagai CONVERSATIONAL,
> meski ada pola sapaan.

---

## Contoh Percakapan Nyata dengan Penjelasan Intent

### Percakapan 1: Normal Flow

```
Turn 1:
  User: "Halo!"
  Intent: CONVERSATIONAL (sapaan, tidak ada kata tanya)
  Proses: invoke_conversational → LLM balas sapaan
  Bot: "Halo! Selamat datang. Ada yang bisa saya bantu seputar KKP/PI?"

Turn 2:
  User: "Apa syarat mengambil KKP?"
  Intent: NEEDS_RETRIEVAL (pertanyaan pertama dengan kata tanya "apa")
  Proses: retrieval → generation
  Bot: "Berdasarkan BAB II Buku Panduan KKP, syarat..."

Turn 3:
  User: "Jelaskan poin 1 lebih detail"
  Intent: CLARIFICATION ("jelaskan" + "lebih detail" = sinyal klarifikasi)
           SwitchDetector: tidak ada switch
           → TRUE clarification
  Proses: invoke_clarification dengan konteks lama
  Bot: "Poin 1 yaitu minimal 100 SKS berarti..."

Turn 4:
  User: "Bagaimana dengan PI?"
  Intent: NEEDS_RETRIEVAL (domain switch: KKP → PI)
  Proses: retrieval baru dengan konteks PI
  Bot: "Berdasarkan Buku Panduan PI..."

Turn 5:
  User: "Terima kasih!"
  Intent: CONVERSATIONAL (ucapan terima kasih, tidak ada kata tanya)
  Proses: invoke_conversational
  Bot: "Sama-sama! Semoga bermanfaat. Ada pertanyaan lain?"
```

### Percakapan 2: Edge Case - Clarification Gagal

```
Turn 1:
  User: "Apa format penulisan PI?"
  Intent: NEEDS_RETRIEVAL
  Bot: "Format penulisan PI menggunakan kertas A4, margin..."

Turn 2:
  User: "Bagaimana dengan KKP?"
  Intent: NEEDS_RETRIEVAL ← BUKAN clarification!
          ClarificationDetector: "bagaimana" = sinyal klarifikasi ✓
          SwitchDetector: domain switch PI → KKP ✓
          → Ada switch → bukan klarifikasi sejati
  Proses: retrieval baru untuk KKP
```

### Percakapan 3: LLM Classifier Dipanggil

```
Turn 1:
  User: "Apa itu bimbingan PI?"
  Intent: NEEDS_RETRIEVAL
  Bot: "Bimbingan PI adalah proses..."

Turn 2:
  User: "Siapa yang bisa jadi pembimbing?"
  Intent: → ConvDetector: tidak conversational
          → has_prior_context: YA
          → SwitchDetector: tidak ada switch (masih topik bimbingan PI)
          → ClarificationDetector:
               Sinyal "siapa" = kata tanya, bukan sinyal clarification
               → False (bukan clarification)
          → LLM Classifier dipanggil
          LLM output: {intent: "needs_retrieval", confidence: 0.85}
  Intent: NEEDS_RETRIEVAL (perlu dokumen baru tentang syarat pembimbing)
```

---

## Flowchart Keputusan Cepat

```
Pesan user masuk
      │
      ▼
Ada pola sapaan/pesan pendek DAN tidak ada kata tanya?
      │
   Ya ─► CONVERSATIONAL
      │
   Tidak
      ▼
Ini pertanyaan pertama (belum ada riwayat)?
      │
   Ya ─► NEEDS_RETRIEVAL
      │
   Tidak
      ▼
Ada sinyal ganti topik ATAU domain/aspek berbeda?
      │
   Ya ─► NEEDS_RETRIEVAL
      │
   Tidak
      ▼
Ada sinyal klarifikasi DAN tidak ada switch?
      │
   Ya ─► CLARIFICATION
      │
   Tidak
      ▼
LLM memutuskan (kasus ambigu)
```
