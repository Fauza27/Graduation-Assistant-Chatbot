# Pseudocode untuk `src/generation/intent_classifier/reformulator.py`

```markdown
ALGORITMA REFORMULASI PERTANYAAN (reformulator.py)

1. IMPOR PUSTAKA
   - Langchain (HumanMessage, ChatOpenAI).
   - Logger, Pengaturan, Memori.
   - Konstanta (`IMPLICIT_REFERENCE_SIGNALS`, `REFORMULATION_PROMPT`).

2. FUNGSI normalize_query(query)
   - Normalisasi istilah akademik via Regex secara agresif.
   - Singkatan "kp" -> "KKP", "pi" -> "Penulisan Ilmiah".
   - Jika query berupa "apa itu X", ubah paksa menjadi "Apa yang dimaksud dengan X".

3. FUNGSI needs_rewrite(query)
   - Gunakan **Regex Word Boundary** (`\b`) saat mengecek kata tunjuk implisit ("itu", "tersebut", "tadi"). Ini mencegah bug *substring match* naif yang memicu reformulasi pada kata seperti "waktu".
   - Kecualikan pemrosesan ulang jika kalimat sudah jelas mandiri (contoh: "apa itu kkp").
   - KEMBALIKAN True/False.

4. KELAS QueryReformulator
   - `__init__(llm)`:
     - Jika objek LLM tidak diberikan, buat objek LLM ChatOpenAI (suhu=0, max_token=100).
   
   - `_extract_last_topic(memory)`:
     - Baca memori percakapan secara mundur (reversed) untuk menemukan topik terakhir yang dibahas (KKP atau Penulisan Ilmiah).
   
   - `_apply_rule_rewrite(message, last_topic)`:
     - Coba lakukan penulisan ulang instan menggunakan *Rule/Regex* tanpa perlu menembak API LLM.
     - Contoh: "terus formatnya" -> "terus formatnya Penulisan Ilmiah".
   
   - `reformulate_query(message, memory)`:
     - JIKA histori percakapan (memori) kosong, langsung KEMBALIKAN tuple (pesan asli, "None").
     - JIKA `_apply_rule_rewrite` berhasil menangani kalimat, KEMBALIKAN tuple (pesan diperbaiki, "Rule").
     - Jika aturan gagal, barulah jatuh (fallback) ke LLM Reformulator.
       - Susun prompt berdasarkan `REFORMULATION_PROMPT` dan panggil API LLM.
       - KEMBALIKAN tuple (pesan dari LLM, "LLM").
       - Jika LLM error, kembalikan tuple (pesan asli, "None") (fallback).

5. FUNGSI reformulate_query(message, memory, llm)
   - Fungsi Wrapper kompatibilitas lama yang mengembalikan nilai _tuple_ (teks, metode).
```
