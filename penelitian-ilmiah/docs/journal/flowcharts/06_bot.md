# Flowchart: `src/bot/`

## `application.py` — Setup Telegram Bot

Mendaftarkan semua command handler dan membangun aplikasi bot.

```
create_bot()
       │
       ▼
ApplicationBuilder()
  .token(TELEGRAM_BOT_TOKEN)
  .concurrent_updates(False)  ← satu pesan diproses per waktu
  .build()
       │
       ▼
add_error_handler(error_handler)
  └─ Jika ada error tak terduga → log + kirim pesan error ke user
       │
       ▼
add_handler(CommandHandler "start" → cmd_start)
add_handler(CommandHandler "help"  → cmd_help)
add_handler(MessageHandler TEXT & bukan COMMAND → handle_text_chat)
       │
Return Application (siap digunakan)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

post_init(application)
  └─ set_my_commands(["/start: Mulai bot", "/help: Lihat bantuan"])
     (Tampil di menu perintah Telegram)
```

---

## `handlers/chat_handler.py` — Handler Pesan Teks

File yang menangani setiap pesan teks dari user di Telegram.

```
handle_text_chat(Update, Context)
       │
  Pesan ada & tidak kosong? ──No──► Return (abaikan)
       │Yes
       ▼
  Ekstrak: text, chat_id, user_id
       │
       ▼
check_and_update_quota(user_id)       [asyncio.to_thread]
  └─ Supabase RPC: increment_quota_if_under_limit
       ├─ p_user_id, p_date (hari ini), p_daily_limit
       ├─ Masih di bawah limit? → Return True + tambah hitungan
       ├─ Sudah mencapai limit? → Return False
       └─ Error DB? → Return True (fallback: jangan blokir user)
       │
  Kuota habis? ──Yes──► Reply: DAILY_LIMIT_REACHED → STOP
       │No
       ▼
send_chat_action(TYPING)   ← tampilkan indikator "sedang mengetik"
       │
       ▼
Reply loading message: "⏳ Sedang mencari jawaban..."
       │
       ▼
asyncio.to_thread(chat, query=text, session_id=user_id)
  └─ Panggil ai_services.chat() di thread terpisah
     (agar event loop Telegram tidak terblokir)
       │
       ▼
Format jawaban HTML:
  ├─ html.escape(answer) → amankan karakter <, >, &
  └─ Tambahkan sumber: "📚 Sumber:\n  • Section — Title (Buku Panduan KKP)"
       │
       ▼
loading_message.edit_text(final_answer)
  └─ Ganti pesan loading dengan jawaban final
       │
       ▼
asyncio.create_task(log_chat_to_db(...))
  └─ Simpan ke tabel "chat_logs" di background (tidak blokir)
```

---

## `messages.py` — Template Pesan

File sederhana berisi semua teks yang dikirim bot.

```
WELCOME       → Pesan sambutan saat /start
HELP          → Penjelasan cara pakai saat /help
DAILY_LIMIT_REACHED → Notifikasi kuota harian habis
GENERIC_ERROR → Pesan error umum
LOADING       → Pesan sementara saat proses berjalan
EMPTY_ANSWER_FALLBACK → Jika jawaban kosong
```

> **Mengapa dipisahkan?** Agar mudah mengubah teks tanpa menyentuh logika program.
