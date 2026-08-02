"""
Pesan-pesan teks untuk Telegram bot.
Format konsisten menggunakan HTML (parse_mode=HTML).
"""

WELCOME = """
👋 <b>Halo, {first_name}!</b>

Selamat datang di Chatbot KKP/PI Assistant!

Kamu bisa bertanya apa saja terkait tentang Kuliah Kerja Praktik (KKP) atau Penelitian Ilmiah (PI)
""".strip()


HELP = """
🤖 <b>Bantuan Chatbot KKP/PI</b>

Saya adalah asisten yang dapat membantu Anda dengan pertanyaan seputar:
• Kuliah Kerja Praktik (KKP)
• Penulisan Ilmiah (PI)

<b>Cara menggunakan:</b>
• Ketik pertanyaan Anda langsung
• Contoh: "Apa syarat untuk mengambil KKP?"
• Contoh: "Bagaimana format penulisan PI?"

<b>Perintah yang tersedia:</b>
/start - Mulai percakapan
/help - Tampilkan bantuan ini

Silakan ajukan pertanyaan Anda!
""".strip()


# {limit} akan diisi dengan settings.RATE_LIMIT_REQUESTS
DAILY_LIMIT_REACHED = (
    "⚠️ <b>Batas Limit Harian Tercapai</b>\n\n"
    "Maaf, Anda telah menggunakan jatah {limit} pertanyaan untuk hari ini "
    "guna menghemat biaya server. Silakan kembali lagi besok hari ya! 🎓"
)


GENERIC_ERROR = "Maaf, terjadi kesalahan. Silakan coba lagi."

LOADING = "⏳ Sedang mencari jawaban..."

EMPTY_ANSWER_FALLBACK = "Maaf, saya belum bisa menjawab sekarang."
