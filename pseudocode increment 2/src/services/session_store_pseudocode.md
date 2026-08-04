# Pseudocode untuk `src/services/session_store.py`

```markdown
ALGORITMA PENYIMPANAN SESI DATABASE (session_store.py)

1. IMPOR PUSTAKA & INISIALISASI
   - `time`, Threading Lock, lru_cache, loguru, Supabase client, datetime.
   - Konfigurasi aplikasi.

2. KELAS DatabaseSessionStore
   - Tujuan: Menyimpan data percakapan user (memori) secara permanen di database Supabase, namun tetap menggunakan RAM lokal (Cache LRU) untuk sesi yang sedang aktif agar aksesnya super cepat.
   
   - `__init__(cache_size)`:
     - Buka koneksi Supabase.
     - Siapkan Cache lokal (`_cache`) dan waktu akses (`_cache_access`).
     - Jalankan `_test_connection()` (cek apakah tabel ada).
   
   - `load_memory(session_id)`:
     - TAHAP 1: Cek Cache Lokal.
       - Jika data sesi ini ada di RAM, perbarui waktu aksesnya, lalu langsung kembalikan datanya (sangat cepat).
     - TAHAP 2: Jika tidak ada di RAM, Cek Database.
       - Lakukan query ke Supabase (tabel `conversation_sessions`).
       - JIKA ADA: bangun kembali objek `ConversationMemory` dari data JSON tersebut.
       - JIKA TIDAK ADA / ERROR: Buat `ConversationMemory` baru yang kosong.
     - TAHAP 3: Simpan ke Cache Lokal.
       - Masukkan data tadi ke Cache lokal lewat `_add_to_cache()`.
       - Perbarui kolom waktu akses terakhir (last_access) di Database secara diam-diam (*fire and forget*) menggunakan representasi waktu UTC *timezone-aware* (`datetime.now(timezone.utc).isoformat()`).
       - Kembalikan memori.

   - `save_memory(session_id, memory)`:
     - Ubah `memory` jadi bentuk JSON (dict).
     - Lakukan *Upsert* (Insert atau Update) ke database Supabase.
     - Perbarui Cache lokal.
     - Jika gagal (koneksi terputus dll), lempar error (tapi aplikasinya dirancang untuk mengabaikan error ini agar chat tetap jalan).

   - `delete_session(session_id)`:
     - Hapus baris sesi di database.
     - Hapus sesi tersebut dari Cache lokal.

   - `cleanup_idle_sessions(ttl_seconds)`:
     - Panggil prosedur Supabase (RPC `cleanup_idle_sessions`) untuk otomatis menghapus sesi-sesi yang `last_access`-nya sudah terlalu lama.
     - Hapus juga sesi yang sudah tua (kedaluwarsa) dari Cache lokal.

   - `_add_to_cache(session_id, memory, access_time)`:
     - Masukkan sesi ke RAM.
     - JIKA Cache Penuh (kapasitas terlampaui):
       - Cari sesi yang Paling Lama Tidak Diakses (Least Recently Used / LRU).
       - Usir (Evict) sesi tersebut dari RAM (hanya dari RAM, di database tetap aman).

3. FUNGSI get_session_store()
   - Pola *Singleton*: Pastikan hanya ada satu objek `DatabaseSessionStore` di seluruh aplikasi yang dibagi-pakai oleh semua request chat.
   - Set kapasitas cache lokal ke 10% dari Maksimal Sesi Aktif.
```
