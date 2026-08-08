# Dokumentasi Proyek Frontend: AI Chatbot Asisten Akademik

Dokumen ini adalah *knowledge base* khusus bagian **Frontend (Antarmuka Web)** dari sistem AI Chatbot Asisten Akademik. Panduan ini dirancang agar agen AI dapat dengan mudah memahami arsitektur UI, pengelolaan state, struktur folder, dan alur integrasi dengan backend.

---

## 1. Ringkasan Frontend
Frontend aplikasi dibangun dengan arsitektur modern berbasis komponen untuk menghadirkan antarmuka obrolan (*chatbot*) yang responsif, dilengkapi panel untuk melihat dokumen PDF rujukan (DocPanel), dan riwayat obrolan yang persisten.

**Tech Stack Frontend**:
- **Framework Utama**: Next.js (App Router) & React.
- **Bahasa**: TypeScript.
- **State Management**: Zustand (dengan *middleware* persistensi `localStorage`).
- **Styling**: Vanilla CSS murni (`globals.css`) dengan desain sistem variabel kustom (mengacu pada pedoman warna ungu/STMIK WICIDA).
- **Autentikasi**: Google Identity Services (Standar GIS / Oauth) yang diverifikasi oleh Backend JWT.
- **Parsing**: `react-markdown` (untuk format respons AI), `jwt-decode` (untuk membaca payload token).

---

## 2. Struktur Folder & Peran Komponen

```text
frontend/
├── package.json                : Dependensi proyek web.
├── tsconfig.json               : Konfigurasi TypeScript.
└── src/
    ├── app/
    │   ├── globals.css         : Induk desain antarmuka. Menyimpan token warna CSS, tipografi, dan layout (seperti `doc-panel`, `sidebar`, `msg-row`).
    │   ├── layout.tsx          : Root Layout Next.js (metadata & font bawaan Inter/Outfit).
    │   ├── login/
    │   │   └── page.tsx        : Halaman Single Sign-On menggunakan GIS.
    │   └── (site)/             : Rute yang dilindungi autentikasi (wajib login).
    │       ├── layout.tsx      : Layout tata letak Desktop/Mobile. Memuat komponen **Sidebar Kiri** (navigasi) dan **DocPanel Kanan** (Penampil Dokumen PDF via `iframe`).
    │       ├── chat/page.tsx   : Antarmuka utama obrolan (*text area*, *chat bubbles*, *typing dots*, dan penampil *Citation Card*).
    │       └── riwayat/page.tsx: Halaman untuk melihat histori obrolan sebelumnya, dikelompokkan berdasarkan tanggal ("Hari Ini", "Kemarin", "Lebih Lama").
    ├── lib/
    │   ├── api.ts              : Klien *fetcher* untuk menghubungi API Backend (`http://localhost:8000`), mengirim *Bearer token*.
    │   ├── auth.ts             : Utilitas penyimpan & pembaca token (JWT).
    │   ├── documentSources.ts  : Pemetaan URL konstan ke lokasi dokumen Supabase Storage (`panduan-pi.pdf`, dsb).
    │   └── store.ts            : Penyimpan state global menggunakan Zustand. Mencatat `session_id`, daftar `messages`, dan kontrol `isDocPanelOpen`.
    └── components/             
        └── [Komponen UI Ekstra]
```

---

## 3. Struktur State Management (Zustand Store)
`lib/store.ts` bertanggung jawab mengelola alur data yang perlu dibagikan antar-halaman (*cross-page*) atau antar-komponen.

### Properti Utama:
- `session_id` (string): ID Sesi unik (UUID/ID Telegram). Jika diganti, percakapan dianggap baru.
- `messages` (Array): Deretan pesan `user` dan `bot`. Pesan bot menyimpan `sources` (berupa array of `CitationSource`).
- `hasHydrated` (boolean): Flag untuk mencegah *hydration mismatch error* karena pembacaan `localStorage` saat SSR.
- **State DocPanel (Tidak persisten/sementara)**:
  - `isDocPanelOpen`: Boolean penentu terbuka-tidaknya sidebar kanan.
  - `activeDoc`: Teks URL Supabase Storage yang saat ini dipajang pada iframe penampil dokumen.

### Aksi (Actions):
- `addMessage`: Mendorong (*push*) pesan baru ke layar.
- `resetSession`: Membuat `session_id` baru dan mengosongkan layar obrolan.
- `openDocument(url)`: Mengubah URL `activeDoc` dan memunculkan panel dokumen serentak (Bisa dipanggil dari area manapun).

---

## 4. Alur Interaksi Kunci

### A. Alur Login & Autentikasi
1. Pengguna membuka `/login`.
2. Menekan tombol "Lanjutkan dengan Google" yang memicu library Google Identity Services (`google.accounts.id`).
3. Google mengirim kredensial OAuth (`credential`) ke frontend.
4. Fungsi `handleGoogleSuccess` meneruskan token ini ke Backend (`POST /api/auth/google/verify`).
5. Backend mengembalikan Custom JWT. Token ini disimpan via utilitas `lib/auth.ts`.
6. Frontend meneruskan navigasi (*redirect*) ke `/chat`. Layar-layar yang dilindungi rute `(site)/layout.tsx` akan memverifikasi token sebelum merender.

### B. Alur Kirim Pesan & Terima Balasan
1. Pengguna mengetik pertanyaan di `chat/page.tsx`. Input dibaca via `useState`.
2. Pengguna menekan *Send*. Fungsi lokal memanggil `addMessage('user', ...)` pada Zustand.
3. Menjalankan fungsi di `lib/api.ts` -> `sendChatMessage(...)` yang mengirim `POST /api/chat`.
4. Jika sukses, respons dan daftar `sources` disuntikkan kembali ke dalam `addMessage('bot', ...)` pada Zustand.
5. `chat/page.tsx` me-render iterasi state pesan melalui *Markdown* (menggunakan `react-markdown`).

### C. Alur Klik Sitasi (Fitur Lompat ke Dokumen)
1. Jika balasan bot (`msg`) menyertakan data `sources` (referensi yang diambil RAG), komponen akan merender `CitationCard` di bawah gelembung obrolan bot.
2. Ketika `CitationCard` diklik, ia membaca kode spesifik `parent_id` (contoh: `kkp-bab1`, `pi-bab3`).
3. Algoritma pendeteksi di `handleCitationClick` akan mencari file PDF yang tepat (`panduan-kkp.pdf` atau `panduan-pi.pdf`) di data statis `documentSources.ts`.
4. URL PDF tersebut diimbuhi `#search="[teks potongan referensi]"` lalu dikirim ke aksi `openDocument(url)`.
5. Komponen `layout.tsx` (yang menampung *DocPanel*) mendeteksi `activeDoc` terisi, lalu membuka *Sidebar Kanan* dan memuat konten via `<iframe key={activeDoc} src={activeDoc} />`.

---

## 5. Pertimbangan & Batasan (Caveats)
1. **Keamanan URL Hash di iframe**: Parameter *Search* PDF via URL (e.g. `#search="kata"`) adalah dukungan standar penampil peramban (contoh: Chrome PDFium). Meski demikian, tingkat presisi loncat ke teks akan berbeda-beda tergantung ekstensi peramban bawaan yang dipakai klien, dan sering terhalang oleh mekanisme keamanan domain lintas (*cross-origin sandboxing*).
2. **Keterbatasan CSS Overlay**: *Overlay* kegelapan (`doc-overlay`) hanya boleh menyala di mode *mobile/tablet* (`<=1023px`). Pada *desktop*, interaksi chat tetap harus aktif meski panel kanan sedang membaca dokumen. Ini diatur paksa di `@media (min-width:1024px)` pada `globals.css`.
3. **Penghentian Otomatis SSR Layout**: Fitur DOM bawaan seperti `window.localStorage` dalam file yang tidak dikhususkan `'use client'` akan menyebabkan *error* hidrasi Next.js. Semua komponen berstatus stateful harus memiliki *directive* `'use client'` di atas filenya.


---

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


---

# Pseudocode Increment 2 - FR-WEB-08 & FR-WEB-09

## FR-WEB-09 (Riwayat & Hapus Percakapan)
**Status:** ✅ Selesai diimplementasikan.
- **Backend:** `backend/src/api/sessions.py` memiliki endpoint:
  - `GET /api/sessions/` — mengambil daftar sesi milik mahasiswa yang login (dilindungi IDOR).
  - `GET /api/sessions/{session_id}` — mengambil detail pesan satu sesi.
  - `DELETE /api/sessions/{session_id}` — menghapus percakapan (dilindungi IDOR).
- **Frontend:**
  - `riwayat/page.tsx`: Mengelompokkan riwayat menjadi "Hari Ini", "Kemarin", "Lebih Lama".
  - `chat/page.tsx`: Tombol kebab menu (⋯) dengan opsi "Hapus Percakapan" memanggil API DELETE lalu reset sesi lokal.

---

## FR-WEB-08 (Dokumen Panduan Sidebar)
**Status:** ✅ Selesai diimplementasikan.

### Modul: `lib/documentSources.ts` [NEW]
- Menyimpan daftar referensi dokumen PDF statis dari Supabase Storage sebagai modul terpisah agar dapat digunakan ulang oleh komponen lain (termasuk sitasi).
- Base URL: `https://pobgqxhneruhswxedqpf.supabase.co/storage/v1/object/public/panduan-dokumen/`
- Nama file yang digunakan (sesuai yang ter-upload di Supabase Storage):
  - `panduan-pi.pdf`
  - `panduan-kkp.pdf`
  - `panduan-skripsi.pdf`
  - `panduan-non-skripsi.pdf`

### Modul: `lib/store.ts` (Tambahan State DocPanel)
- State `isDocPanelOpen` dan `activeDoc` dipindahkan ke Zustand global store.
- Action `openDocument(url)` membuka panel sekaligus mengarahkan ke dokumen tertentu dari komponen manapun (termasuk `CitationCard`).
- State DocPanel **tidak di-persist** ke localStorage (menggunakan `partialize`).

### Modul: `app/(site)/layout.tsx` (DocPanel)
- DocPanel menampilkan dua state:
  1. **Daftar dokumen** (saat `activeDoc == null`): Menampilkan tombol untuk PI, KKP, Skripsi, Non-Skripsi.
  2. **PDF Viewer** (saat `activeDoc != null`): Menampilkan `<iframe key={activeDoc} src={activeDoc}>` untuk memuat PDF.
     - Properti `key={activeDoc}` memastikan iframe di-remount ketika dokumen berganti.
     - Tombol panah kembali mengeset `activeDoc` ke `null` untuk kembali ke daftar.
- CSS `doc-overlay` hanya aktif di layar ≤1023px (tablet/mobile) agar tidak memblokir scroll chat di desktop.

### Modul: `app/(site)/chat/page.tsx` (Klik Sitasi → Buka Dokumen)
- Setiap `CitationCard` yang diklik memanggil `handleCitationClick(src)`.
- Fungsi tersebut membaca `src.parent_id`, mendeteksi domain (pi/kkp/skripsi/non-skripsi), lalu memanggil `openDocument(url)` untuk membuka panel dengan PDF yang relevan.
- **Catatan implementasi:** Navigasi ke halaman spesifik dalam PDF (via `#page=N` atau `#search=`) tidak dapat diandalkan karena keterbatasan *browser sandboxing* pada PDF lintas-domain (`iframe` dari Supabase Storage). Implementasi terbatas pada pembukaan dokumen yang tepat berdasarkan domain.

### Interface `CitationSource` (di `lib/store.ts`)
```typescript
export interface CitationSource {
  title?: string;
  section?: string;
  parent_id?: string;
  score?: number;
}
```
- `ChatMessage.sources` diubah dari `string[]` menjadi `(CitationSource | string)[]` agar kompatibel dengan data riwayat dari database maupun data live dari API.
