# Pseudocode untuk `scripts/supabase_migration_quota_rpc.sql`

```markdown
ALGORITMA FUNGSI PENAMBAHAN KUOTA USER (supabase_migration_quota_rpc.sql)

1. DEFINISI FUNGSI
   - Nama: `increment_quota_if_under_limit`
   - Input/Parameter: 
     - p_user_id (Teks): ID unik dari pengguna.
     - p_date (Teks): Tanggal dalam format YYYY-MM-DD.
     - p_daily_limit (Angka/Integer): Batas maksimal pesan yang diizinkan per hari.
   - Output/Kembalian:
     - Boolean (TRUE jika sukses ditambah, FALSE jika gagal karena sudah melebihi limit).
   - Bahasa: plpgsql (prosedural SQL PostgreSQL).

2. ALGORITMA UTAMA (Proses Atomik Upsert)
   - Deklarasikan variabel internal `v_new_count` untuk menyimpan jumlah pesan terbaru.
   - COBA masukkan data pengguna ke tabel `user_quotas` (user_id, date, message_count bernilai 1).
   - JIKA data sudah ada sebelumnya (Terjadi konflik/duplikasi pada user_id dan date yang sama):
     - LAKUKAN UPDATE (Tambahkan message_count dengan 1).
     - SYARAT UPDATE (WHERE): Lakukan update hanya jika `message_count` saat ini masih di bawah batas (`< p_daily_limit`).
   - KEMBALIKAN (RETURNING) nilai `message_count` terbaru ke dalam variabel `v_new_count`.

3. PENGECEKAN HASIL
   - JIKA `v_new_count` bernilai NULL:
     - Artinya, baris tidak di-update karena gagal memenuhi syarat WHERE (kuota sudah penuh atau sama dengan limit).
     - KEMBALIKAN nilai FALSE.
   - SELAIN ITU (Jika berhasil):
     - KEMBALIKAN nilai TRUE.
```
