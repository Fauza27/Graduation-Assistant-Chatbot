# Penjelasan Rinci Migrasi Skema Database (Increment 0)

Dokumen ini menjelaskan secara teknis dan kritis alasan di balik setiap baris kode SQL pada file `supabase_migration_multidomain.sql`. Tujuannya adalah agar pengembang memahami dampak dari setiap keputusan desain database terhadap performa, keamanan, dan skalabilitas sistem.

---

## 1. Modifikasi Tabel `parent_documents` & `child_documents`

```sql
ALTER TABLE child_documents ADD COLUMN domain TEXT NOT NULL DEFAULT 'PI'
CHECK (domain IN ('PI', 'KKP', 'SKRIPSI', 'NON_SKRIPSI'));
CREATE INDEX idx_child_documents_domain ON child_documents(domain);
```

### Mengapa menggunakan `TEXT` + `CHECK` alih-alih `ENUM`?
PostgreSQL memiliki tipe data khusus `ENUM` (misal: `CREATE TYPE domain_type AS ENUM ('PI', 'KKP')`). Namun, kita memilih `TEXT` dengan fungsi `CHECK`.
- **Alasan Fleksibilitas:** Menambahkan nilai baru pada ENUM di PostgreSQL seringkali kaku (terutama saat menggunakan Supabase yang bisa jadi membatasi migrasi tipe data di masa depan). Dengan `TEXT` dan `CHECK`, kita cukup melakukan `ALTER TABLE ... DROP CONSTRAINT` lalu menambahkannya kembali dengan mudah jika ada domain ke-5 di masa depan.
- **Performa:** Untuk kardinalitas rendah (hanya 4 pilihan unik), tipe data `TEXT` dengan panjang karakter pendek ('PI', 'KKP') tidak memiliki penalti performa yang signifikan dibandingkan `ENUM`.

### Mengapa perlu `DEFAULT 'PI'`?
Karena tabel Anda sudah memiliki data (hasil *restore*), menambahkan kolom baru dengan aturan `NOT NULL` akan **gagal total/error** karena PostgreSQL bingung apa isi dari kolom tersebut untuk data yang sudah ada. 
- Kita mengakali ini dengan memberikan nilai `DEFAULT 'PI'`. Semua data yang baru Anda restore sekarang akan memiliki domain 'PI'.
- Nanti, Anda cukup menjalankan kueri sederhana untuk memperbaiki data KKP: `UPDATE child_documents SET domain = 'KKP' WHERE source LIKE '%KKP%';` (berdasarkan nama sumber dokumennya).

### Mengapa membuat Index `idx_child_documents_domain`?
*Hybrid search* berbasis vektor sangat rakus resource. Jika seorang mahasiswa bertanya *"Apa syarat sidang skripsi?"*, sistem Anda akan mem-filter: `WHERE domain = 'SKRIPSI'`.
- **Tanpa Index:** PostgreSQL akan melakukan **Sequential Scan**, yaitu membaca seluruh potongan tabel satu per satu dari atas ke bawah hanya untuk mencari mana yang berlabel 'SKRIPSI'. Semakin banyak data, semakin lambat.
- **Dengan Index:** (Menggunakan B-Tree default), PostgreSQL langsung "melompat" secara instan ke kumpulan baris yang berlabel 'SKRIPSI'. Ini akan memangkas waktu pencarian secara drastis saat koleksi dokumen semakin bengkak.

---

## 2. Pembuatan Tabel `mahasiswa_accounts`

```sql
CREATE TABLE mahasiswa_accounts (
    mahasiswa_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL, ...
);
```

### Mengapa `UUID` dan bukan `SERIAL` (Integer 1, 2, 3...)?
- **Mencegah ID Enumeration (Security):** Jika menggunakan ID berurutan, peretas bisa dengan mudah menebak URL seperti `/api/user/12`, `/api/user/13`. UUID (`e.g., 550e8400-e29b-41d4-a716-446655440000`) mencegah hal ini karena bersifat acak kriptografik.
- **Skalabilitas:** Pembuatan UUID dilakukan dengan fungsi bawaan `gen_random_uuid()` (v4). Sangat ideal untuk sistem terdistribusi.

### Mengapa identifier-nya `google_sub` dan bukan `email`?
Ini adalah detail krusial dalam penerapan OAuth. 
- Di Google, seorang pengguna **bisa mengganti alamat email mereka**, namun ID Internal Google mereka (**Subject ID / `sub`**) bersifat permanen.
- Jika Anda mengaitkan akun berdasarkan `email`, saat mahasiswa mengganti email Google-nya, sistem akan mengira dia pengguna baru. Dengan `google_sub`, identitasnya tidak akan pernah salah.

### Mengapa tipe waktunya `TIMESTAMPTZ` (Timestamp with Time Zone)?
Banyak pengembang keliru menggunakan `TIMESTAMP` (tanpa zona waktu).
- `TIMESTAMPTZ` memaksa database menyimpan waktu secara absolut dalam format **UTC (Coordinated Universal Time)**.
- Ketika data ini ditarik ke _frontend_ atau _backend_, format UTC akan otomatis dikonversi dengan aman mengikuti zona waktu komputer lokal (misal: WITA / GMT+8). Ini mencegah bug pergeseran jam.

---

## 3. Modifikasi Tabel `conversation_sessions`

```sql
ALTER TABLE conversation_sessions ADD COLUMN mahasiswa_id UUID REFERENCES mahasiswa_accounts(mahasiswa_id) ON DELETE SET NULL;
```
### Mengapa Foreign Key `ON DELETE SET NULL`?
- Jika suatu hari ada mahasiswa yang meminta akunnya dihapus, kita **tidak ingin riwayat percakapannya (chat logs) ikut terhapus otomatis** dari database, karena data obrolan tersebut masih berguna untuk analitik (menilai performa LLM, topik paling populer, dll).
- Dengan `ON DELETE SET NULL`, jika akun terhapus, maka `mahasiswa_id` di tabel sesi hanya akan berubah menjadi `NULL` (menjadi anonim), tetapi isi pesannya tetap utuh.

---

## 4. Pembuatan Tabel `chunk_edit_logs`

```sql
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'success', 'failed')),
```

### Mengapa status ini penting (State Machine)?
Tabel ini bukan sekadar riwayat (*Audit Trail*), tetapi juga berfungsi sebagai **antrian eksekusi (Queue)**.
- Ketika admin mengedit isi chunk, sistem tidak boleh langsung meniban vektor saat itu juga jika API OpenAI sedang *down* atau *rate-limited*.
- Sistem akan mencatat dengan status `pending`. Backend Anda akan menangkapnya, mengubah status ke `processing` (agar jika ada 2 admin mengklik bersamaan, tidak dieksekusi ganda), men-generate vektor ke OpenAI, lalu jika berhasil mengubahnya jadi `success`. Jika gagal, status menjadi `failed` dan teks aslinya tidak jadi rusak.
- Ini memastikan **Integritas Data** antara teks dan *embedding vector*-nya tidak pernah meleset.
