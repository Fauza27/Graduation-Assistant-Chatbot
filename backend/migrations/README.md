# Database migrations

File migration di folder ini adalah sumber perubahan schema aplikasi. Jalankan
berdasarkan nama file secara berurutan melalui Supabase SQL Editor atau `psql`.

Setiap file:

- aman dijalankan ulang;
- mencatat versinya ke `public.app_schema_migrations`;
- memakai transaction agar perubahan tidak tersimpan setengah jalan;
- tidak menghapus data aplikasi secara otomatis.

Folder `scripts/` tetap menyimpan migration lama untuk referensi. Perubahan
schema baru harus ditambahkan ke folder ini.
