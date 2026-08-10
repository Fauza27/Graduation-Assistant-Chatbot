# Pseudocode untuk `scripts/supabase_session_migration.sql`

```markdown
ALGORITMA MIGRASI PENYIMPANAN SESI KE DATABASE (supabase_session_migration.sql)

1. PEMBUATAN TABEL SESI PERCAKAPAN
   - Buat tabel `conversation_sessions` (jika belum ada) dengan struktur:
     - session_id (TEXT, Primary Key): ID unik untuk sesi obrolan.
     - turns (JSONB): Menyimpan riwayat percakapan (array tanya-jawab) (Default: '[]').
     - last_access (Timestamp): Kapan sesi ini terakhir digunakan (untuk penghapusan idle).
     - created_at (Timestamp): Kapan sesi ini dibuat.

2. PEMBUATAN INDEKS
   - Buat indeks pada kolom `last_access` untuk mempercepat pencarian dan penghapusan sesi yang sudah kedaluwarsa (idle cleanup).
   - Buat indeks pada kolom `created_at` untuk keperluan analisis dan pelacakan umur sesi.

3. PENGATURAN KEAMANAN (Row Level Security)
   - Aktifkan fitur RLS (Row Level Security) pada tabel `conversation_sessions`.
   - Hapus aturan akses (policy) yang sudah ada agar tidak terjadi duplikasi.
   - Buat Aturan BACA:
     - Hanya user database dengan peran `service_role` (sistem internal backend) yang diizinkan untuk melihat/membaca (SELECT) data sesi.
   - Buat Aturan TULIS:
     - Hanya user dengan peran `service_role` yang diizinkan untuk menambah atau memodifikasi (INSERT/UPDATE/DELETE) data sesi.

4. FUNGSI PENGHAPUSAN SESI KEDALUWARSA (cleanup_idle_sessions)
   - INPUT: Batas waktu tunggu/TTL dalam detik (p_ttl_seconds, default 3600 detik/1 jam).
   - OUTPUT: Jumlah sesi yang berhasil dihapus (Integer).
   - ALGORITMA:
     - HAPUS baris dari tabel `conversation_sessions` DI MANA `last_access` lebih lama dari (WAKTU_SEKARANG dikurangi interval detik p_ttl_seconds).
     - Simpan jumlah baris yang berhasil dihapus ke dalam variabel.
     - Tampilkan log peringatan (NOTICE) ke konsol sistem.
     - KEMBALIKAN jumlah baris yang dihapus.

5. FUNGSI STATISTIK SESI (get_session_statistics)
   - OUTPUT: Tabel rekap data (total sesi, sesi aktif 1 jam, sesi aktif 24 jam, rata-rata panjang chat, sesi tertua, sesi terbaru).
   - ALGORITMA:
     - Hitung total baris sesi.
     - Hitung sesi yang aktif dalam 1 jam terakhir (berdasarkan last_access).
     - Hitung sesi yang aktif dalam 24 jam terakhir.
     - Hitung rata-rata jumlah elemen dalam array JSONB `turns` (menggunakan avg() dan jsonb_array_length()).
     - Cari waktu paling awal (MIN) di `created_at`.
     - Cari waktu paling akhir (MAX) di `created_at`.
     - KEMBALIKAN semua nilai tersebut sebagai tabel (Record).

6. PENANDA MIGRASI
   - Coba masukkan data rekam jejak migrasi ke dalam tabel `user_quotas` dengan user_id '_system_migration'.
   - Jika sudah ada, abaikan (DO NOTHING).
   - Kembalikan teks status "Session storage migration completed successfully".
```
