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
- **Catatan implementasi:** Navigasi ke halaman atau teks spesifik dalam PDF (via `#page=N` atau `#search=`) tidak dapat selalu diandalkan karena dukungan fitur ini tidak konsisten lintas-browser/viewer PDF ketika dimuat di dalam `iframe`. Implementasi ditekankan pada *fallback* yang aman, yakni pembukaan dokumen secara penuh berdasarkan domain.

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
