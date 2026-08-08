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
     - Properti `key={activeDoc}` memastikan iframe di-remount ketika dokumen berganti — ini penting karena mekanisme ini memaksa Chrome PDFium menginisialisasi ulang viewer PDF dari nol, sehingga parameter `#page=N` langsung diterapkan tanpa perlu refresh manual.
     - Tombol panah kembali mengeset `activeDoc` ke `null` untuk kembali ke daftar.
     - Tombol **"Buka di Tab Baru"** (ikon tautan eksternal) memungkinkan pengguna membuka PDF di tab penuh untuk penggunaan Ctrl+F manual.
- CSS `doc-overlay` hanya aktif di layar ≤1023px (tablet/mobile) agar tidak memblokir scroll chat di desktop.

### Modul: `app/(site)/chat/page.tsx` (Klik Sitasi → Buka Dokumen)
- Setiap `CitationCard` yang diklik memanggil `handleCitationClick(src)`.
- Fungsi tersebut membaca `src.parent_id`, mendeteksi domain (pi/kkp/skripsi/non-skripsi), lalu membangun URL dokumen.
- **Strategi navigasi halaman (terverifikasi):**
  - **Prioritas 1:** Jika `src.pages` tersedia (array nomor halaman dari backend), gunakan `#page=N` (halaman pertama/terkecil). Fitur ini **terverifikasi berfungsi** pada Chrome PDFium.
  - **Prioritas 2 (Fallback):** Jika `pages` tidak tersedia, gunakan `#search=teks` sebagai *best-effort*. Fitur ini **terverifikasi TIDAK berfungsi** pada Chrome PDFium (meskipun teks ada di PDF via Ctrl+F), namun tetap disertakan untuk kompatibilitas browser lain.
- Memanggil `openDocument(url)` untuk membuka panel dengan PDF yang relevan.

### Perubahan Backend untuk Mendukung `#page=N`

#### `src/retrieval/parent_child.py` (Tambahan Pengambilan Halaman)
- Setelah mengambil dokumen induk, fungsi `fetch_parents()` sekarang juga:
  1. Mengumpulkan semua `child_id` yang cocok dari `matched_children`.
  2. Men-query tabel `child_documents` untuk mengambil kolom `pages` (nomor halaman asli di PDF) dari child yang cocok.
  3. Menyisipkan data `matched_pages` (array nomor halaman, diurutkan dan di-deduplikasi) ke setiap dokumen induk.

#### `src/services/ai_services.py` (Tambahan Field `pages` di Respons)
- `sources_list` sekarang menyertakan field `pages` dari `matched_pages`, sehingga frontend dapat menggunakan `#page=N`.

### Interface `CitationSource` (di `lib/store.ts`)
```typescript
export interface CitationSource {
  title?: string;
  section?: string;
  parent_id?: string;
  score?: number;
  pages?: number[];  // Nomor halaman dari child_documents yang cocok
}
```
- `ChatMessage.sources` diubah dari `string[]` menjadi `(CitationSource | string)[]` agar kompatibel dengan data riwayat dari database maupun data live dari API.

