# Pemilihan model LLM chatbot (30 September 2026)

## Pilihan dan harga

| Model | Input / 1 juta token | Output / 1 juta token | Catatan |
| --- | ---: | ---: | --- |
| GPT-4o mini (sebelumnya) | US$0,15 | US$0,60 | Lebih murah dari GPT-4.1 mini, tetapi kalah pada replay pengembangan ini. |
| GPT-4.1 mini | US$0,40 | US$1,60 | Kandidat non-reasoning yang lebih mahal; tidak diuji pada dataset ini. |
| **GPT-6 Luna (dipilih)** | **US$0,10** | **US$0,50** | Lebih banyak jawaban benar dan biaya tercatat lebih rendah pada replay ini. |

Harga di atas adalah tarif standar tanpa diskon *cached input*, Batch, atau Flex. Sumber: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), dan [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). Model Luna mendukung `reasoning_effort="none"`; API menolak `temperature=0`, sehingga pembuatan klien LLM disatukan agar parameter setiap model kompatibel.

## Bukti pengujian

Sebelum perubahan, GPT-4o mini dengan reranker nonaktif menjawab 127 dari 158 kasus yang dapat dinilai dengan benar dalam replay 163 pertanyaan. Setelah pengguna memberi izin spesifik, GPT-6 Luna diuji pada 163 pertanyaan yang sama dan menjawab 142 dari 158 kasus dengan benar. Rincian penilaian, perbandingan berpasangan, biaya, latency, contoh kesalahan, dan batas klaim ada di [laporan replay penuh](llm-full-comparison-20260930.md). Ini tetap regresi pengembangan, bukan pengujian akhir yang independen.

## Perubahan aplikasi

`LLM_MODEL` disetel menjadi `gpt-6-luna` pada konfigurasi bawaan, contoh lingkungan, dan `.env` lokal. `src/services/chat_model.py` sekarang membuat klien yang sama untuk generation, reformulasi, ringkasan, evaluator agent, dan RAGAS; Luna menggunakan `reasoning_effort="none"` tanpa `temperature`, sedangkan model lama tetap memakai `temperature=0`. Tarif Luna ditambahkan ke `config/pricing.yaml` agar monitoring biaya tidak mencatat nol. Tidak ada perubahan database.

Perubahan ini dapat dibalik hanya dengan mengubah `LLM_MODEL`; untuk GPT-4o mini, parameter lama tetap didukung. Uji ulang dengan pertanyaan baru dan lebih dari satu replay per model masih diperlukan sebelum menyatakan peningkatan umum di luar dataset pengembangan.
