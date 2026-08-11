# Pseudocode Frontend — Increment 3

## Admin Dashboard: Kelola Chunk & Autentikasi

### STMIK Widya Cipta Dharma

|                     |                                                                                                                                                                                                                                                                                                                        |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Versi**           | 1.0                                                                                                                                                                                                                                                                                                                    |
| **Acuan**           | `04_Pseudocode_Backend_Increment3.md` v1.2 (kontrak API — backend sudah diimplementasikan), mockup HTML Admin Dashboard (rujukan visual & interaksi), `AI_Knowledge_Base_Frontend.md` (konvensi frontend eksisting: Next.js App Router, TypeScript, Zustand, Vanilla CSS)                                              |
| **Tanggal disusun** | 10 Agustus 2026                                                                                                                                                                                                                                                                                                        |
| **Cakupan**         | Frontend saja. Untuk detail visual/interaksi per elemen (warna, layout, animasi step re-embed, drill-down mobile), **mockup HTML adalah rujukan utama** — dokumen ini fokus pada bagaimana mockup itu disambungkan ke data & API asli lewat Next.js, bukan mengulang seluruh detail UI yang sudah disetujui di mockup. |

---

## 0. Ringkasan

Backend Increment 3 sudah selesai (lihat walkthrough terakhir) dan mengekspos 7 endpoint di `/api/admin/*`. Tugas frontend: mengganti data lokal mockup (`const DOCS = [...]`, `setTimeout` palsu untuk animasi re-embed) dengan panggilan API sungguhan, sambil mempertahankan seluruh perilaku UI yang sudah divalidasi di mockup (hierarki 4 level, kolom Struktur Dokumen + Child Chunk, panel detail kompak, halaman editor penuh, modal status re-embed, drill-down mobile).

---

## 1. Keputusan Desain

### 1.1 Koreksi routing: `app/admin/` (folder asli), BUKAN `app/(admin)/` (route group)

`03_Rencana_Pengembangan_Incremental.md` menyebut `frontend/app/(admin)` sebagai lokasi kerja Increment 3. Di Next.js App Router, tanda kurung `(admin)` menandakan **route group** — folder itu **tidak menambah segmen URL**. Kalau dipakai apa adanya, `app/(admin)/login/page.tsx` akan menghasilkan URL `/login`, **persis sama** dengan `app/login/page.tsx` milik mahasiswa (Google OAuth) yang sudah ada — collision routing.

**Perbaikan**: pakai folder asli **`app/admin/`** (tanpa kurung), sehingga semua rute admin otomatis berprefix `/admin/*` (`/admin/login`, `/admin/dashboard`, dst.) — sekaligus jadi pemisah yang jelas dari rute mahasiswa. Sebutan "(admin)" di Rencana Pengembangan kemungkinan cuma penyebutan longgar, bukan instruksi teknis literal.

### 1.2 Auth admin sepenuhnya terpisah dari auth mahasiswa

Modul baru (`lib/adminAuth.ts`, `lib/adminApi.ts`) dibuat **terpisah** dari `lib/auth.ts`/`lib/api.ts` milik mahasiswa — bukan memodifikasi keduanya. Alasan: skema token beda total (JWT admin punya klaim `role:"admin"`, bukan hasil verifikasi Google), dan supaya tidak ada risiko token admin ketiban dipakai memanggil endpoint mahasiswa atau sebaliknya. Key penyimpanan token juga dibedakan namanya: `admin_access_token` (bukan `access_token` yang sudah dipakai mahasiswa) — supaya kalau suatu saat admin & mahasiswa login di browser yang sama, dua sesi itu tidak saling menimpa.

### 1.3 "Ingat saya" di form login → pilihan `localStorage` vs `sessionStorage`

Checkbox "Ingat saya" di mockup belum fungsional. Perilaku sungguhan: dicentang → token disimpan di `localStorage` (bertahan meski browser ditutup); tidak dicentang → token disimpan di `sessionStorage` (hilang saat tab ditutup). `getAdminToken()` mengecek dua-duanya (tidak tahu sebelumnya mana yang dipakai).

### 1.4 "Buka Editor Penuh" = navigasi route asli, bukan view-toggle JS

Mockup memakai satu halaman dengan dua "view" yang di-toggle lewat JS (`setView('browse' | 'edit')`). Untuk Next.js, ini dipetakan jadi **dua route sungguhan**:

- `/admin/dashboard` — Browse view (tree + kolom child + panel detail kompak)
- `/admin/dashboard/chunks/[childId]` — Edit view (halaman editor penuh)

Alasannya: dapat dukungan tombol back browser & URL yang bisa dibagikan/refresh secara gratis dari Next.js router, dan konsisten dengan pola aplikasi mahasiswa yang sudah ada (halaman terpisah per rute: `/chat`, `/riwayat`, `/profil`) — bukan satu halaman dengan banyak state tersembunyi. Memilih child chunk di kolom 2 (panel detail kompak muncul di kanan, TANPA pindah halaman) tetap state lokal — hanya tombol "Buka Editor Penuh" (ikon maximize) yang benar-benar berpindah rute.

### 1.5 State tree disimpan di Zustand, TANPA `persist` middleware

Tidak seperti `lib/store.ts` milik mahasiswa (sengaja di-persist ke `localStorage` untuk riwayat chat), data tree admin **tidak** di-persist — setiap admin buka `/admin/dashboard`, tree diambil ulang dari server (data ini milik banyak orang/berubah-ubah, beda karakter dengan riwayat chat pribadi). Store dipakai murni untuk berbagi data tree + state seleksi antar-komponen dalam satu sesi browser.

### 1.6 Desain visual pakai token yang sudah ada + tambahan status palette

Variabel CSS di mockup (`--purple-primary`, dst.) sudah cocok dengan desain sistem `globals.css` milik mahasiswa. **Tidak perlu bikin stylesheet baru** — tambahkan saja variabel status baru (`--status-success-bg`, dst., lihat mockup bagian `:root`) ke `globals.css` yang sudah ada, supaya satu desain sistem dipakai bersama oleh halaman mahasiswa & admin.

### 1.7 Catatan pengujian terkait backend

Saat menguji tombol **Hapus**, pastikan isu `ON DELETE CASCADE` pada `chunk_edit_logs` yang saya angkat di review sebelumnya sudah dikonfirmasi ditangani di backend — kalau belum, tombol Hapus pada chunk yang pernah diedit akan mengembalikan error 500 dari server, bukan bug di frontend.

---

## 2. Struktur Folder & Routing (Next.js App Router)

```text
frontend/src/
├── app/
│   ├── admin/                             # BARU — folder asli (bukan route group), lihat §1.1
│   │   ├── login/
│   │   │   └── page.tsx                   # Form login admin (username/password)
│   │   └── dashboard/
│   │       ├── layout.tsx                 # Proteksi token admin + AdminSidebar + StatGrid
│   │       ├── page.tsx                   # Browse view: kolom Struktur Dokumen + Child Chunk + panel detail
│   │       └── chunks/
│   │           └── [childId]/
│   │               └── page.tsx           # Edit view: halaman editor penuh
│   ├── login/                             # TIDAK DIUBAH (mahasiswa, Google OAuth)
│   └── (site)/                            # TIDAK DIUBAH (mahasiswa)
├── components/
│   └── admin/                             # BARU
│       ├── AdminSidebar.tsx               # Sidebar admin (menu "Kelola Knowledge Base", profil, logout)
│       ├── StatGrid.tsx                   # 4 kartu statistik ringkasan
│       ├── KnowledgeTreeColumn.tsx        # Kolom 1: Struktur Dokumen (dipakai di Browse & Edit)
│       ├── ChildChunkColumn.tsx           # Kolom 2: daftar child chunk dari parent terpilih
│       ├── RelationDiagram.tsx            # Visualisasi SVG Parent → Child (collapsible)
│       ├── ChunkDetailPanel.tsx           # Panel kanan kompak (Browse) — metadata/content tab + aksi
│       ├── ChunkEditForm.tsx              # Form metadata+content, dipakai di panel kompak MAUPUN edit page
│       ├── ReembedStatusModal.tsx         # Modal sinkronisasi dengan status chip, progress bar, dan polling asli
│       ├── DeleteConfirmModal.tsx
│       └── MobileKnowledgeShell.tsx       # Drill-down mobile: Daftar Dokumen → Struktur → Detail, dengan ringkasan status per langkah
└── lib/
    ├── adminAuth.ts                       # BARU — login/logout/getAdminToken admin (terpisah, §1.2)
    ├── adminApi.ts                        # BARU — seluruh pemanggilan /api/admin/*
    └── adminStore.ts                      # BARU — Zustand store tree + state seleksi (§1.5)
```

---

## 3. Tipe Data (mengikuti persis kontrak API backend §6, `04_Pseudocode_Backend_Increment3.md`)

```typescript
// lib/adminTypes.ts
export type EmbeddingStatus = "pending" | "stale" | "success" | "failed";
export type EditLogStatus = "pending" | "processing" | "success" | "failed";

export interface ChildLite {
  id: string;
  title: string;
  pages: string;
  embedding_status: EmbeddingStatus;
}
export interface ParentNode {
  parent_id: string;
  title: string;
  child_count: number;
  children: ChildLite[];
}
export interface ChapterNode {
  section: string;
  parents: ParentNode[];
}
export interface DocumentNode {
  domain: string;
  source: string;
  chapters: ChapterNode[];
}
export interface SummaryStats {
  total_documents: number;
  total_parents: number;
  total_children: number;
  last_updated_at: string;
}
export interface KnowledgeTreeResponse {
  summary: SummaryStats;
  documents: DocumentNode[];
}
export interface ChunkDetail {
  id: string;
  title: string;
  pages: string;
  content: string;
  embedding_status: EmbeddingStatus;
  reembedded_at: string | null;
  parent: { parent_id: string; title: string };
  section: string;
  domain: string;
  source: string;
}
export interface ChunkEditStatus {
  log_id: string;
  child_id: string;
  status: EditLogStatus;
  error_message: string | null;
  edited_at: string;
  reembedded_at: string | null;
}
```

---

## 4. Pseudocode — `lib/`

### `lib/adminAuth.ts`

```markdown
ALGORITMA OTENTIKASI ADMIN (terpisah dari lib/auth.ts milik mahasiswa — lihat §1.2)

1. FUNGSI adminLogin(username, password, rememberMe)
   - PANGGIL POST NEXT_PUBLIC_API_BASE_URL/api/admin/login dengan body {username, password}.
   - JIKA sukses (200):
     - storage = rememberMe ? localStorage : sessionStorage (lihat §1.3)
     - storage.setItem('admin_access_token', response.access_token)
     - storage.setItem('admin_info', JSON.stringify(response.admin))
     - KEMBALIKAN {success: true}
   - JIKA gagal (401): KEMBALIKAN {success: false, message: "Username atau password salah."}
   - JIKA error jaringan lain: KEMBALIKAN {success: false, message: "Tidak bisa terhubung ke server."}

2. FUNGSI getAdminToken()
   - KEMBALIKAN localStorage.getItem('admin_access_token') ?? sessionStorage.getItem('admin_access_token') ?? null

3. FUNGSI getAdminInfo()
   - raw = localStorage.getItem('admin_info') ?? sessionStorage.getItem('admin_info')
   - KEMBALIKAN raw ? JSON.parse(raw) : null (dipakai AdminSidebar untuk tampilkan nama asli, GANTIKAN "Admin" hardcode di mockup)

4. FUNGSI adminLogout()
   - Hapus 'admin_access_token' dan 'admin_info' dari localStorage DAN sessionStorage (hapus dua-duanya, tidak tahu mana yang dipakai).
   - (Opsional) PANGGIL POST /api/admin/logout — best-effort, tidak perlu menunggu/blocking.
   - Arahkan ke /admin/login.
```

### `lib/adminApi.ts`

```markdown
ALGORITMA PEMANGGILAN API ADMIN

0. FUNGSI PEMBANTU adminFetch(path, options)
   - token = getAdminToken(). JIKA tidak ada: panggil adminLogout(), lempar error, STOP.
   - Set header Authorization: `Bearer ${token}`, Content-Type: application/json (jika ada body).
   - PANGGIL fetch(`${NEXT_PUBLIC_API_BASE_URL}/api/admin${path}`, options).
   - JIKA response.status === 401: panggil adminLogout(), STOP (sesi admin kedaluwarsa/tidak valid).
   - JIKA response.status === 403: lempar error "Akun ini bukan admin." (kasus defensif, seharusnya tidak terjadi dari UI admin).
   - JIKA response.status === 404: lempar error dengan pesan dari body response (biar pemanggil bisa tampilkan pesan spesifik, mis. "Chunk tidak ditemukan").
   - JIKA !response.ok lainnya: lempar error generik dengan status code (biar pemanggil bisa tampilkan toast).
   - KEMBALIKAN response.json().

1. FUNGSI getKnowledgeTree(): Promise<KnowledgeTreeResponse>
   - KEMBALIKAN adminFetch('/documents', {method:'GET'})

2. FUNGSI getChunkDetail(childId): Promise<ChunkDetail>
   - KEMBALIKAN adminFetch(`/chunks/${childId}`, {method:'GET'})

3. FUNGSI saveChunk(childId, {title?, pages?, content?}): Promise<ChunkSaveResponse>
   - KEMBALIKAN adminFetch(`/chunks/${childId}`, {method:'PUT', body: JSON.stringify({title, pages, content})})

4. FUNGSI triggerReembed(childId): Promise<ReembedTriggerResponse>
   - KEMBALIKAN adminFetch(`/chunks/${childId}/reembed`, {method:'POST'})

5. FUNGSI getEditStatus(childId): Promise<ChunkEditStatus>
   - KEMBALIKAN adminFetch(`/chunks/${childId}/edit-status`, {method:'GET'})

6. FUNGSI deleteChunk(childId): Promise<DeleteResponse>
   - KEMBALIKAN adminFetch(`/chunks/${childId}`, {method:'DELETE'})
```

### `lib/adminStore.ts` (Zustand, TANPA persist — lihat §1.5)

````markdown
ALGORITMA STATE GLOBAL ADMIN

1. STATE
   - tree: KnowledgeTreeResponse | null (null = belum dimuat)
   - isTreeLoading: boolean
   - selectedChildId: string | null (untuk panel detail kompak di Browse view)
   - selectedParentKey: string | null (domain+source+parent_id, untuk highlight kolom 1 & filter kolom 2)

2. AKSI fetchTree()
   - Set isTreeLoading = true.
   - PANGGIL adminApi.getKnowledgeTree(), simpan hasil ke `tree`.
   - Set isTreeLoading = false.

3. AKSI selectChild(childId, parentKey)
   - Set selectedChildId dan selectedParentKey.

4. AKSI patchChunkInTree(childId, updates)
   - Cari childId di dalam `tree` (loop documents→chapters→parents→children) dan gabungkan field-nya
     dengan `updates` (mis. {embedding_status: 'stale'}) — TANPA fetch ulang seluruh tree.
   - Dipakai setelah saveChunk() atau setelah polling edit-status berhasil, supaya badge status
     langsung berubah tanpa jeda (mirror pola mockup yang langsung mutasi state lokal).

# 6. Admin Panel Frontend Features

Frontend aplikasi juga dilengkapi dengan **Admin Panel** yang sekarang benar-benar ada di workspace. Struktur dan perilakunya mengikuti file `frontend/src/app/admin/*`, `frontend/src/components/admin/*`, dan `frontend/src/lib/admin*`.

## 6.1 Admin Authentication System

**Lokasi**: `src/lib/adminAuth.ts`

### Core Functions:

- `adminLogin(username, password, rememberMe)`: POST ke `/api/admin/login`.
  - Jika sukses, simpan `admin_access_token` dan `admin_info`.
  - Jika `rememberMe = true`, gunakan `localStorage`; selain itu `sessionStorage`.
  - Jika 401, tampilkan pesan login salah.
  - Jika error lain, tampilkan pesan tidak bisa terhubung ke server.

- `getAdminToken()`: ambil token dari `localStorage`, fallback ke `sessionStorage`.
- `getAdminInfo()`: parse JSON dari `admin_info`.
- `adminLogout()`: hapus token/info dari kedua storage dan kirim POST best-effort ke `/api/admin/logout`.

### Security Features:

- JWT token dengan `role: 'admin'` dari backend.
- SSR-safe karena semua akses storage dicek `typeof window`.
- Logout client-side bersifat stateless, backend hanya mengembalikan pesan sukses.

## 6.2 Admin State Management (Zustand)

**Lokasi**: `src/lib/adminStore.ts`

### State Structure:

```typescript
interface AdminState {
  tree: KnowledgeTreeResponse | null;
  isTreeLoading: boolean;
  selectedChildId: string | null;
  selectedParentKey: string | null;

  fetchTree: () => Promise<void>;
  selectChild: (childId: string | null, parentKey: string | null) => void;
  patchChunkInTree: (childId: string, updates: { embedding_status?: EmbeddingStatus }) => void;
  removeChunkFromTree: (childId: string, parentDeleted: boolean) => void;
}
```
````

### Key Actions:

- `fetchTree()`: load tree penuh dari `/api/admin/documents`.
- `selectChild(childId, parentKey)`: set child dan parent aktif untuk panel detail.
- `patchChunkInTree(childId, updates)`: update status embedding secara lokal.
- `removeChunkFromTree(childId, parentDeleted)`: hapus child dari tree dan cleanup parent jika backend juga menghapus parent.

### Performance Notes:

- Store tidak memakai `persist`.
- Tree diambil ulang saat dashboard dibuka.
- Update dilakukan immutably dengan deep clone sederhana.

## 6.3 Admin API Client

**Lokasi**: `src/lib/adminApi.ts`

### Core Functions:

- `adminFetch(path, options)`: wrapper fetch dengan Authorization Bearer token.
- `getKnowledgeTree()`: GET `/api/admin/documents`.
- `getChunkDetail(childId)`: GET `/api/admin/chunks/{childId}`.
- `saveChunk(childId, updates)`: PUT partial update ke chunk.
- `triggerReembed(childId)`: POST `/api/admin/chunks/{childId}/reembed`.
- `getEditStatus(childId)`: GET `/api/admin/chunks/{childId}/edit-status`.
- `deleteChunk(childId)`: DELETE `/api/admin/chunks/{childId}`.

### Error Handling:

- 401 memicu `adminLogout()`.
- 403 ditampilkan sebagai akun bukan admin.
- Error body dari server dibaca dari `detail` jika tersedia.

## 6.4 Admin TypeScript Types

**Lokasi**: `src/lib/adminTypes.ts`

### Hierarchical Tree Types:

```typescript
type EmbeddingStatus = "pending" | "stale" | "success" | "failed";
type EditLogStatus = "pending" | "processing" | "success" | "failed";

interface ChildLite {
  id: string;
  title: string;
  pages: string;
  embedding_status: EmbeddingStatus;
}

interface ParentNode {
  parent_id: string;
  title: string;
  child_count: number;
  children: ChildLite[];
}

interface ChapterNode {
  section: string;
  parents: ParentNode[];
}

interface DocumentNode {
  domain: string;
  source: string;
  chapters: ChapterNode[];
}
```

### Detail & Status Types:

```typescript
interface SummaryStats {
  total_documents: number;
  total_parents: number;
  total_children: number;
  last_updated_at: string;
}

interface ChunkDetail {
  id: string;
  title: string;
  pages: string;
  content: string;
  embedding_status: EmbeddingStatus;
  reembedded_at: string | null;
  parent: { parent_id: string; title: string };
  section: string;
  domain: string;
  source: string;
}

interface ChunkEditStatus {
  log_id: string;
  child_id: string;
  status: EditLogStatus;
  error_message: string | null;
  edited_at: string;
  reembedded_at: string | null;
}
```

## 6.5 Admin Routes & Pages

### A. Admin Layout (`app/admin/layout.tsx`)

**Features**:

- Memeriksa token admin pada mount.
- Jika token tidak ada, redirect ke `/admin/login`.
- Jika tree belum dimuat, panggil `fetchTree()`.
- Menampilkan `<AdminSidebar />` di desktop dan `<MobileKnowledgeShell />` di viewport kecil.
- Mengimpor `admin.css` untuk styling khusus dashboard admin.

### B. Admin Dashboard (`app/admin/dashboard/page.tsx`)

**Layout**: browse view tiga kolom.

1. Kolom 1: Struktur Dokumen.
2. Kolom 2: Child Chunk.
3. Panel kanan: Detail chunk terpilih.

**Komponen yang Dipakai**:

- `StatGrid`: menampilkan ringkasan summary.
- `KnowledgeTreeColumn`: tree domain/source/section/parent.
- `ChildChunkColumn`: daftar child chunk dari parent aktif.
- `RelationDiagram`: visual relasi parent-child.
- `ChunkDetailPanel`: detail cepat child terpilih.

**Perilaku**:

- Search dokumen dan child dilakukan client-side.
- Parent aktif ditentukan dari `selectedParentKey` di store.
- Tombol pada child list membuka editor penuh ke route `/admin/dashboard/chunks/[childId]`.

### C. Chunk Editor (`app/admin/dashboard/chunks/[childId]/page.tsx`)

**Layout**: editor penuh dengan tree kiri, form tengah, info panel kanan.

**Perilaku**:

- Ambil detail chunk dari backend saat route berubah.
- Jika chunk tidak ditemukan, tampilkan empty state dan tombol kembali.
- Breadcrumb menampilkan domain/source, section, parent, dan child id.
- Tombol maximize pada mobile info panel membuka editor penuh jika dari shell mobile.

## 6.6 Admin Components Architecture

### Core Components:

#### A. Navigation Components

- **`AdminSidebar`**: sidebar dengan menu knowledge base, logout, dan profil admin.
- **`KnowledgeTreeColumn`**: tree expandable berdasarkan query dan selected parent.
- **`ChildChunkColumn`**: daftar child dengan status badge dan tombol buka editor penuh.

#### B. Content Management Components

- **`ChunkEditForm`**: editor metadata/content dengan simpan, re-embed, dan delete; dipakai di panel kompak maupun editor penuh.
- **`ChunkDetailPanel`**: panel detail cepat di dashboard browse.
- **`StatGrid`**: ringkasan statistik tree.

#### C. Modal Components

- **`ReembedStatusModal`**: modal progress dengan polling edit status, status label, progress bar, dan tombol close yang nonaktif saat proses berjalan.
- **`DeleteConfirmModal`**: modal konfirmasi penghapusan child chunk.
- **`RelationDiagram`**: visual hubungan parent-child.

#### D. Layout Components

- **`MobileKnowledgeShell`**: shell mobile bertahap 1/2/3 dengan header yang menjelaskan langkah, ringkasan jumlah dokumen/parent/child, dan shortcut ke editor penuh.
- **`app/admin/layout.tsx`**: layout utama yang memutuskan desktop vs mobile shell.

## 6.7 Admin Authentication Flow

### Login Flow:

1. User membuka `/admin/login`.
2. Mengisi username dan password.
3. `adminLogin()` memanggil backend `/api/admin/login`.
4. Jika sukses, token dan info admin disimpan ke storage yang dipilih.
5. Redirect ke `/admin/dashboard`.

### Protection Flow:

1. `app/admin/layout.tsx` memeriksa `getAdminToken()`.
2. Jika token kosong, redirect ke `/admin/login`.
3. `adminFetch()` menyertakan Bearer token di setiap request.
4. Jika backend mengembalikan 401, client logout dan kembali ke login.

### Logout Flow:

1. User klik logout di sidebar atau fungsi logout dipanggil.
2. `adminLogout()` menghapus token dan info admin dari storage.
3. Client diarahkan ke `/admin/login`.

## 6.8 Admin UI/UX Features

### Design System:

- Dashboard memakai styling lokal di `admin.css` bersama token warna global.
- Brand panel login memakai visual STMIK dengan blob dekoratif.
- Status badge menggunakan warna success, warning, danger, dan info.

### Interactive Features:

- Search tree dan child dilakukan langsung di client.
- Panel detail di dashboard browse bisa dipilih tanpa pindah route.
- Editor penuh memakai route terpisah agar back button browser bekerja.
- Re-embed memakai modal progress dan polling backend.

### Responsive Behavior:

- Desktop/tablet: sidebar + main panel.
- Mobile: shell bertahap untuk daftar dokumen, struktur, lalu detail.
- Pada mobile, layout admin tidak bergantung pada tiga kolom penuh.

### Performance Notes:

- Store tree tidak dipersist.
- Data tree diambil ulang saat dashboard dibuka.
- Update status dilakukan optimistically di store sebelum atau sesudah response sukses.

## 6.9 Integration dengan Backend Admin API

### API Integration Pattern:

```typescript
const result = await saveChunk(childId, {
  title: titleDraft,
  pages: pagesDraft,
  content: contentDraft,
});

patchChunkInTree(childId, { embedding_status: result.embedding_status });
```

### Real-time Features:

- Save chunk bersifat manual, bukan auto-save.
- Re-embed dipantau dengan polling ke `/edit-status`.
- Delete chunk memperbarui tree lokal berdasarkan `parent_deleted`.

### Security Considerations:

- Semua request admin memakai bearer token.
- Client melakukan redirect jika token hilang atau tidak valid.
- Admin dan mahasiswa memakai storage token terpisah.

---

## 7. Admin vs Mahasiswa Feature Comparison

| Feature                | Mahasiswa Interface             | Admin Interface             |
| ---------------------- | ------------------------------- | --------------------------- |
| **Authentication**     | Google OAuth (GIS)              | Username/Password (bcrypt)  |
| **Primary Function**   | Chat dengan AI Assistant        | Content Management          |
| **State Management**   | Chat messages & session         | Knowledge tree & chunks     |
| **API Endpoints**      | `/api/chat`, `/api/auth/google` | `/api/admin/*` endpoints    |
| **Storage**            | Session-based chat history      | Persistent content editing  |
| **UI Theme**           | Purple chat bubbles             | Purple admin dashboard      |
| **Mobile Support**     | Chat-optimized                  | Admin panel mobile-friendly |
| **Real-time Features** | Typing indicators               | Polling status updates      |

### Shared Infrastructure:

- `globals.css` masih menjadi sumber token desain utama.
- Next.js App Router dipakai untuk route mahasiswa dan admin.
- TypeScript dipakai penuh pada kedua sisi.
- Error handling mengikuti pola response backend yang seragam.

---

Dokumentasi frontend sekarang selaras dengan implementasi admin panel nyata di workspace, termasuk route, store, API client, modal re-embed, dan struktur tree yang dipakai oleh dashboard.
