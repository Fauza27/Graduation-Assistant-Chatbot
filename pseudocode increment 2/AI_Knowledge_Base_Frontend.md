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
