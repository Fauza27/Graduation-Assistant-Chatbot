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
