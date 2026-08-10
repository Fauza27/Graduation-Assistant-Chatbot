ALGORITMA HALAMAN CHAT

1. STATE GLOBAL (di `lib/store.ts` menggunakan Zustand)
   - `session_id`: ID unik percakapan (string | null), inisialisasi dengan `null`.
   - `messages`: Daftar pesan obrolan (array of object), inisialisasi kosong `[]`.
   - `hasHydrated`: Status rehidrasi `localStorage` (boolean), inisialisasi `false`.
   - **Konfigurasi Middleware Persist**:
     - Gunakan middleware `persist` dari Zustand agar data `session_id` dan `messages` otomatis disimpan ke `localStorage`.
     - Manfaatkan callback `onRehydrateStorage` untuk mengubah `hasHydrated` menjadi `true` setelah proses muat data selesai (mencegah *race condition* di Next.js).
   - **Aksi (Actions)**:
     - `addMessage(role, text, sources)`: Menambahkan pesan baru ke array `messages`.
     - `setMessages(messages)`: Mengganti seluruh pesan sekaligus (saat memuat riwayat).
     - `resetSession()`: Menghapus array `messages` dan set `session_id` ke UUID baru.
     - `setHydrated()`: Set status hidrasi.

2. EFEK SAMPING (useEffect)
   - Scroll ke bagian bawah (bottom) setiap kali `messages` bertambah.
   - Jika halaman chat pertama kali dimuat:
     - TUNGGU hingga `hasHydrated` bernilai `true` (menghindari penimpaan sesi yang sedang direstorasi dari *local storage*).
     - Jika `hasHydrated` bernilai `true` DAN `session_id` masih null, panggil `resetSession()`.

3. FUNGSI handleSendMessage()
   - JIKA `inputValue` kosong, abaikan.
   - Tambahkan pesan user ke `messages` dengan role="user".
   - Set `inputValue` menjadi kosong.
   - Set `isLoading` = true (tampilkan animasi mengetik bot).
   - PANGGIL `sendChatMessage(teks, session_id)` dari `lib/api.ts`.
   - SETELAH DAPAT BALASAN:
     - Set `isLoading` = false.
     - Tambahkan pesan bot ke `messages` dengan role="bot", teks jawaban, dan `sources`.
   - JIKA ERROR:
     - Set `isLoading` = false.
     - Tambahkan pesan bot berisi error (misal kuota habis).

4. FUNGSI handleDeleteSession()
   - Munculkan tombol "Hapus Percakapan" pada menu dropdown (kebab icon di pojok kanan atas layar chat).
   - (*Catatan: Sesuai desain v4, penghapusan HANYA dapat dilakukan dari dalam sesi aktif ini, bukan dari daftar riwayat di sidebar*).
   - Saat tombol ditekan, munculkan konfirmasi `window.confirm`.
   - Jika `Yes`: 
     - Panggil API `DELETE NEXT_PUBLIC_API_BASE_URL/api/sessions/{session_id}` dengan Bearer token.
     - Tunggu respon API, lalu panggil `resetSession()` agar UI kembali bersih dan membuat ID baru.
     - Jika gagal, tampilkan notifikasi error.

5. RENDER TAMPILAN
   - Header Desktop ("Chat").
     - Terdapat menu *dropdown* (kebab menu) berisi opsi **"Hapus Percakapan"**. Jika di-klik, panggil `handleDeleteSession()`.
   - Container Chat (Bisa di-scroll).
     - JIKA `messages` kosong: Tampilkan UI "Mulai percakapan baru" beserta saran (*chips*).
     - JIKA ada: Looping array `messages`:
       - JIKA role "user": Tampilkan teks di dalam *bubble* (bubble ungu).
       - JIKA role "bot": 
         - **Sesuai desain Increment 2**: JANGAN TAMPILKAN BUBBLE.
         - Gunakan `react-markdown` untuk me-render teks jawaban agar format (bold, list) dari LLM tampil rapi.
         - Tampilkan avatar bot kecil di sebelah kiri.
         - JIKA ada array `sources`: Tampilkan komponen `<CitationCard />`.
           - **Perbaikan UI:** Pastikan referensi (`src`) dibungkus dengan `String(src)` sebelum melakukan `.substring()` karena data sumber (terutama dari riwayat database) dapat berupa objek atau array.
     - JIKA `isLoading` true: Tampilkan animasi "typing" bot.
   - Composer (Input Teks + Tombol Kirim).
