# Pseudocode untuk `src/generation/intent_classifier/models.py`

```markdown
ALGORITMA MODEL DATA (models.py)

1. IMPOR PUSTAKA
   - `dataclass`, `Enum`.
   - `IntentType` dari memori.

2. ENUMERASI SwitchType
   - Mendefinisikan tipe perpindahan konteks.
   - `NONE`: Tidak ada perpindahan.
   - `TOPIC`: Pindah topik eksplisit.
   - `DOMAIN`: Pindah domain utama (KKP/PI).
   - `ASPECT`: Pindah sub-aspek (Syarat, Dosen, Laporan, dll).

3. STRUKTUR DATA ClassificationResult
   - `intent` (Tipe `IntentType`): Hasil akhir klasifikasi (Retrieval, Conversational, Clarification).
   - `confidence` (Angka desimal): Tingkat keyakinan (0-1).
   - `reason` (Teks): Alasan kenapa memilih intent tersebut.
   - `switch_type` (Tipe `SwitchType`): Menyimpan jenis perpindahan jika ada.
   - `switch_reason` (Teks): Penjelasan alasan perpindahan.

4. STRUKTUR DATA SwitchDetectionResult
   - `has_switch` (Boolean): Bernilai Benar (True) jika detektor menemukan adanya perpindahan konteks percakapan.
   - `switch_type` (Tipe `SwitchType`): Tipe perpindahan (Topik, Domain, atau Aspek).
   - `reason` (Teks): Bukti penemuan perpindahan (misal: ada kata 'sekarang' atau 'bagaimana dengan').
```
