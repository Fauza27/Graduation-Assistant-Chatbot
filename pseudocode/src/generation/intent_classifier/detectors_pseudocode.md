# Pseudocode untuk `src/generation/intent_classifier/detectors.py`

```markdown
ALGORITMA DETEKTOR PERCAKAPAN (detectors.py)

1. KELAS SwitchDetector
   - `detect_explicit_switch(message)`:
     - Cari kata dari pesan user yang cocok dengan `TOPIC_SWITCH_SIGNALS["explicit"]` (misal: "sekarang", "bagaimana dengan").
     - Kembalikan kata sinyal tersebut jika ada, jika tidak ada kembalikan None.
   
   - `detect_domain_switch(message, memory)`:
     - Deteksi apakah domain pesan saat ini (misal PI) berbeda dengan domain di pesan sebelumnya (misal KKP).
     - Kembalikan True/False dan alasan.
   
   - `detect_aspect_switch(message, memory)`:
     - Deteksi apakah aspek pesan saat ini (misal "syarat") berbeda dengan aspek sebelumnya (misal "dosen").
     - Kembalikan True/False dan alasan.
   
   - `detect_switch(message, memory)`:
     - Jalankan `detect_explicit_switch`. Jika True -> Pindah Topik (TOPIC).
     - Jalankan `detect_domain_switch`. Jika True -> Pindah Domain (DOMAIN).
     - Jalankan `detect_aspect_switch`. Jika True -> Pindah Aspek (ASPECT).
     - Kembalikan objek `SwitchDetectionResult`.

2. KELAS ClarificationDetector
   - `detect_clarification_signals(message)`:
     - Cari kata dari pesan user yang cocok dengan `CLARIFICATION_SIGNALS` (misal "jelaskan lagi", "contohnya").
   
   - `is_true_clarification(message, memory)`:
     - JIKA pesan punya sinyal klarifikasi, DAN TIDAK TERDETEKSI adanya perpindahan topik (dari `SwitchDetector`).
     - Maka itu adalah klarifikasi asli (True). Kembalikan True.

3. KELAS ConversationalDetector
   - `is_short_message(message)`:
     - Cek apakah panjang pesan kurang dari sama dengan 9 karakter.
   
   - `has_question_keywords(message)`:
     - Cek apakah ada kata tanya (apa, bagaimana, dll) di pesan.
   
   - `matches_conversational_pattern(message)`:
     - Cek apakah cocok dengan daftar pola obrolan (halo, terima kasih, dll).
   
   - `is_conversational(message)`:
     - JIKA (pesan sangat pendek DAN tidak ada kata tanya) ATAU (cocok dengan pola obrolan DAN tidak ada kata tanya).
     - Kembalikan True.
```
