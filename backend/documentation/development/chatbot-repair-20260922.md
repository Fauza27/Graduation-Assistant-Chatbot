# Perbaikan chatbot berdasarkan percakapan mahasiswa

## Ruang lingkup dan sumber

Analisis dilakukan terhadap baseline `manual-conversation-baseline-20260921`:
20 sesi, 163 pertanyaan, jawaban tersimpan, dan 163 execution trace dari Supabase.
Database dibaca saja. Hasil penelitian lama tidak ditimpa dan agent tidak dijalankan.
Dokumen pembanding adalah panduan dalam `extract-pdf`, beserta snapshot 175
parent dan 373 child database. Pemeriksaan isi terarah dilakukan pada kasus
representatif; belum semua jawaban diberi penilaian manual benar/salah.

Artefak lokal:

- `results/chatbot_repair/baseline_trace_audit.json`: audit mekanis semua request,
  termasuk jawaban lama, query, konteks, dan simulasi seleksi dengan skor lama.
- `tests/fixtures/chatbot_gate_regressions.json`: empat kasus nyata dengan skor
  tersimpan dan parent relevan yang diperiksa manual.
- `results/chatbot_repair/replay-initial.json`: percobaan API yang gagal karena
  saldo habis; bukan hasil evaluasi kualitas setelah perbaikan.

## Temuan yang terbukti

1. **85/163 request tidak memiliki konteks akhir.** Pada seluruh 85 request ini,
   semua kandidat dibuang oleh ambang skor absolut `0.0`. Ini bukan jumlah
   jawaban salah: sebagian pertanyaan memang tidak memiliki jawaban eksplisit.
2. **43 request yang ditulis ulang tetap direrank dengan pertanyaan mentah.**
   Domain atau rujukan yang sudah diselesaikan untuk pencarian hilang lagi
   ketika reranker memilih konteks.
3. Pemicu reformulasi terlalu sempit. `ipknya`, `berkas yang harus saya upload`,
   `minimal berapa kali`, dan pertanyaan hasil/pembahasan bisa dicari tanpa
   konteks percakapan.
4. Aturan lama mengambil topik dari jawaban assistant terbaru. Jawaban salah
   tentang KKP dapat menggantikan topik Skripsi yang dipilih pengguna.
5. Mengganti `ujiannya` dengan `ujian Skripsi` menghilangkan tahap akademik.
   Menambahkan domain terakhir pada `kalau KKP sama juga?` menghasilkan query
   campuran PI/KKP tanpa menjelaskan atribut yang dibandingkan.
6. Instruksi generasi mengizinkan riwayat sebagai sumber fakta, sehingga
   jawaban lama yang keliru bisa diulang ketika retrieval kosong.
7. Dedup teks lintas domain bisa menghapus salah satu sumber pada perbandingan.

## Contoh audit isi

| Kasus | Bukti dan masalah |
| --- | --- |
| Sesi 1.1, syarat Skripsi | Panduan Skripsi 2.5 memuat 138 SKS dan IPK 3,25. `parent-skripsi-010` berada pada peringkat pertama reranker dengan skor -3,81585, lalu dibuang bersama seluruh kandidat. |
| Sesi 1.2, SKS/IPK lanjutan | Query tidak memuat konteks Skripsi; hasil KKP dipilih dan jawaban memakai 100 SKS/2,00. |
| Sesi 1.3, IPK 3,20 | Query lama sudah berubah menjadi terkait KKP setelah jawaban keliru sebelumnya. |
| Sesi 1.7, mulai bimbingan | Panduan Skripsi 2.6.1 mewajibkan menemui pembimbing paling lambat satu minggu; jawaban lama justru menyatakan tidak ada ketentuan untuk segera bimbingan. Query tidak membawa domain. |
| Sesi 2.5, penyempurnaan judul | Panduan Skripsi 2.4.3 membedakan penyempurnaan judul tanpa mengubah inti masalah dan pengajuan judul baru kepada kaprodi. Jawaban lama menggeneralisasi bahwa setiap koreksi kecil perlu pengajuan ulang. Konteks request kosong. |
| Sesi 7.3, PI tanpa instansi | Panduan PI 2.5–2.6 dan `parent-006` membolehkan studi literatur/riset mandiri tanpa instansi. Jawaban lama mewajibkan tempat penelitian. Perlu uji jawaban ulang setelah perbaikan. |
| Sesi 17.1, Web Developer | Panduan Non-Skripsi 3.2.3 dan `parent-non-skripsi-028` menyebut Web Developer. Parent itu peringkat pertama tetapi ditolak karena skor -1,67. Tetap perlu menyebut ketentuan lain; pekerjaan ini tidak otomatis memenuhi seluruh syarat. |
| Sesi 17.5–6, produk tim dan penilaian atasan | Panduan Non-Skripsi 3.2.2 secara eksplisit mengizinkan produk tim/individu dan mensyaratkan dokumen evaluasi. Pertanyaan lanjutan perlu mempertahankan jalur profesional. |
| Sesi 19.4, hasil dan pembahasan | Sistematika Non-Skripsi profesional/wirausaha memakai BAB III. Jawaban lama mengambil BAB IV dari PI/Skripsi karena query tidak mempertahankan domain/jalur. |

Beberapa sesi dimulai dengan pertanyaan ambigu, seperti seminar proposal tanpa
menyebut Skripsi/Non-Skripsi atau “jalur ini” tanpa percakapan sebelumnya.
Nama sesi pada dataset bukan konteks yang diterima chatbot. Jangan memasukkan
nama sesi diam-diam saat pengujian ulang. Klarifikasi yang tepat merupakan
hasil yang sah; bukan seluruh penolakan harus diubah menjadi jawaban pasti.

## Perubahan kode

- Normalisasi `sempro` dan `semhas` menjadi istilah lengkap.
- Reformulasi mencakup pertanyaan tanpa domain dan rujukan informal. Satu
  pemanggilan LLM menyelesaikan domain, tahap, jalur, dan atribut pertanyaan.
- Aturan penggantian kata ganti dengan domain dihapus. Riwayat pengguna menjadi
  acuan utama; domain eksplisit pada pertanyaan terbaru tidak boleh dihapus
  oleh hasil reformulasi. Kegagalan rewriter mengembalikan query asli.
- Reranker memakai query yang sudah diselesaikan, sama seperti pencarian.
- Ambang skor absolut menjadi opsional (`None` secara default). Relative gap
  dan top-N tetap berlaku. Jika lingkungan menyetel `RERANK_MIN_TOP_SCORE`,
  ambang eksplisit itu tetap dihormati.
- Dedup teks dibatasi pada sumber dan parent yang sama.
- Prompt membedakan riwayat percakapan dari bukti dokumen, melarang penambahan
  aturan umum, dan membedakan “belum ditemukan dalam konteks” dari “tidak ada
  dalam seluruh panduan”.
- Status konteks kosong tidak lagi selalu menyalahkan ambang relevansi. Pesan
  sekarang juga benar untuk pencarian kosong atau gangguan dependency.

Tidak ada migrasi SQL atau perubahan isi dokumen/database. Model tetap sama.
Reformulasi lebih sering dipanggil pada percakapan kontekstual; biaya dan latency
tambahan perlu diukur saat API tersedia. Prompt yang lebih ketat juga belum
menjamin semua halusinasi hilang.

## Validasi dan batas hasil

Validasi akhir: 266 test backend lulus, Ruff pada seluruh file perubahan
chatbot lulus, dan `git diff --check` lulus. Tiga peringatan deprecation
dependency yang sudah ada tetap muncul. Pemeriksaan Ruff seluruh repository
masih menemukan masalah lama pada arsip eksperimen, bot Telegram, dan skrip
database yang berada di luar perubahan ini.

Test menggunakan skor asli membuktikan empat parent relevan yang dahulu
ditolak kini lolos seleksi. Ini membuktikan perbaikan seleksi, bukan akurasi
jawaban end-to-end. Unit test memeriksa pemicu konteks, penjagaan domain,
summary-only memory, penggunaan query rerank, dan provenance dedup.

Replay reranker lokal dengan model yang sudah tersimpan juga menempatkan bukti
yang benar pada posisi pertama untuk syarat Skripsi, kewajiban bimbingan
Skripsi, dan BAB hasil/pembahasan Non-Skripsi. Kasus perbandingan PI–KKP belum
bisa dinilai dengan replay kandidat lama karena kandidat KKP yang diperlukan
tidak ada pada hasil retrieval lama; kasus ini memerlukan pencarian baru.

Percobaan live dibatasi pada 18 pertanyaan dalam enam sesi. API embedding dan
generasi mengembalikan `credit_balance_exhausted` pada pertanyaan pertama.
Tidak ada jawaban baru yang berhasil dibuat. Pengujian semantik lanjutan,
terutama pertanyaan tanpa jawaban dan perbandingan lintas domain, masih perlu
dijalankan sebelum menyatakan kualitas meningkat.

Pengulangan setelah saldo tersedia:

```powershell
.\virtual_environment\Scripts\python.exe scripts/run_chatbot_replay.py tmp/agent-research-complete-20260921.json --sessions 1 3 14 17 19 20 --limit 3 --output results/chatbot_repair/replay-next.json
```

Script menggunakan API berbayar, retrieval nyata, dan memory lokal baru per
sesi. Jawaban lama hanya disimpan sebagai pembanding. Script tidak menulis
session, metrics, atau hasil evaluasi ke database. Cakupannya komponen RAG,
bukan pengujian HTTP, autentikasi, atau persistensi session. Gunakan nama output
baru karena file hasil yang sudah ada sengaja tidak boleh ditimpa.
