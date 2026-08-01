# Software Requirement Specification

## Functional Requirements

FR-01
Sistem dapat menjawab pertanyaan mahasiswa menggunakan RAG.

FR-02
Sistem mendukung empat domain:
- KKP
- PI
- Skripsi
- Non Skripsi

FR-03
pengguna dapat login dan logout

FR-04
pengguna dapat melakukan chat

FR-05
pengguna dapat melihat history percakapan

FR-06
pengguna dapat membuat chat baru

FR-07
pengguna dapat melihat list history percakapan

FR-08
Pengguna dapat memberikan Like dan dislike pada jawaban yang diberikan, beserta alasannya agar sistem dapat terus ditingkatkan. (tidak wajib, Optional Enhancement)

FR-09
Sistem menyimpan histori percakapan.

FR-10
Admin dapat melihat dashboard admin.

FR-11
Admin dapat melihat histori percakapan.

FR-12
Admin dapat melihat analytics chatbot.

FR-13
Admin dapat mengedit knowledge base

FR-14
Retrieval Evaluation Agent dapat:
- mendeteksi retrieval failure
- mendeteksi missing knowledge
- mendeteksi dokumen yang sering gagal ditemukan
- menghasilkan rekomendasi

FR-15
Admin dapat:
- approve
- reject
- edit recommendation
Karena agent tidak boleh langsung mengubah KB.

## Non Functional Requirement
| ID | Kategori | Requirement |
|----|----------|-------------|
| NFR-01 | Performance | Response time p95 chatbot < 10 detik total (termasuk retrieval + generation) |
| NFR-02 | Accuracy | Jawaban harus grounded pada knowledge base 
| NFR-03 | Security | Autentikasi mahasiswa (OAuth supabase untuk mahasiswa, autentikasi biasa untuk admin), role-based access untuk admin vs mahasiswa |
| NFR-04 | Privacy | Data chat & feedback disimpan sesuai etika penelitian; anonimkan saat dipakai untuk laporan/BAB IV |
| NFR-05 | Scalability | Sistem tetap responsif saat concurrent user meningkat (mis. masa pengajuan PI/skripsi) |
| NFR-06 | Availability | Uptime terjaga minimal selama periode pengujian & sidang |
| NFR-07 | Maintainability | Admin non-teknis bisa update knowledge base tanpa sentuh kode |
| NFR-08 | Usability | UI web dapat dipakai mahasiswa awam teknologi tanpa training |
