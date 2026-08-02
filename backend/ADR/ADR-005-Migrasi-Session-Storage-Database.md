# ADR-005: Migrasi Session Storage dari In-Memory ke Database

## 1. Context (Mengapa keputusan ini perlu dibuat?)
Sistem chatbot menggunakan session management untuk menyimpan riwayat percakapan dan konteks user. Implementasi awal menggunakan **in-memory storage** dengan dictionary Python yang disimpan di RAM server. Setiap session berisi `ConversationMemory` dengan window 5 turn terakhir, plus timestamp untuk TTL cleanup dan LRU eviction.

Masalah mulai terasa ketika sistem harus di-deploy ke production. Setiap kali server restart (entah karena deployment baru, crash, atau maintenance), **semua session hilang**. User yang sedang chat tiba-tiba kehilangan konteks percakapan. Lebih parah lagi, jika kita mau scale horizontal (multiple server instances di belakang load balancer), setiap server punya session store terpisah yang tidak sinkron.

Contoh masalah real yang terjadi:
```
User: "Bagaimana format cover KKP?"
Bot: "Cover menggunakan Times New Roman 14pt..."

[Server restart karena deployment]

User: "Terus marginnya berapa?"
Bot: "Maaf, saya tidak ingat percakapan sebelumnya. Bisa ulangi pertanyaannya?"
```

Constraint utama di sini adalah **reliability** (session harus survive restart) dan **scalability** (harus bisa multi-server), tapi tetap mempertahankan **performance** yang baik untuk user experience.

## 2. Options (Apa saja yang dipertimbangkan?)
Berikut alternatif solusi untuk persistent session storage:

1. **Tetap In-Memory + Sticky Sessions**: 
   Mempertahankan dictionary di RAM, tapi menggunakan load balancer yang mengarahkan user ke server yang sama terus.
   *Pro*: Tidak perlu ubah kode, performa tetap maksimal (0ms).
   *Kontra*: Masih kehilangan session saat restart, tidak bisa scale elastis, single point of failure per user.

2. **Redis Cache External**: 
   Pindahkan session storage ke Redis cluster terpisah.
   *Pro*: Sangat cepat, built for caching, support TTL native.
   *Kontra*: Infrastruktur tambahan, biaya hosting Redis, network latency, satu lagi moving part yang bisa rusak.

3. **Database-Backed dengan Hot Cache**: 
   Simpan session di Supabase PostgreSQL (yang sudah ada), tapi tetap pakai LRU cache di memory untuk session yang aktif.
   *Pro*: Tidak perlu infrastruktur baru, ACID transactions, backup otomatis, bisa query untuk analytics.
   *Kontra*: Latency lebih tinggi untuk cache miss, kompleksitas serialization.

## 3. Decision (Apa yang dipilih dan kenapa?)
Kami memutuskan untuk memilih **Opsi 3: Database-Backed dengan Hot Cache**.

**Alasan Utama:**
Dalam konteks ini, **reliability dan cost-effectiveness** lebih penting daripada **pure performance**. 
- Opsi 3 memanfaatkan infrastruktur Supabase yang sudah ada, jadi tidak ada biaya tambahan atau kompleksitas deployment baru seperti Redis.
- Hot LRU cache (50 session terpanas) tetap memberikan performa 0ms untuk user yang aktif, sementara cache miss hanya terjadi untuk session yang jarang diakses.
- PostgreSQL JSONB memberikan fleksibilitas untuk menyimpan struktur `ConversationMemory` yang kompleks tanpa perlu normalisasi tabel.
- Bonus: bisa dapat analytics gratis (berapa user aktif, rata-rata panjang percakapan, dll) langsung dari SQL query.

## 4. Consequence (Apa yang harus diterima?)
Migrasi ke database-backed session storage membawa beberapa trade-off yang harus kita terima:

1. **Latency Overhead untuk Cold Sessions**: User yang baru mulai chat atau yang sessionnya sudah di-evict dari cache akan mengalami tambahan ~100ms untuk load session dari database. Ini masih acceptable untuk chatbot, tapi terasa jika dibandingkan dengan 0ms sebelumnya.

2. **Kompleksitas Serialization**: `ConversationMemory` dengan `Turn` objects harus di-serialize ke JSONB dan di-deserialize kembali. Kita harus maintain compatibility antara struktur data di memory dan di database, plus handle edge cases seperti data corruption.

3. **Database Dependency**: Sistem sekarang bergantung pada Supabase availability. Jika database down, fallback ke in-memory mode masih bisa jalan, tapi session tidak persistent. Ini menambah satu potential point of failure.

4. **Memory + Storage Double Usage**: Session sekarang disimpan di dua tempat (cache + database), jadi ada overhead storage. Plus kita harus manage cache eviction policy yang tepat agar tidak memory leak.