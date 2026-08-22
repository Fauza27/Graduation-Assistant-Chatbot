# Pseudocode untuk `src/generation/memory.py`

```markdown
ALGORITMA PENYIMPANAN MEMORI PERCAKAPAN (memory.py)

1. DEKLARASI ENUM & STRUKTUR DATA
   - `IntentType`: Jenis percakapan (NEEDS_RETRIEVAL, CONVERSATIONAL, CLARIFICATION).
   - `Turn` (Dataclass): Objek yang merepresentasikan satu pesan, berisi:
     - `role`: "user" (pengguna) atau "assistant" (bot).
     - `content`: isi pesan (teks).
     - `intent`: tipe tujuan (opsional).
     - `retrieved_doc_contents`: daftar teks dokumen yang digunakan bot untuk menjawab (jika ada).
     - `timestamp`: waktu pesan dibuat.

2. KELAS ConversationMemory
   - `__init__(max_turns=5)`:
     - Inisialisasi array `_turns` kosong.
     - Set batas maksimal jumlah percakapan yang diingat secara internal (`max_turns`).

   - `add_user_turn(content, intent)`:
     - Tambahkan pesan dari user ke daftar `_turns`.

   - `add_assistant_turn(content, retrieved_doc_contents, sources)`:
     - Tambahkan pesan balasan bot beserta dokumen sumber ke daftar `_turns`.

   - `get_history_for_llm()`:
     - Ambil histori pesan untuk disuapkan ke LLM (format dict).
     - **Batas LLM Context**: Terapkan *sliding window* dengan batas `settings.MAX_HISTORY_TURNS` (default: 3 giliran) agar input ke LLM tidak membengkak berlebihan.

   - `get_last_retrieved_docs()`:
     - Cari dari pesan terakhir bot, apa saja isi teks dokumen yang dipakai untuk menjawab.
     - Kembalikan daftar dokumen.

   - `get_conversation_summary()`:
     - Rangkum percakapan saat ini sebagai string teks, dibatasi 200 karakter per pesan, untuk mempermudah pengecekan log.

   - `get_last_question()` & `get_last_answer()`:
     - Ambil teks pertanyaan terakhir user dan jawaban terakhir bot.

   - `has_prior_context` (Property):
     - Kembalikan True jika ada minimal satu percakapan tuntas (user -> asisten) sebelum pesan saat ini.

   - FUNGSI KONVERSI DB:
     - `to_dict()`: Konversi array `_turns` menjadi bentuk *Dictionary/JSON* agar bisa disimpan di Database (Supabase JSONB).
     - `from_dict(turns_data, max_turns)`: Bangun kembali (Rekonstruksi) objek `ConversationMemory` dari data mentah yang ditarik dari Database.
```
