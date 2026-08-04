# Pseudocode untuk `src/bot/messages.py`

```markdown
ALGORITMA TEKS PESAN BOT TELEGRAM (messages.py)

1. TUJUAN
   - Menyimpan seluruh templat string / pesan balasan (reply) yang akan digunakan oleh Telegram bot.
   - Semua format teks dibuat mendukung tag HTML (contoh: <b> untuk bold).

2. KONSTANTA PESAN:
   - WELCOME
     - Berisi kalimat sapaan awal saat bot dimulai.
     - Menyapa dengan nama depan pengguna ("Halo, {first_name}!").
     - Memberi tahu fungsi bot untuk tanya jawab seputar KKP/PI.

   - HELP
     - Berisi panduan bantuan.
     - Menjelaskan topik yang didukung dan contoh pertanyaan.
     - Menjelaskan daftar perintah (/start, /help).

   - DAILY_LIMIT_REACHED
     - Pesan peringatan kuota harian habis.
     - Memiliki *placeholder* "{limit}" yang akan diisi oleh angka dari pengaturan.

   - GENERIC_ERROR
     - Teks "Maaf, terjadi kesalahan. Silakan coba lagi." (untuk pesan jika sistem error).

   - LOADING
     - Teks "⏳ Sedang mencari jawaban..." (pesan sementara yang muncul sebelum LLM membalas).

   - EMPTY_ANSWER_FALLBACK
     - Teks balasan cadangan jika bot tidak mengembalikan jawaban teks sama sekali.
```
