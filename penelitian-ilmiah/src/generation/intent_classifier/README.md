# Intent Classifier & Query Processing

Modul ini bertanggung jawab untuk menganalisis niat (intent) pengguna sebelum diteruskan ke pipeline RAG atau LLM. Modul ini menjadi otak utama yang membedakan kapan sistem harus mencari dokumen dan kapan cukup menjawab dengan santai.

## Struktur Modul

- **`classifier.py`**: Menggunakan LLM (via `ChatOpenAI` dengan mode `with_structured_output`) untuk mengklasifikasikan intent percakapan. Intent yang dihasilkan akan masuk ke dalam salah satu dari 3 kategori:
  1. `needs_retrieval`: Pertanyaan substantif tentang KKP/PI yang butuh dokumen rujukan.
  2. `conversational`: Pertanyaan umum, sapaan, atau obrolan santai.
  3. `clarification`: Permintaan penjelasan lebih lanjut dari jawaban sebelumnya.
- **`detectors.py`**: Mendeteksi *Context Switching* menggunakan *heuristic rules* (berbasis regex dan keyword). Ini digunakan untuk mengenali kapan pengguna secara mendadak berganti topik dari PI ke KKP, atau berpindah fokus (misal: dari syarat pendaftaran ke durasi pelaksanaan).
- **`reformulator.py`**: Berfungsi untuk memperbaiki query yang mengandung referensi implisit (seperti "bagaimana dengan itu?") menjadi query eksplisit ("bagaimana dengan syarat pendaftaran KKP?"). Ini penting karena algoritma *vector search* tidak memiliki memori percakapan.
- **`constants.py`**: Menyimpan definisi prompt dan schema Pydantic yang digunakan untuk standarisasi output.

## Alur Pemrosesan
Setiap pesan baru dari pengguna akan dianalisis melalui beberapa lapis:
1. Apakah ini *context switch* mendadak? (di-*handle* oleh `detectors.py`)
2. Jika butuh klarifikasi atau ada kata ganti penunjuk ("dia", "itu"), reformulasi pertanyaan berdasarkan riwayat sesi (`reformulator.py`).
3. Tentukan klasifikasi final: apakah butuh RAG, atau langsung dijawab (`classifier.py`).

Dengan pre-processing ini, performa RAG akan jauh lebih relevan karena beban pencarian hanya dieksekusi untuk pertanyaan yang benar-benar membutuhkan data dokumen.
