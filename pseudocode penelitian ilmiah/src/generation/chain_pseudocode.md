# Pseudocode untuk `src/generation/chain.py`

```markdown
ALGORITMA GENERASI JAWABAN CHATBOT (chain.py)

1. IMPOR PUSTAKA
   - Langchain (Dokumen, Parser Output, Prompt Template, ChatOpenAI).
   - loguru (logger), modul konfigurasi, deteksi panduan.

2. KONSTANTA PROMPT
   - `SYSTEM_PROMPT`: Peran AI sebagai asisten akademik STMIK Wicida. Mengatur aturan menjawab (berbasis dokumen, cantumkan bab sumber, dilarang halusinasi, format list).
   - `HUMAN_PROMPT`: Format input untuk AI (Konteks dokumen + Pertanyaan User).
   - `HUMAN_PROMPT_WITH_HISTORY`: Format input yang mempertimbangkan histori percakapan.
   - `CONVERSATIONAL_PROMPT`: Format obrolan biasa (sapaan/terima kasih) tanpa pencarian dokumen.
   - `CLARIFICATION_PROMPT`: Format untuk meminta penjelasan lebih lanjut dari jawaban sebelumnya.

3. FUNGSI _format_context(documents)
   - Ambil list objek Dokumen dari proses Retrieval (Pencarian).
   - GABUNGKAN teks dari tiap dokumen dengan pembatas "---".
   - TAMBAHKAN header pada tiap dokumen (contoh: "[Sumber: Buku Panduan PI] - BAB II - Relevansi: 0.85").
   - KEMBALIKAN teks gabungan yang siap dibaca LLM.

4. FUNGSI _postprocess_answer(answer)
   - Rapikan hasil jawaban teks LLM.
   - HAPUS spasi berlebih dan ganti baris kosong yang terlalu banyak.
   - KEMBALIKAN teks rapi.

5. FUNGSI _build_sources(context_documents, limit=3)
   - Buat list meta-data sumber referensi (maksimal 3 teratas).
   - Ambil ID dokumen, judul, bab, dan skor kemiripan.
   - KEMBALIKAN array daftar sumber.

6. FUNGSI build_rag_chain(streaming)
   - Buat objek `ChatOpenAI` dengan model, suhu 0, dan token 1200.
   - Gabungkan `SYSTEM_PROMPT` dan `HUMAN_PROMPT`.
   - BENTUK "Chain" RAG: (Format Input Konteks) -> Prompt -> LLM -> Output String.
   - KEMBALIKAN chain.

7. KELAS RAGChain
   - Inisialisasi: Buat dan simpan instance LLM.
   - METHOD `invoke_with_history(question, context, history)`:
     - Log informasi pemrosesan.
     - **Adaptive History**: Jika dokumen konteks kosong (icu *Minimum Evidence Triggered*), potong histori paksa menjadi 1 giliran (maksimal 2 pesan terakhir) untuk mode obrolan biasa.
     - Hitung profil token input dan output menggunakan `tiktoken`.
     - Susun pesan konteks dan histori sebagai array `SystemMessage`, `HumanMessage`, dan `AIMessage`.
     - Masukkan konteks dan panggil LLM.
     - Cetak profil penggunaan token ke log.
     - Kembalikan jawaban LLM + sumber referensi.
   - METHOD `invoke_conversational(question, history)`:
     - Gunakan saat pengguna hanya basa-basi ("Halo", "Terima kasih").
     - Panggil LLM tanpa memasukkan dokumen konteks berat.
     - Kembalikan jawaban saja (sumber = kosong).
   - METHOD `invoke_clarification(question, history, last_context)`:
     - Gunakan jika pengguna minta penjelasan tambahan ("Tolong jelaskan lebih detail").
     - Cek apakah topik masih relevan dengan dokumen lama (`_check_context_relevance`).
     - Jika TIDAK RELEVAN (< 0.3): Beralih (Fallback) jalankan Retrieval pencarian ulang.
     - Jika RELEVAN: Minta LLM menjelaskan ulang dokumen sebelumnya.
     - Kembalikan jawaban.

8. FUNGSI generate_answer(question, context)
   - Fungsi sederhana untuk mengeksekusi Chain reguler.
   - Format jawaban dan kembalikan output-nya.
```
