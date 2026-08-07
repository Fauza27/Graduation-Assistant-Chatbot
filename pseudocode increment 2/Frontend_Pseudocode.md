# Pseudocode Frontend - Increment 2 (Web UI & Integrasi API)

Dokumen ini berisi rancangan *pseudocode* untuk struktur kode *frontend* (menggunakan Next.js App Router, TailwindCSS/Vanilla CSS) pada Increment 2.
Fokus utamanya adalah membangun Antarmuka Pengguna (UI) sesuai `mockup.html` dan mengintegrasikannya dengan backend (Google OAuth, dan Chat API).

---

## 1. STRUKTUR FOLDER & ROUTING (Next.js App Router)

```text
frontend/src/
├── app/
│   ├── layout.tsx             # Root layout (provider auth, font, dll)
│   ├── page.tsx               # Redirector: jika belum login ke /login, jika sudah ke /chat
│   ├── login/                 
│   │   └── page.tsx           # Halaman Login (Tombol Google OAuth)
│   └── (site)/                # Route group untuk halaman yang butuh Auth & Layout Utama
│       ├── layout.tsx         # Layout Utama (Sidebar, Mobile Topbar, Bottom Nav, DocPanel)
│       ├── chat/page.tsx      # Halaman Chat (Utama)
│       ├── riwayat/page.tsx   # Halaman Riwayat Chat
│       └── profil/page.tsx    # Halaman Profil User
├── components/                # Komponen UI Reusable
│   ├── Sidebar.tsx
│   ├── BottomNav.tsx
│   ├── DocPanel.tsx
│   ├── ChatBubble.tsx
│   └── CitationCard.tsx
└── lib/                       # Utilitas & API
    ├── auth.ts                # Logika verify token ke backend, simpan token (sessionStorage)
    ├── api.ts                 # Fetch ke endpoint backend (/api/ai/chat)
    └── store.ts               # State management (Zustand/Context) untuk DocPanel, dll
```

---

## 2. PSEUDOCODE - LIB (API & AUTH)

### `lib/auth.ts`
```markdown
ALGORITMA OTENTIKASI & TOKEN

1. FUNGSI handleGoogleLogin(credentialResponse)
   - Terima token dari Google Identity Services (dari komponen `<GoogleLogin />`).
   - PANGGIL POST `NEXT_PUBLIC_API_BASE_URL/api/auth/google/verify` ke backend dengan body `{ id_token: credentialResponse.credential }`.
   - JIKA sukses:
     - Simpan `access_token` ke dalam `localStorage.setItem('access_token', token)`.
     - Arahkan pengguna ke halaman `/chat`.
   - JIKA gagal: Tampilkan pesan error (alert).

2. FUNGSI getAuthToken()
   - KEMBALIKAN `localStorage.getItem('access_token')`.

3. FUNGSI logout()
   - Hapus token dari `localStorage`.
   - Arahkan pengguna ke `/login`.
```

### `lib/api.ts`
```markdown
ALGORITMA PEMANGGILAN API

1. FUNGSI sendChatMessage(query, session_id)
   - Ambil token lewat `getAuthToken()`.
   - JIKA tidak ada token, paksa logout.
   - PANGGIL POST `NEXT_PUBLIC_API_BASE_URL/api/ai/chat` ke backend.
   - Set Header:
     - `Content-Type: application/json`
     - `Authorization: Bearer <token>`
   - Set Body:
     - `query`: teks dari user
     - `session_id`: ID unik percakapan
     - `channel`: "website"
   - KEMBALIKAN data jawaban JSON dari backend.
   - JIKA error HTTP 401: Token kedaluwarsa, paksa logout.
   - JIKA error HTTP 429: Kembalikan pesan limit harian habis.
```

---

## 3. PSEUDOCODE - HALAMAN UTAMA

### `app/login/page.tsx`
```markdown
ALGORITMA HALAMAN LOGIN

1. RENDER TAMPILAN
   - Tampilkan logo kampus.
   - Tampilkan judul "Selamat datang di Asisten WICIDA".
   - Tampilkan komponen `<GoogleLogin />` (menggunakan pustaka `@react-oauth/google`).
2. EVENT onSuccess (Google Sign-In)
   - Panggil fungsi `handleGoogleLogin(credentialResponse)` dari `lib/auth.ts`.
3. EVENT onError
   - Tampilkan pesan error login gagal.
```

### `app/(site)/layout.tsx`
```markdown
ALGORITMA LAYOUT UTAMA (APP SHELL)

1. INISIALISASI
   - Gunakan `useEffect` untuk memeriksa token di `localStorage`.
   - JIKA sedang mengecek token, tampilkan indikator Loading (menghindari FOUC).
   - JIKA token tidak ada (setelah pengecekan), arahkan (redirect) ke `/login`.
   
2. RENDER STRUKTUR LAYOUT (Berdasarkan Mockup)
   - BUNGKUS DENGAN DIV CLASS "app" (flex, height 100vh)
   
   - TAMPILKAN Komponen `<Sidebar />` (Di sebelah kiri)
     - Sidebar memuat tombol "Chat Baru", navigasi "Riwayat Chat", "Dokumen Panduan", "Profil".
     - Jika tombol "Chat Baru" diklik: panggil `resetSession()` dari `lib/store.ts` dan arahkan ke halaman `/chat`.
   
   - DIV MAIN PANEL (Di tengah)
     - TAMPILKAN Mobile Topbar (Hanya tampil di layar kecil)
     - TAMPILKAN Konten dinamis `{children}` (bisa berupa /chat, /riwayat, /profil)
     - TAMPILKAN Komponen `<BottomNav />` (Hanya tampil di layar kecil)
     
   - TAMPILKAN Komponen `<DocPanel />` (Panel dokumen di sebelah kanan/overlay)
```

### `app/(site)/chat/page.tsx`
```markdown
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
```

### `app/(site)/riwayat/page.tsx`
```markdown
ALGORITMA HALAMAN RIWAYAT

1. INISIALISASI
   - Panggil GET `NEXT_PUBLIC_API_BASE_URL/api/sessions` untuk mendapatkan histori seluruh percakapan pengguna (mengembalikan daftar sesi beserta timestamp dan preview pesan pertama).

2. RENDER TAMPILAN
   - Kelompokkan hasil respon API berdasarkan tanggal ("Hari ini", "Kemarin", "Minggu lalu").
   - Tampilkan daftar percakapan sebelumnya.
   - Ketika item di-klik, panggil GET `NEXT_PUBLIC_API_BASE_URL/api/sessions/{id}` dan set hasilnya ke global state `messages` dan `session_id`, lalu pindah ke halaman `/chat`.
```

### `app/(site)/profil/page.tsx`
```markdown
ALGORITMA HALAMAN PROFIL

1. INISIALISASI
   - Lakukan GET request ke `NEXT_PUBLIC_API_BASE_URL/api/auth/me` dengan Bearer token.
   - Ambil data `avatar_url`, `nama`, dan `email` dari respons database (jangan andalkan payload JWT untuk avatar).
2. RENDER TAMPILAN
   - Tampilkan Avatar (dari URL yang didapat), Nama, dan Email.
   - Tampilkan tombol opsi "Riwayat Chat Saya", "Dokumen Panduan".
   - Tampilkan tombol "Logout".
   - Ketika tombol Logout di-klik, panggil `logout()` dari `lib/auth.ts`.
```

---

## 4. PSEUDOCODE - KOMPONEN UMUM

### `components/DocPanel.tsx`
```markdown
ALGORITMA PANEL DOKUMEN PANDUAN

1. STATE GLOBAL (Bisa pakai Context/Zustand)
   - `isOpen`: Apakah panel terbuka atau tertutup.
   - `activeDocUrl`: URL file dokumen PDF (dari Supabase Storage `panduan-dokumen`).
   - `activeTab`: "panel" (tampil setengah layar) atau "halaman" (tampil penuh).

2. RENDER
   - JIKA `isOpen` false: Terapkan gaya CSS tersembunyi (width 0 / transform).
   - JIKA `isOpen` true:
     - Tampilkan toolbar dokumen (Tab, tombol close).
     - Tampilkan penampil iframe PDF (menunjuk ke `activeDocUrl`).
     - *Catatan: Pengambilan file PDF dilakukan langsung (direct link) ke Supabase Storage, bukan ke backend API.*
```
