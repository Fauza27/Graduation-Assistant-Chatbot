# Pseudocode: Site Layout
## File: `app/(site)/layout.tsx`

```markdown
ALGORITMA LAYOUT UTAMA (APP SHELL)

1. COMPONENT SETUP
   - 'use client' directive
   - React hooks: useEffect, useState
   - Navigation: useRouter, usePathname
   - Authentication: getAuthToken, logout, jwtDecode
   - Global State: useAppStore (isDocPanelOpen, activeDoc, setDocPanelOpen, setActiveDoc, resetSession)

2. AUTHENTICATION & HYDRATION CHECK
   - Set `isClient` true untuk menghindari hydration mismatch.
   - Ambil token autentikasi.
   - JIKA token tidak ada: redirect ke `/login`.
   - JIKA token ada: decode JWT.
     - Jika token sudah expired (`exp * 1000 < Date.now()`), panggil `logout()`.

3. RENDER STRUKTUR LAYOUT (app)
   - BUNGKUS DENGAN DIV CLASS "app"
   
   - BAGIAN KIRI: SIDEBAR (`aside.sidebar`)
     - Header: Logo STMIK WCD dan tombol close (untuk mobile).
     - Tombol "Chat Baru": Memanggil `resetSession()`, arahkan ke `/chat`, tutup sidebar (mobile).
     - Navigasi (Link):
       - "Riwayat Chat": Menuju `/riwayat`.
       - "DOKUMEN PANDUAN": Toggle untuk membuka/tutup panel dokumen.
     - Footer:
       - "Profil": Menuju `/profil`.
       - "Logout": Panggil `logout()`.
     - Sidebar Overlay: Untuk menutup sidebar di mobile ketika diklik.
   
   - BAGIAN TENGAH: MAIN PANEL (`main.main-panel`)
     - Mobile Topbar: Tombol hamburger (membuka sidebar), Judul "Asisten WCD", tombol "Chat Baru".
     - Konten Dinamis: `{children}` (akan dirender sesuai route: /chat, /riwayat, /profil).
     - Mobile Bottom Nav: Navigasi bawah untuk mobile (Chat, Riwayat, Profil).
     
   - BAGIAN KANAN: DOCUMENT PANEL (`aside.doc-panel`)
     - Header Panel:
       - JIKA dokumen aktif: Tampilkan tombol kembali ke daftar dan tombol buka PDF di tab baru.
       - JIKA tidak ada: Tampilkan tombol tutup (mobile).
       - Judul "Dokumen Panduan" dan tombol silang untuk menutup.
     - Konten Panel:
       - JIKA dokumen aktif: Render `<iframe src={activeDoc} />` untuk menampilkan PDF.
       - JIKA tidak ada: Tampilkan daftar tombol dokumen (mapping dari `DOCUMENTS`).
         - Jika salah satu diklik, panggil `setActiveDoc(doc.fileUrl)`.
     - Doc Overlay: Untuk menutup panel di layar yang lebih kecil saat area luar diklik.
```
