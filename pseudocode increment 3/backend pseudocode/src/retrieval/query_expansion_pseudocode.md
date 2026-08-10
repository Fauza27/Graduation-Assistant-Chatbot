# Pseudocode untuk `src/retrieval/query_expansion.py`

```markdown
ALGORITMA PERLUASAN KATA KUNCI (query_expansion.py)

1. IMPOR PUSTAKA
   - Ekspresi reguler (`re`), loguru.

2. KONSTANTA DAFTAR SINGKATAN
   - `UPPERCASE_ACRONYMS`: Kamus singkatan huruf besar ke kepanjangannya. (PI -> Penulisan Ilmiah, KKP -> Kuliah Kerja Praktik, SKS -> Satuan Kredit Semester, dll).
   - `LONG_FORM_TO_ACRONYM`: Kamus kepanjangan ke singkatan (penulisan ilmiah -> PI, dll).
   - `SYNONYMS`: Kamus sinonim/istilah alternatif yang sering dipakai mahasiswa tapi punya istilah resmi berbeda di dokumen. Contoh:
     - "pendadaran" → ["ujian skripsi", "sidang skripsi", "ujian tugas akhir", "seminar pendadaran"]
     - "sidang" → ["ujian skripsi", "pendadaran"]
     - "pembimbing" → ["dosen pembimbing"]
     - "penguji" → ["dosen penguji"]

3. FUNGSI _has_uppercase_token(text, token)
   - Mengecek apakah sebuah singkatan huruf kapital (misal "PI") benar-benar muncul sebagai kata utuh di dalam teks, bukan sebagai bagian dari kata lain (seperti "PINTAR").
   - Kembalikan True/False menggunakan Regex Boundary (`\b`).

4. FUNGSI _has_phrase(text_lower, phrase)
   - Mengecek substring biasa dalam teks huruf kecil.

5. FUNGSI expand_query(question)
   - JIKA pertanyaan kosong, kembalikan kosong.
   - Buat daftar `additions` kosong (untuk menampung kata tambahan).
   - Ubah teks pertanyaan jadi huruf kecil semua untuk pengecekan tipe ke-2.
   
   - Aturan 1: Singkatan Besar -> Kepanjangan
     - LOOP semua singkatan di `UPPERCASE_ACRONYMS`:
       - JIKA teks punya singkatan utuh (contoh ada kata "KKP"):
         - LOOP semua kemungkinan kepanjangannya (contoh "Kuliah Kerja Praktik").
         - JIKA kepanjangan itu belum ada di teks asli dan belum ditambahkan: Tambahkan ke `additions`.
   
   - Aturan 2: Kepanjangan -> Singkatan
     - LOOP semua frase di `LONG_FORM_TO_ACRONYM`:
       - JIKA teks punya frase utuh (contoh ada kata "kuliah kerja praktik"):
         - LOOP semua kemungkinan singkatannya (contoh "KKP").
         - JIKA singkatan itu tidak ada secara kapital di teks dan belum ditambahkan: Tambahkan ke `additions`.
   
   - Aturan 3: Sinonim / Istilah Alternatif
     - LOOP semua kata di `SYNONYMS`:
       - JIKA kata tersebut muncul sebagai kata utuh (Regex Boundary `\b`) di teks:
         - LOOP semua padanan resminya.
         - JIKA padanan belum ada di teks dan belum ditambahkan: Tambahkan ke `additions`.
   
   - JIKA tidak ada tambahan: Kembalikan teks asli.
   - JIKA ada: Gabungkan teks asli dengan tambahan (diberi spasi). Log aksi ini.
   - Kembalikan teks perluasan (contoh: "Apa itu kkp? Kuliah Kerja Praktik").

6. FUNGSI expand_query_smart(question, enable_expansion)
   - Bungkus (wrapper) untuk on/off fitur ini secara dinamis.
   - Jika `enable_expansion` False, kembalikan pertanyaan aslinya.
   - Jika True, panggil `expand_query(question)`.
```
