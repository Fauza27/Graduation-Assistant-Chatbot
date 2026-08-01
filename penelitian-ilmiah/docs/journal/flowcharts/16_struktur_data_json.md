# Struktur Data JSON — Format Chunk Dokumen

Penjelasan format file JSON yang digunakan sebagai input ingestion pipeline.

---

## `child_chunk_pi.json` — Format Child Chunk

Berisi potongan kecil dari buku panduan PI, digunakan untuk pencarian.

```json
[
  {
    "id": "pi-001",
    "parent_id": "parent-001",
    "title": "Latar Belakang dan Tujuan Panduan PI",
    "content": "Panduan Penyusunan Penulisan Ilmiah (PI) ini disusun untuk memberikan...",
    "section": "BAB I",
    "pages": ["1", "2"],
    "source": "Panduan Penyusunan Penulisan Imliah (PI) Cetak"
  },
  {
    "id": "pi-002",
    "parent_id": "parent-001",
    "title": "Latar Belakang dan Tujuan Panduan PI",
    "content": "Tujuan disusunnya panduan ini antara lain untuk menyeragamkan...",
    "section": "BAB I",
    "pages": ["2", "3"],
    "source": "Panduan Penyusunan Penulisan Imliah (PI) Cetak"
  }
]
```

### Field Wajib Child Chunk

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `id` | string | ID unik child chunk, format: `pi-NNN` atau `kkp-NNN` |
| `parent_id` | string | ID parent yang memiliki chunk ini |
| `title` | string | Judul sub-bab |
| `content` | string | Teks potongan (biasanya 200-400 kata) |
| `section` | string | Bagian buku: "BAB I", "BAB II", ..., "Lampiran" |
| `pages` | array | Nomor halaman asal di buku (opsional tapi dianjurkan) |
| `source` | string | Nama file/dokumen sumber |

---

## `parent_chunk_pi.json` — Format Parent Chunk

Berisi teks lengkap (konteks penuh) yang dikirim ke LLM saat menjawab.

```json
[
  {
    "parent_id": "parent-001",
    "title": "Latar Belakang dan Tujuan Panduan PI",
    "content": "BAB I - PENDAHULUAN\n\n1.1 Latar Belakang\nPanduan ini disusun untuk memberikan pedoman yang jelas dan terstandar...\n\n1.2 Tujuan\nTujuan panduan ini adalah:\n1. Menyeragamkan format penulisan PI di seluruh program studi\n2. Memberikan acuan yang jelas bagi mahasiswa dan dosen pembimbing\n3. ...",
    "section": "BAB I",
    "child_ids": ["pi-001", "pi-002", "pi-003"]
  },
  {
    "parent_id": "parent-002",
    "title": "Syarat dan Ketentuan PI",
    "content": "BAB II - KETENTUAN UMUM\n\n2.1 Syarat Mengambil PI\n...",
    "section": "BAB II",
    "child_ids": ["pi-004", "pi-005", "pi-006", "pi-007"]
  }
]
```

### Field Wajib Parent Chunk

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `parent_id` | string | ID unik parent, format: `parent-NNN` atau `parent-kkp-NNN` |
| `title` | string | Judul bab/sub-bab lengkap |
| `content` | string | Teks lengkap (biasanya 500-1500 kata) |
| `section` | string | Bagian buku: "BAB I", "BAB II", ..., "Lampiran" |
| `child_ids` | array | List ID child yang termasuk dalam parent ini |

---

## Relasi Parent ↔ Child

```
parent-001
  ├── pi-001  "...paragraph 1..."
  ├── pi-002  "...paragraph 2..."
  └── pi-003  "...paragraph 3..."

parent-002
  ├── pi-004  "...paragraph 4..."
  ├── pi-005  "...paragraph 5..."
  ├── pi-006  "...paragraph 6..."
  └── pi-007  "...paragraph 7..."
```

**Mengapa dipisah?** Embedding bekerja paling baik pada teks pendek (child). Tapi LLM butuh konteks panjang untuk menjawab (parent). Strategi "parent-child chunking" mendapat yang terbaik dari keduanya.

---

## Setelah Masuk ke Database

Setelah ingestion, data di Supabase memiliki field tambahan:

### `child_documents` (di Supabase)
```json
{
  "id":         "pi-001",
  "parent_id":  "parent-001",
  "title":      "Latar Belakang...",
  "content":    "Panduan ini disusun...",
  "section":    "BAB I",
  "pages":      ["1", "2"],
  "source":     "Panduan PI Cetak",
  "metadata":   {
    "parent_id": "parent-001",
    "title":     "Latar Belakang...",
    "section":   "BAB I",
    "pages":     ["1", "2"],
    "source":    "Panduan PI Cetak"
  },
  "embedding":  [0.023, -0.041, 0.187, ...],  ← 2000 float (tidak terlihat di UI)
  "created_at": "2026-05-04T08:00:00+00:00"
}
```

### `parent_documents` (di Supabase)
```json
{
  "parent_id":  "parent-001",
  "title":      "Latar Belakang dan Tujuan Panduan PI",
  "content":    "BAB I - PENDAHULUAN\n\n1.1 Latar Belakang\n...",
  "section":    "BAB I",
  "child_ids":  ["pi-001", "pi-002", "pi-003"],
  "created_at": "2026-05-04T08:00:00+00:00"
}
```

---

## Statistik Dataset

| Dataset | Parent Chunks | Child Chunks |
|---------|-------------|-------------|
| PI (Penulisan Ilmiah) | 23 | ~60-70 |
| KKP (Kuliah Kerja Praktik) | 23 | ~60-70 |
| **Total** | **46** | **~120-140** |

---

## Naming Convention ID

```
PI Child:    pi-001, pi-002, ..., pi-NNN
PI Parent:   parent-001, parent-002, ..., parent-NNN

KKP Child:   kkp-001, kkp-002, ..., kkp-NNN
KKP Parent:  parent-kkp-001, parent-kkp-002, ..., parent-kkp-NNN
```

Convention ini dipakai `source_utils.py` untuk mendeteksi tipe panduan (PI vs KKP) dari ID.
