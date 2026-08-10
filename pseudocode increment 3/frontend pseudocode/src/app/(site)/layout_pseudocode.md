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
