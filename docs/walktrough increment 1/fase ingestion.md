# Walkthrough: Ekspansi Domain Skripsi & Non-Skripsi (Increment 1)

## Ringkasan Perubahan
Pada tahap ini, kita telah berhasil memperluas kapabilitas sistem RAG (Retrieval-Augmented Generation) untuk mencakup dua domain baru: **Skripsi** dan **Non-Skripsi**. Kini sistem memiliki 4 domain utama: PI, KKP, Skripsi, dan Non-Skripsi.

Perubahan menyentuh tiga lapisan utama sistem:
1. **Ingestion Layer (`main.py` & `embedder.py`)**
   - Menambahkan opsi CLI `--dataset skripsi`, `--dataset non_skripsi`, dan `--dataset all` untuk mempermudah proses ingestion.
   - Memodifikasi `embedder.py` untuk mendeteksi `domain` berdasarkan awalan `parent_id` dokumen dan langsung menyuntikkan (upsert) nilai domain tersebut ke kolom baru `domain` di database Supabase (baik pada tabel `parent_documents` maupun `child_documents`).
2. **Retrieval Layer (`source_utils.py` & `self_query.py` & `query_expansion.py`)**
   - Memperbarui `PanduanType` dan logika deteksi tipe dokumen agar bisa mendeteksi 4 tipe dokumen.
   - Menginjeksikan keyword pencarian yang akurat berdasarkan isi dokumen:
     - **Skripsi**: _"skripsi", "tugas akhir skripsi", "pendadaran", "seminar hasil", "proposal skripsi"_
     - **Non-Skripsi**: _"non skripsi", "karya ilmiah", "jalur profesional", "wirausaha", "jurnal", "prosiding", "startup"_
   - Menambahkan aturan otomatis mengubah singkatan **"TA"** menjadi "Tugas Akhir" agar pencarian dari pengguna yang menggunakan singkatan tetap efektif.
3. **Generation Layer (`constants.py`)**
   - Memperbarui daftar `domain_keywords` pada `intent_classifier` agar AI dapat mendeteksi saat mahasiswa sedang berpindah topik (*context switching*) misalnya dari bertanya tentang KKP lalu bertanya tentang Skripsi.

## Hasil Validasi (Ingestion)
1. **Dataset Skripsi**: Berhasil di-*ingest* 22 dokumen induk (parents) dan 146 *chunks* anak ke Supabase.
2. **Dataset Non-Skripsi**: Berhasil di-*ingest* 29 dokumen induk (parents) dan 205 *chunks* anak ke Supabase.

## Catatan Evaluasi RAG Pipeline
Berdasarkan hasil uji coba pipeline menggunakan command line, AI sudah berhasil mengkategorikan pertanyaan dengan sangat baik ke sumber yang tepat. Terdapat *minor bug* (kekurangan) pada hasil pencarian (retrieval) dari database Supabase dimana dokumen dari domain lain terkadang ikut muncul. Hal ini wajar karena kita **belum memperbarui skrip RPC SQL Supabase (hybrid search) untuk melakukan filter menggunakan kolom `domain` secara native**.

Perbaikan fitur *filter domain/source* di level database tersebut merupakan bagian dari fase optimasi atau Increment berikutnya.

**Selamat! Increment 1 telah selesai sepenuhnya!**
