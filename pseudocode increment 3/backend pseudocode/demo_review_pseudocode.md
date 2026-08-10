# Pseudocode untuk `demo_review.py`

```markdown
ALGORITMA REVIEW OTOMATIS DOKUMEN WORD (demo_review.py)

1. IMPOR PUSTAKA
   - docx (Document, Pt, Cm, Inches, WD_ALIGN_PARAGRAPH) untuk membaca file .docx
   - Counter, defaultdict dari collections untuk menghitung statistik.
   - re untuk deteksi teks menggunakan regex.

2. KONSTANTA
   - DOCX_PATH: Path file target yang akan direview (misal: "naskah PI\PI_Muhammad_Fauza_BAB1-3.docx").

3. FUNGSI KONVERSI
   - emu_to_cm(emu): Ubah ukuran EMU (English Metric Units) ke sentimeter (cm) dengan membaginya 360.000.
   - pt_to_float(pt_val): Ubah objek Pt dari docx ke angka desimal (float).

4. FUNGSI analyze_document(path: String) -> Dictionary
   - Inisialisasi dictionary `results` untuk menyimpan: margin, font, ukuran, spasi, daftar heading, jumlah kata/paragraf, bab terdeteksi, boolean struktur dokumen (abstrak, daftar isi, dll), tabel, gambar, dan alignment.
   - Buka dokumen docx dengan `Document(path)`.
   
   - TAHAP 1: CEK MARGIN HALAMAN
     - Ambil konfigurasi margin dari bagian (section) pertama dokumen (atas, bawah, kiri, kanan).
     - Konversi nilainya ke sentimeter menggunakan `emu_to_cm` dan simpan ke `results`.
     
   - TAHAP 2: BACA SETIAP PARAGRAF
     - LOOP melalui setiap paragraf di dokumen:
       - Ambil teks paragraf dan hapus spasi berlebih. Jika kosong, abaikan.
       - Tambah 1 ke `paragraph_count`.
       - Tambah jumlah kata paragraf tersebut ke `word_count`.
       - Catat statistik perataan teks (alignment).
       - Catat statistik ukuran spasi baris (line_spacing).
       - LOOP melalui setiap 'run' (potongan teks dengan format seragam) dalam paragraf:
         - Jika run memiliki nama font, catat dan hitung kemunculannya.
         - Jika run memiliki ukuran font, catat dan hitung kemunculannya.
         
     - TAHAP 3: DETEKSI STRUKTUR (Dalam Loop Paragraf)
       - Ubah teks menjadi huruf kecil (lowercase).
       - Cari pola regex "bab [i, ii, iii, iv, v]" di awal teks. Jika ketemu, simpan 60 karakter pertamanya ke daftar BAB.
       - Cek apakah paragraf mengandung kata kunci:
         - "abstrak" (teks pendek < 30 karakter) -> has_abstrak = True
         - "kata pengantar" -> has_kata_pengantar = True
         - "daftar isi" -> has_daftar_isi = True
         - "daftar pustaka" -> has_daftar_pustaka = True
       - Cek format style paragraf, jika style memiliki kata "heading", simpan sebagai bagian dari judul/sub-judul.
       
   - TAHAP 4: HITUNG GAMBAR DAN TABEL
     - Loop melalui relasi dokumen, jika tipe relasi mengandung "image", tambah hitungan `images_count`.
     - Jumlah tabel diambil langsung dari `len(doc.tables)`.
     
   - TAHAP 5: ESTIMASI HALAMAN
     - Estimasi halaman dihitung dari total kata dibagi 250 (rata-rata kata per halaman). Minimal 1 halaman.
     
   - KEMBALIKAN dictionary `results`.

5. FUNGSI print_review(results: Dictionary)
   - Tampilkan laporan hasil review dalam format konsol:
   - Tampilkan pengecekan Margin (standar atas 3, bawah 3, kiri 4, kanan 3). Beri tanda ✅ jika sesuai/mendekati, ❌ jika jauh.
   - Tampilkan top 5 Font yang paling banyak dipakai. Beri tanda ✅ jika "Times New Roman".
   - Tampilkan top 5 Ukuran Font. Beri tanda ✅ jika ukurannya "12.0pt".
   - Tampilkan jenis Spasi Baris yang digunakan.
   - Tampilkan Statistik: estimasi halaman (✅ jika >= 40 halaman), jumlah paragraf, kata, tabel, gambar.
   - Tampilkan Kelengkapan Struktur:
     - Apakah ada Abstrak, Kata Pengantar, Daftar Isi, Daftar Pustaka (✅ atau ❌).
     - Tampilkan list BAB yang berhasil ditemukan.
     - Bandingkan list BAB yang ditemukan dengan ekspektasi (BAB I - BAB V), tampilkan BAB apa saja yang kurang/tidak ada.

6. EKSEKUSI UTAMA (if __name__ == "__main__")
   - Cetak path file yang akan dibaca.
   - Panggil `analyze_document(DOCX_PATH)`.
   - Cetak hasil evaluasi dengan `print_review(results)`.
```
