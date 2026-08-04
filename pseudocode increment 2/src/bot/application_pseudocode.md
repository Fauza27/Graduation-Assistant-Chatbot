# Pseudocode untuk `src/bot/application.py`

```markdown
ALGORITMA INISIALISASI TELEGRAM BOT (application.py)

1. IMPOR PUSTAKA
   - Modul `telegram` dan `telegram.ext` (Application, CommandHandler, ContextTypes, dsb).
   - Modul logger dari loguru.
   - Pesan teks `messages`, handler khusus `chat_handler`, dan konfigurasi aplikasi.

2. FUNGSI error_handler(update, context)
   - Dipanggil setiap kali terjadi kesalahan/exception tak terduga saat bot beroperasi.
   - Catat pesan kesalahan lengkap dengan *stack trace* ke logger (`logger.error`).
   - JIKA `update` memiliki objek pesan (bukan event lain):
     - COBA balas pesan ke pengguna menggunakan teks `messages.GENERIC_ERROR` ("Maaf, terjadi kesalahan...").
     - HINGGA BERHASIL atau JIKA ERROR lagi saat membalas, abaikan (pass).

3. FUNGSI cmd_help(update, context)
   - Fungsi pemicu saat pengguna mengetik `/help`.
   - Balas pesan pengguna dengan teks bawaan dari `messages.HELP` dalam format HTML.

4. FUNGSI post_init(application)
   - Fungsi asinkron yang dieksekusi tepat setelah bot selesai diinisialisasi, namun sebelum mulai menerima pesan.
   - Daftarkan menu perintah bawaan bot ke Telegram server (`set_my_commands`):
     - "start": "Mulai bot"
     - "help": "Lihat bantuan"
   - Perintah ini akan muncul di tombol menu hamburger aplikasi Telegram pengguna.

5. FUNGSI create_bot() -> Objek Telegram Application
   - Ambil konfigurasi (get_settings) seperti Token Bot Telegram.
   - Gunakan pola *Builder* dari ApplicationBuilder:
     - Masukkan token bot.
     - Matikan `concurrent_updates` (opsional, atur jika ingin menangani update secara sekuensial atau paralel).
     - Bangun (Build) aplikasinya.
   - Daftarkan penanganan kesalahan (error_handler).
   - Daftarkan penanganan perintah `/start` (memanggil `chat_handler.cmd_start`).
   - Daftarkan penanganan perintah `/help` (memanggil `cmd_help`).
   - Daftarkan penanganan pesan teks bebas dari pengguna dengan memanggil `chat_handler.build_text_chat_handler()`.
   - KEMBALIKAN objek aplikasi bot.
```
