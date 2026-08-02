# ADR-001: Arsitektur Sistem Utama (FastAPI + Telegram Bot)

## 1. Context (Mengapa keputusan ini perlu dibuat?)
Aplikasi Chatbot KKP/PI ini dirancang untuk membantu mahasiswa menemukan informasi panduan akademik. Sistem harus dapat diakses melalui Telegram Bot (sebagai antarmuka utama pengguna) sekaligus menyediakan REST API yang berpotensi digunakan untuk pengujian (CLI/Evaluasi) atau antarmuka web di masa depan. 

Keterbatasan (*constraints*) utama dalam proyek ini adalah:
- **Budget**: Deployment diupayakan menggunakan infrastruktur gratis atau berbiaya rendah (seperti Google Cloud Run atau Azure Container Apps), yang sangat cocok dengan model *serverless*.
- **Tim Size & Skill**: Proyek ini dikembangkan dalam lingkup penelitian individual, sehingga pemeliharaan arsitektur yang terlalu kompleks akan membebani pengembang.
- **Scale**: Target audiens adalah mahasiswa aktif (ratusan orang), bukan jutaan, dengan lonjakan *traffic* terprediksi (hanya ramai menjelang penyusunan KKP/PI).

Sistem membutuhkan *core engine* RAG (Retrieval-Augmented Generation) yang konsisten, terlepas dari saluran (channel) mana pertanyaan itu masuk.

## 2. Options (Apa saja yang dipertimbangkan?)
Berikut adalah beberapa alternatif arsitektur yang dievaluasi:

1. **Memisahkan Service (Microservices)**: Membangun satu service khusus untuk REST API (engine RAG) dan satu service terpisah (daemon) khusus untuk Telegram Bot yang memanggil REST API tersebut.
2. **Daemon Telegram Bot Murni (Long Polling)**: Hanya menggunakan `python-telegram-bot` yang berjalan terus-menerus menggunakan mode *polling*, tanpa menyediakan REST API sama sekali.
3. **Monolith Serverless (FastAPI + Webhook)**: Menggabungkan *engine* RAG, endpoint REST API, dan *handler* Telegram Bot ke dalam satu aplikasi berbasis FastAPI. Telegram diintegrasikan melalui *Webhook* (atau *Polling* saat *development*), di mana permintaan dari Telegram masuk sebagai *HTTP POST request* ke FastAPI.

## 3. Decision (Apa yang dipilih dan kenapa?)
Kami memutuskan untuk memilih **Opsi 3: Monolith Serverless (FastAPI + Webhook)**.

**Alasan Utama:**
Di konteks ini, **efisiensi biaya (infrastruktur) dan kemudahan pemeliharaan** lebih penting daripada **pembagian *concern* (decoupling) secara ketat**. 
- Opsi 3 memberikan keuntungan di mana kita hanya perlu men-*deploy* dan memelihara satu *container image* (sangat menghemat biaya di Cloud Run/Azure).
- Menggunakan *Webhook* melalui FastAPI memungkinkan container untuk mati (*scale-to-zero*) saat tidak ada *traffic*, menghemat biaya operasional, yang mana tidak mungkin dilakukan jika menggunakan *Long Polling* (Opsi 2).
- Kode pipeline RAG dapat diimpor langsung (melalui pemanggilan fungsi lokal Python) tanpa adanya latensi *network* atau kompleksitas *HTTP call* internal antar-*microservices* (seperti pada Opsi 1).

## 4. Consequence (Apa yang harus diterima?)
Setiap keputusan memiliki harga, dan dengan memilih pendekatan *Monolith Serverless* ini, kita harus menerima beberapa konsekuensi:

1. **Kompleksitas Inisialisasi**: Menyinkronkan siklus hidup (*lifecycle*) aplikasi FastAPI dengan *lifecycle* asinkron `python-telegram-bot` membutuhkan pengelolaan kode yang lebih hati-hati (misalnya, memastikan *bot webhook* disetel saat FastAPI *startup* dan ditutup saat *shutdown*).
2. **Cold Start Latency**: Karena sistem bisa *scale-to-zero*, pengguna pertama yang mengirim pesan ke bot setelah beberapa saat *idle* akan mengalami sedikit jeda waktu tunggu (beberapa detik ekstra) karena *container* harus di-*spin up* terlebih dahulu.
3. **Tidak Stateless Penuh**: Meskipun diusahakan *stateless*, pustaka Telegram Bot kadang menyimpan status kecil di memori (*ConversationHandler* lokal). Jika container di-*restart* atau di-*scale-out* menjadi beberapa *instance*, riwayat percakapan yang belum dipindahkan ke basis data terpusat (seperti Redis/Supabase) bisa hilang, sehingga aplikasi harus dipaksa sedemikian rupa agar benar-benar bergantung pada *database* untuk *state* (atau membatasi pada 1 *instance* konkuren).
