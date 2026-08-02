import json
import warnings
from pathlib import Path
from datetime import datetime
import math
from statistics import mean

warnings.filterwarnings("ignore", category=DeprecationWarning)

from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    answer_correctness,
    answer_similarity,
    context_precision,
    context_recall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from loguru import logger

from config.settings import get_settings


# Threshold targets
THRESHOLD_TARGETS = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.85,
    "answer_correctness": 0.85,
    "answer_similarity": 0.85,
    "context_precision": 0.85,
    "context_recall": 0.85,
}

METRIC_NAMES = list(THRESHOLD_TARGETS.keys())


# Evaluation Dataset
# Mendukung evaluasi untuk PI dan KKP
EVAL_QUESTIONS_PI = [
    # Syarat & Ketentuan
    {
        "question": "Apa syarat SKS minimal untuk mengambil Penulisan Ilmiah (PI)?",
        "ground_truth": "Minimal 100 SKS dengan IPK minimal 2,00.",
    },
    {
        "question": "Berapa IP Kumulatif minimal yang harus dimiliki mahasiswa untuk mengambil PI?",
        "ground_truth": (
            "Mahasiswa harus memiliki IP Kumulatif minimal 2,00 untuk dapat "
            "mengambil mata kuliah Penulisan Ilmiah (PI)."
        ),
    },
    {
        "question": "Apakah PI wajib dilakukan di sebuah instansi atau perusahaan?",
        "ground_truth": (
            "Tidak wajib. PI adalah riset mandiri pada organisasi/instansi atau "
            "studi literatur pada buku dan jurnal ilmiah. Penelitian juga dapat "
            "dilakukan tanpa tempat/instansi, berasal dari riset mandiri berbasis "
            "studi literatur."
        ),
    },
    {
        "question": "Berapa lama minimal kegiatan penelitian PI jika dilakukan di perusahaan atau instansi?",
        "ground_truth": (
            "Kegiatan penelitian PI di perusahaan atau instansi minimal selama "
            "7 hari kerja."
        ),
    },
    {
        "question": "Apa tujuan utama Penulisan Ilmiah (PI)?",
        "ground_truth": (
            "Tujuan PI adalah memberi pemahaman agar mahasiswa berpikir logis dan "
            "ilmiah dalam menguraikan dan membahas suatu permasalahan, dapat "
            "membandingkan antara teori yang didapatkan dengan praktik kehidupan "
            "nyata, serta dapat menuangkannya dalam bentuk tulisan secara sistematis "
            "dan terstruktur."
        ),
    },

    # ── Dosen Pembimbing & Penguji ───────────────────────────────
    {
        "question": "Siapa yang menjadi dosen pembimbing PI?",
        "ground_truth": (
            "Dosen Pembimbing PI adalah Dosen Pembimbing Akademik (Dosen Wali). "
            "Dosen Pembimbing harus terdaftar sebagai dosen STMIK Widya Cipta Dharma "
            "dan memiliki jabatan fungsional minimal asisten ahli atau lektor dengan "
            "kualifikasi pendidikan S2 atau S3."
        ),
    },
    {
        "question": "Berapa jumlah dosen penguji pada ujian PI?",
        "ground_truth": (
            "Setiap kegiatan PI diuji oleh 2 Dosen Penguji, yaitu satu Ketua Penguji "
            "dan satu Anggota Penguji yang ditunjuk oleh Ketua Program Studi."
        ),
    },
    {
        "question": "Apa syarat jabatan fungsional minimal untuk menjadi dosen pembimbing atau penguji PI?",
        "ground_truth": "Minimal asisten ahli atau lektor dengan kualifikasi S2 atau S3 dan kompetensi relevan dengan PI.",
    },
    {
        "question": "Dalam kondisi apa mahasiswa dapat mengajukan penggantian dosen pembimbing PI?",
        "ground_truth": (
            "Mahasiswa dapat mengajukan penggantian Dosen Pembimbing apabila terjadi: "
            "(1) meninggal dunia, (2) sakit dan harus istirahat panjang, "
            "(3) cuti di luar tanggungan, atau (4) pindah tugas."
        ),
    },
    {
        "question": "Siapa yang berwenang mengeluarkan surat tugas dosen pembimbing pengganti PI?",
        "ground_truth": (
            "Ketua Program Studi mengeluarkan surat tugas pengganti setelah "
            "mempertimbangkan masa studi mahasiswa dan kebijakan yang berlaku."
        ),
    },

    # ── Proses Bimbingan ─────────────────────────────────────────
    {
        "question": "Berapa lama maksimal masa bimbingan PI?",
        "ground_truth": "Maksimal 6 bulan (1 semester), dapat diperpanjang dengan persetujuan Ketua Program Studi.",
    },
    {
        "question": "Berapa kali minimal pertemuan bimbingan PI dengan dosen pembimbing?",
        "ground_truth": (
            "Pertemuan dengan Dosen Pembimbing dijadwalkan minimal 8 kali, "
            "terdiri dari minimal 2 kali saat pelaksanaan PI dan 6 kali saat "
            "penyusunan laporan akhir."
        ),
    },
    {
        "question": "Di mana bimbingan PI dapat dilaksanakan?",
        "ground_truth": (
            "Bimbingan dapat dilaksanakan di kampus STMIK Widya Cipta Dharma atau "
            "secara online/daring berdasarkan kesepakatan dosen pembimbing dan mahasiswa."
        ),
    },
    {
        "question": "Apa yang harus dibawa mahasiswa setiap kali melakukan bimbingan PI?",
        "ground_truth": "Lembar bimbingan yang memuat materi bimbingan, tanggal, dan tanda tangan Dosen Pembimbing.",
    },
    {
        "question": "Kapan mahasiswa harus pertama kali menemui dosen pembimbing setelah form usulan PI disetujui?",
        "ground_truth": (
            "Mahasiswa wajib menemui Dosen Pembimbing paling lambat satu minggu "
            "setelah form usulan PI disetujui."
        ),
    },

    # ── Hak Mahasiswa ────────────────────────────────────────────
    {
        "question": "Apa saja hak mahasiswa dalam proses bimbingan PI?",
        "ground_truth": (
            "Hak mahasiswa bimbingan meliputi: (1) mendapatkan bimbingan, arahan, "
            "masukan, dan bantuan proporsional dari Dosen Pembimbing, (2) mendapatkan "
            "tanda tangan persetujuan Dosen Pembimbing setelah persyaratan terpenuhi, "
            "(3) mendapat perlakuan yang baik dari semua pihak, dan (4) mendapatkan "
            "hasil penilaian yang proporsional atas usaha dan pekerjaannya."
        ),
    },

    # ── Prosedur Ujian ───────────────────────────────────────────
    {
        "question": "Apa saja berkas yang harus dilampirkan saat mendaftar ujian PI?",
        "ground_truth": (
            "Berkas pendaftaran ujian PI meliputi: Form Pengecekan Syarat Administrasi, "
            "Form Pendaftaran Ujian PI, Form Permohonan Ujian PI, Lembar Persetujuan "
            "Ujian PI, Form Bimbingan Laporan PI, Form Daftar Hadir Menyaksikan Ujian PI, "
            "Transkrip Nilai (SKS minimal 100, IPK minimal 2.00), Kuitansi BPP dan SKS "
            "tervalidasi BAUK, KRS tervalidasi BAAK, Surat keterangan penelitian, "
            "Daftar wawancara, Draf laporan PI, Lembar Persetujuan Waktu Ujian PI, "
            "dan Bukti anti-plagiarisme maksimal 30%."
        ),
    },
    {
        "question": "Paling lambat kapan seminar PI harus dilaksanakan setelah persetujuan dosen pembimbing?",
        "ground_truth": (
            "Seminar PI dilakukan paling lambat 15 hari setelah persetujuan "
            "Dosen Pembimbing."
        ),
    },
    {
        "question": "Berapa lama waktu ujian PI dan bagaimana pembagiannya?",
        "ground_truth": (
            "Ujian PI maksimal 60 menit, terdiri dari 10 menit presentasi dan "
            "50 menit tanya jawab."
        ),
    },
    {
        "question": "Berapa kali minimal mahasiswa harus menghadiri seminar PI orang lain sebelum bisa seminar sendiri?",
        "ground_truth": (
            "Untuk melaksanakan seminar PI, mahasiswa wajib menghadiri seminar "
            "laporan PI minimal 3 kali."
        ),
    },
    {
        "question": "Apa ketentuan pakaian saat ujian PI untuk mahasiswa pria?",
        "ground_truth": (
            "Mahasiswa pria wajib mengenakan kemeja putih berdasi, almamater, "
            "celana hitam kain, dan sepatu tertutup hitam."
        ),
    },
    {
        "question": "Apa ketentuan pakaian saat ujian PI untuk mahasiswi berjilbab?",
        "ground_truth": (
            "Mahasiswi berjilbab wajib mengenakan kemeja putih berdasi, almamater, "
            "rok hitam di bawah lutut, sepatu tertutup hitam, dan jilbab hitam."
        ),
    },

    # ── Penilaian & Kelulusan ────────────────────────────────────
    {
        "question": "Apa saja komponen penilaian ujian PI?",
        "ground_truth": (
            "Komponen penilaian meliputi: Orisinalitas Penulisan, Sistematika dan "
            "Tata Cara Penulisan Laporan, Penguasaan Materi Sesuai Capaian "
            "Pembelajaran Mata Kuliah, Kemampuan Argumentasi dan Presentasi, dan "
            "Penampilan/Etika. Setiap komponen diberi nilai dalam rentang 0-100 "
            "dan nilai akhir merupakan rata-rata dari seluruh komponen."
        ),
    },
    {
        "question": "Apa skala penilaian dan predikat kelulusan PI?",
        "ground_truth": (
            "Nilai akhir PI menggunakan skala 100 dengan predikat: A (80-100) "
            "Sangat Baik - Lulus, B (70-79) Baik - Lulus, C (60-69) Cukup - Lulus, "
            "D (40-59) Kurang - Tidak Lulus, E (0-39) Sangat Kurang - Tidak Lulus."
        ),
    },
    {
        "question": "Apa syarat kelulusan ujian PI?",
        "ground_truth": (
            "Mahasiswa dinyatakan lulus apabila: (1) PI merupakan karya otentik, "
            "(2) memperoleh nilai minimal C, (3) telah memperbaiki PI sesuai saran "
            "dan arahan dibuktikan dengan penandatanganan halaman pengesahan, "
            "(4) telah menyerahkan jilid laporan ke Perpustakaan STMIK Widya Cipta "
            "Dharma dan menyerahkan surat keterangan penyerahan ke Program Studi."
        ),
    },
    {
        "question": "Apa konsekuensi jika PI terbukti merupakan jiplakan atau duplikasi karya orang lain?",
        "ground_truth": (
            "Jika terbukti duplikasi, jiplakan, atau terjemahan karya orang lain, "
            "dianggap pelanggaran akademik dan mahasiswa harus mengajukan judul baru."
        ),
    },
    {
        "question": "Bagaimana cara nilai PI dapat tercantum dalam transkrip mahasiswa?",
        "ground_truth": (
            "Nilai PI tercantum dalam transkrip setelah mahasiswa menyerahkan surat "
            "keterangan pengumpulan berkas jilid PI dari perpustakaan ke program studi."
        ),
    },

    # ── Format & Tata Tulis ──────────────────────────────────────
    {
        "question": "Berapa minimal halaman laporan PI?",
        "ground_truth": "Minimal 40 halaman (tidak termasuk cover, daftar isi, daftar tabel, daftar gambar, daftar lampiran, daftar pustaka, dan lampiran).",
    },
    {
        "question": "Apa format margin yang digunakan dalam penulisan PI?",
        "ground_truth": (
            "Margin: atas 3 cm, bawah 3 cm, kiri 4 cm, kanan 3 cm. "
            "Naskah rata kiri dan kanan."
        ),
    },
    {
        "question": "Jenis huruf apa yang digunakan dalam penulisan laporan PI?",
        "ground_truth": (
            "Jenis huruf Times New Roman ukuran 12 untuk seluruh naskah. "
            "Dalam tabel boleh lebih kecil dari 12."
        ),
    },
    {
        "question": "Berapa spasi yang digunakan untuk penulisan naskah PI?",
        "ground_truth": "1,5 spasi untuk naskah utama; 1 spasi untuk daftar isi, daftar tabel, daftar gambar, daftar lampiran, judul tabel, judul gambar, dan daftar pustaka.",
    },
    {
        "question": "Bagaimana ketentuan penomoran halaman bagian awal laporan PI?",
        "ground_truth": (
            "Bagian awal laporan (halaman judul sampai daftar gambar) menggunakan "
            "angka Romawi kecil yang diletakkan di tengah bawah halaman."
        ),
    },
    {
        "question": "Bagaimana ketentuan penomoran halaman bagian utama dan akhir laporan PI?",
        "ground_truth": (
            "Bagian utama dan akhir (Bab I sampai akhir) menggunakan angka Arab "
            "di kanan atas. Jika ada judul atau bab di bagian atas halaman, "
            "nomor halaman ditulis di tengah bawah."
        ),
    },
    {
        "question": "Bagaimana aturan penulisan alinea baru dalam laporan PI?",
        "ground_truth": (
            "Baris pertama alinea baru menjorok 6 ketukan dari margin kiri "
            "atau sekitar 1,2 cm."
        ),
    },
    {
        "question": "Apa ketentuan penggunaan tanda desimal dalam laporan PI?",
        "ground_truth": (
            "Bilangan desimal ditandai dengan koma (,), bukan titik (.). "
            "Angka menggunakan pembulatan dua angka atau lebih di belakang koma "
            "sesuai keperluan."
        ),
    },
    {
        "question": "Bagaimana aturan penulisan judul tabel dalam laporan PI?",
        "ground_truth": (
            "Nomor tabel dan keterangannya ditempatkan simetris di atas tabel "
            "tanpa titik. Judul ditulis dengan huruf tidak tebal, kapital di awal "
            "kata, tanpa titik. Jika lebih dari satu baris, baris kedua dimulai "
            "tepat di bawah huruf pertama judul dengan spasi 1 dan font 11."
        ),
    },
    {
        "question": "Bagaimana aturan penulisan judul gambar dalam laporan PI?",
        "ground_truth": (
            "Nomor gambar dan judul diletakkan simetris di bawah gambar tanpa titik. "
            "Jika judul lebih dari satu baris, baris kedua dimulai tepat di bawah "
            "huruf pertama judul dengan spasi 1 dan font 11. Sumber pustaka gambar "
            "ditulis setelah judul gambar."
        ),
    },
    {
        "question": "Apa aturan bahasa yang digunakan dalam penulisan laporan PI?",
        "ground_truth": (
            "Bahasa yang digunakan mengikuti EYD Edisi Kelima. Kalimat tidak "
            "menampilkan orang pertama atau orang kedua (saya, aku, kita, peneliti, "
            "penulis), melainkan menggunakan kalimat pasif. Istilah asing yang "
            "digunakan harus dicetak miring dan konsisten."
        ),
    },
    {
        "question": "Apa spesifikasi kertas yang digunakan untuk laporan PI?",
        "ground_truth": (
            "Kertas laporan hardcover PI menggunakan HVS A4 (21 cm x 29,7 cm) "
            "berat 80 gram, warna putih polos. Penulisan pada satu sisi kertas "
            "dengan tinta hitam, kecuali lambang dan gambar yang harus berwarna."
        ),
    },

    # ── Daftar Pustaka ───────────────────────────────────────────
    {
        "question": "Berapa jumlah minimal referensi daftar pustaka PI?",
        "ground_truth": (
            "Jumlah referensi minimal 15. 80% berasal dari buku dan jurnal. "
            "Disarankan merujuk referensi kurang dari 5 tahun kecuali yang "
            "sangat penting."
        ),
    },
    {
        "question": "Apa format penulisan daftar pustaka yang digunakan dalam PI?",
        "ground_truth": "Format APA (American Psychological Association). Disarankan menggunakan Mendeley atau tools reference lainnya. Urutan berdasarkan abjad nama penulis pertama dengan hanging indent.",
    },
    {
        "question": "Bagaimana format penulisan referensi artikel jurnal dalam daftar pustaka PI?",
        "ground_truth": (
            "Format: Penulis, A. A., & Penulis, B. B. (Tahun). Judul artikel. "
            "Nama Jurnal, volume(edisi), halaman. https://doi.org/xx.xxxxx. "
            "Contoh: Bryman, A. (2006). Integrating quantitative and qualitative "
            "research: How is it done? Qualitative Research, 6(1), 97-113."
        ),
    },
    {
        "question": "Bagaimana format penulisan referensi buku dalam daftar pustaka PI?",
        "ground_truth": (
            "Format: Penulis, A. A. (Tahun). Judul buku: Subjudul jika ada. "
            "Penerbit: Kota Terbit. Contoh: Sugiyono. (2016). Metode penelitian "
            "kuantitatif, kualitatif, dan R&D. Alfabeta: Bandung."
        ),
    },
    {
        "question": "Bagaimana cara menulis referensi dari sumber PI yang tidak dipublikasikan?",
        "ground_truth": (
            "Format: Penulis, A. A. (Tahun). Judul PI (PI tidak dipublikasikan). "
            "Institusi. Contoh: Pratama, R. F. (2020). Pengaruh media pembelajaran "
            "berbasis teknologi terhadap hasil belajar siswa (PI tidak dipublikasikan). "
            "STMIK Widya Cipta Dharma."
        ),
    },
    {
        "question": "Bagaimana cara menulis referensi dari media online yang tidak memiliki penulis?",
        "ground_truth": (
            "Format: Nama Organisasi atau Judul Artikel. (Tahun, Tanggal). "
            "Judul artikel. Nama Situs Web. URL. Contoh: Kementerian Pendidikan "
            "dan Kebudayaan. (2021, 15 Mei). Peningkatan kompetensi guru di era "
            "digital. Kemendikbud. https://www.kemendikbud.go.id"
        ),
    },

    # ── Sistematika Laporan ──────────────────────────────────────
    {
        "question": "Apa saja sistematika penulisan laporan PI?",
        "ground_truth": (
            "Sistematika terdiri atas Bagian Awal (Cover, Pengesahan, Abstrak, "
            "Kata Pengantar, Daftar Isi/Tabel/Gambar/Lampiran), Bagian Utama "
            "(BAB I Pendahuluan, BAB II Tinjauan Pustaka, BAB III Metode Penelitian, "
            "BAB IV Hasil dan Pembahasan, BAB V Penutup), dan Bagian Akhir "
            "(Daftar Pustaka, Lampiran)."
        ),
    },
    {
        "question": "Apa saja isi BAB I Pendahuluan dalam laporan PI?",
        "ground_truth": (
            "BAB I Pendahuluan berisi: Latar Belakang Masalah, Rumusan Masalah, "
            "Batasan Masalah, Tujuan Penelitian, Manfaat Penelitian, dan "
            "Sistematika Penulisan."
        ),
    },
    {
        "question": "Apa yang dimuat dalam BAB II Tinjauan Pustaka pada laporan PI?",
        "ground_truth": (
            "BAB II Tinjauan Pustaka berisi: Kajian Empiris (kajian dari penelitian "
            "sebelumnya yang relevan) dan Landasan Teori (ilmu-ilmu dasar relevan "
            "yang disusun sistematis). Semua sumber harus dicantumkan dengan nama "
            "penulis dan tahun terbit, maksimal 5 tahun terakhir."
        ),
    },
    {
        "question": "Apa yang dimuat dalam BAB III Metode Penelitian pada laporan PI?",
        "ground_truth": (
            "BAB III Metode Penelitian memuat: Tempat dan Waktu Penelitian, "
            "Teknik Pengumpulan Data (studi pustaka dan studi lapangan seperti "
            "observasi, wawancara, dokumentasi), Metode Pengembangan Sistem, "
            "dan Jadwal Penelitian."
        ),
    },
    {
        "question": "Apa yang dimuat dalam BAB V Penutup pada laporan PI?",
        "ground_truth": (
            "BAB V Penutup berisi: Kesimpulan (menjawab rumusan masalah dan "
            "menyimpulkan apakah hasil layak diimplementasikan) dan Saran "
            "(hal yang belum ditempuh dan layak dilaksanakan, terkait objek "
            "penelitian maupun pembaca yang akan mengembangkan hasil penelitian)."
        ),
    },
    {
        "question": "Apa yang harus dimuat dalam Abstrak laporan PI?",
        "ground_truth": (
            "Abstrak memuat latar belakang masalah, metode yang digunakan, dan "
            "hasil penelitian. Terdiri dari 3 alinea, maksimal 300 kata, panjang "
            "tidak lebih dari satu halaman, ditulis dengan jarak 1 spasi, dibuat "
            "dalam dua bahasa (Indonesia dan Inggris), serta memiliki 3-5 kata "
            "kunci yang ditulis huruf kecil dan dipisahkan koma."
        ),
    },
    {
        "question": "Berapa batas maksimal tingkat plagiarisme yang diizinkan untuk PI?",
        "ground_truth": "Maksimal 30% berdasarkan hasil pemeriksaan dari perangkat lunak pendeteksi plagiarisme yang valid.",
    },

    # ── Capaian Pembelajaran ─────────────────────────────────────
    {
        "question": "Apa capaian pembelajaran PI untuk Program Studi Sistem Informasi?",
        "ground_truth": (
            "Capaian pembelajaran Program Studi Sistem Informasi untuk PI meliputi: "
            "mampu berkomunikasi dan melakukan presentasi untuk menyajikan gagasan "
            "secara lisan maupun tertulis, dan mampu bekerja sama dalam tim."
        ),
    },
    {
        "question": "Apa capaian pembelajaran PI untuk Program Studi Bisnis Digital?",
        "ground_truth": (
            "Capaian pembelajaran Program Studi Bisnis Digital untuk PI meliputi: "
            "mampu menerapkan pemikiran logis, kritis, sistematis, dan inovatif; "
            "mampu menunjukkan kinerja mandiri, bermutu, dan terukur dalam bentuk "
            "laporan; mampu mengambil keputusan secara tepat berdasarkan analisis "
            "informasi; dan mampu memelihara dan mengembangkan hubungan jaringan "
            "kerja dengan pembimbing, kolega, dan sejawat."
        ),
    },
]


EVAL_QUESTIONS_KKP = [
    # ── Syarat & Ketentuan ──────────────────────────────────────
    {
        "question": "Apa syarat SKS minimal untuk mengambil Kuliah Kerja Praktik (KKP)?",
        "ground_truth": (
            "Mahasiswa yang berhak mengikuti KKP adalah mahasiswa yang telah "
            "menyelesaikan mata kuliah dengan jumlah SKS minimal 100 SKS dengan "
            "IP Kumulatif minimal 2,00."
        ),
    },
    {
        "question": "Berapa lama minimal pelaksanaan KKP?",
        "ground_truth": (
            "Kuliah Kerja Praktik dilaksanakan minimal 30 hari kerja atau "
            "1 (satu) bulan."
        ),
    },
    {
        "question": "Berapa jumlah dosen pembimbing dan penguji yang mendampingi mahasiswa KKP?",
        "ground_truth": (
            "Setiap kegiatan KKP dibimbing oleh 1 Dosen Pembimbing dan diuji "
            "oleh 2 Dosen Penguji."
        ),
    },
    {
        "question": "Apa bidang yang menjadi sasaran pengalaman belajar dalam KKP?",
        "ground_truth": (
            "Sasaran utama KKP adalah agar mahasiswa mendapatkan pengalaman "
            "belajar di bidang Sistem Informasi Manajemen, Teknik Komputer, "
            "Teknik Pemrograman, Digital Marketing, dan Entrepreneurship."
        ),
    },

    # ── Dosen Pembimbing & Penguji ───────────────────────────────
    {
        "question": "Siapa yang menjadi dosen pembimbing KKP?",
        "ground_truth": "Dosen Pembimbing Akademik (Dosen Wali) dengan jabatan minimal asisten ahli atau lektor, kualifikasi S2 atau S3, dan kompetensi relevan.",
    },
    {
        "question": "Apa tugas dosen penguji pada ujian KKP?",
        "ground_truth": (
            "Dosen penguji bertugas menguji mahasiswa pada saat ujian KKP, "
            "bertanggung jawab dan menunjukkan dedikasi selama ujian, mematuhi "
            "peraturan kampus, serta berhak memberikan masukan apabila naskah "
            "tidak sesuai panduan penyusunan KKP."
        ),
    },
    {
        "question": "Dalam kondisi apa dosen pembimbing KKP dapat mengundurkan diri?",
        "ground_truth": (
            "Dosen Pembimbing dapat mengajukan pengunduran diri secara tertulis "
            "apabila terjadi: sakit dan harus istirahat panjang, cuti di luar "
            "tanggungan, pindah tugas, atau alasan lainnya."
        ),
    },
    {
        "question": "Siapa yang berwenang menunjuk ketua penguji dan anggota penguji KKP?",
        "ground_truth": (
            "Ketua Program Studi menunjuk satu dosen sebagai Ketua Penguji dan "
            "satu dosen sebagai Anggota Penguji setelah berkas pendaftaran ujian "
            "KKP dinyatakan lengkap."
        ),
    },

    # ── Proses Bimbingan ─────────────────────────────────────────
    {
        "question": "Berapa kali minimal pertemuan bimbingan KKP?",
        "ground_truth": (
            "Pertemuan dengan Dosen Pembimbing KKP dijadwalkan minimal 8 kali, "
            "terdiri dari minimal 2 kali selama tahap pelaksanaan kegiatan KKP "
            "dan 6 kali selama tahap penyusunan laporan akhir KKP."
        ),
    },
    {
        "question": "Berapa lama maksimal masa bimbingan KKP?",
        "ground_truth": "Maksimal 6 bulan (1 semester), dapat diperpanjang dengan persetujuan Ketua Program Studi.",
    },
    {
        "question": "Apa yang dilakukan mahasiswa selama pelaksanaan KKP di instansi?",
        "ground_truth": (
            "Selama KKP mahasiswa: melapor kepada pimpinan instansi, mendiskusikan "
            "rencana kerja dengan pembimbing lapangan, melaporkan kegiatan KKP "
            "kepada dosen pembimbing minimal 8 kali, dan menyiapkan dokumentasi "
            "foto yang memperlihatkan praktikan melakukan setiap jenis kerja."
        ),
    },

    # ── Tempat KKP ───────────────────────────────────────────────
    {
        "question": "Apa saja kriteria tempat KKP yang diizinkan?",
        "ground_truth": (
            "Tempat KKP harus merupakan instansi pemerintah, BUMN, BUMD, perusahaan "
            "swasta, lembaga penelitian, startup, atau organisasi lain berbadan hukum "
            "resmi; relevan dengan bidang keilmuan program studi; memiliki kegiatan "
            "operasional aktif; dan dapat menerima maksimal 5 mahasiswa per instansi "
            "atau sesuai kesepakatan dalam MoA."
        ),
    },
    {
        "question": "Bagaimana mahasiswa diutamakan mencari tempat KKP?",
        "ground_truth": (
            "Mahasiswa diutamakan mencari tempat KKP melalui Unit Bursa Kerja Khusus "
            "(BKK) STMIK Widya Cipta Dharma untuk memperoleh tempat yang telah "
            "menjalin MoU dengan kampus."
        ),
    },
    {
        "question": "Apa yang dimaksud dengan tempat KKP dalam panduan?",
        "ground_truth": (
            "Tempat KKP adalah instansi, perusahaan, lembaga, atau organisasi resmi "
            "yang menyediakan lingkungan kerja nyata relevan dengan bidang keilmuan "
            "mahasiswa, mendukung penerapan teori dan keterampilan akademik ke dalam "
            "praktik profesional, serta menyediakan pembimbing lapangan."
        ),
    },

    # ── Tahapan Pengajuan KKP ────────────────────────────────────
    {
        "question": "Apa langkah pertama yang harus dilakukan mahasiswa dalam tahap awal pengajuan KKP?",
        "ground_truth": (
            "Mahasiswa mendaftarkan mata kuliah KKP pada Rencana Studi sebagai "
            "langkah pertama dalam tahap awal pengajuan KKP."
        ),
    },
    {
        "question": "Apa yang harus dilakukan mahasiswa setelah mendapatkan surat balasan dari instansi KKP?",
        "ground_truth": (
            "Setelah mendapatkan surat balasan dari instansi atau tempat penelitian, "
            "mahasiswa mengunggah surat balasan tersebut ke laman web BAAK untuk "
            "mendapatkan lembar kehadiran KKP."
        ),
    },
    {
        "question": "Apa yang harus mahasiswa lakukan setelah selesai melaksanakan KKP?",
        "ground_truth": (
            "Setelah selesai KKP, mahasiswa: membuat laporan sesuai panduan, "
            "memprogramkan mata kuliah KKP pada KRS, menyeminarkan laporan hasil "
            "KKP, dan wajib menghadiri seminar laporan KKP minimal 3 kali sebelum "
            "dapat melaksanakan seminar sendiri."
        ),
    },

    # ── Prosedur Ujian ───────────────────────────────────────────
    {
        "question": "Apa saja berkas yang harus dilampirkan saat mendaftar ujian KKP?",
        "ground_truth": (
            "Berkas pendaftaran ujian KKP meliputi: Form Pengecekan Syarat Administrasi, "
            "Form Pendaftaran Ujian KKP, Form Permohonan Ujian KKP, Lembar Persetujuan "
            "Ujian KKP, Form Bimbingan Laporan KKP, Form Daftar Hadir Menyaksikan "
            "Ujian KKP, Transkrip Nilai (SKS minimal 100, IPK minimal 2.00), Kuitansi "
            "BPP dan SKS tervalidasi BAUK, KRS tervalidasi BAAK, Surat keterangan "
            "penelitian, Presensi kehadiran dan nilai dari tempat penelitian, Daftar "
            "rincian kegiatan KKP, Daftar wawancara, Draf laporan KKP, Lembar "
            "Persetujuan Waktu Ujian KKP, dan Bukti anti-plagiarisme maksimal 30%."
        ),
    },
    {
        "question": "Berapa lama waktu yang diberikan untuk ujian KKP?",
        "ground_truth": (
            "Ujian KKP maksimal 60 menit, terdiri dari 10 menit presentasi dan "
            "50 menit tanya jawab."
        ),
    },
    {
        "question": "Paling lambat kapan seminar KKP harus dilaksanakan?",
        "ground_truth": (
            "Seminar KKP dilakukan paling lambat 15 hari setelah persetujuan "
            "Dosen Pembimbing."
        ),
    },
    {
        "question": "Siapa yang memimpin ujian seminar KKP?",
        "ground_truth": (
            "Ujian seminar KKP dipimpin oleh Dosen Pembimbing sebagai ketua "
            "panitia ujian. Seminar bersifat terbuka dan dihadiri Dosen Pembimbing, "
            "Dosen Penguji, dan mahasiswa lain."
        ),
    },
    {
        "question": "Bagaimana mekanisme perbaikan naskah KKP setelah ujian?",
        "ground_truth": (
            "Mahasiswa memperbaiki naskah berdasarkan saran pembimbing dan penguji, "
            "kemudian mengajukan hasil perbaikan kepada keduanya. Dosen Penguji "
            "memeriksa perbaikan; jika memenuhi syarat, menandatangani halaman "
            "pengesahan KKP. Naskah yang selesai diperbaiki kemudian ditandatangani "
            "Dosen Pembimbing."
        ),
    },

    # ── Penilaian & Kelulusan ────────────────────────────────────
    {
        "question": "Bagaimana sistem penilaian KKP dan bobot antara dosen internal dan pembimbing lapangan?",
        "ground_truth": (
            "Nilai KKP diberikan oleh Dosen Internal STMIK Wicida (Pembimbing Utama, "
            "Ketua Penguji, dan Anggota Penguji) serta Pembimbing Lapangan dengan "
            "perbandingan 60:40. Skala nilai: A (80-100) Lulus, B (70-79) Lulus, "
            "C (60-69) Lulus, D (40-59) Tidak Lulus, E (0-39) Tidak Lulus."
        ),
    },
    {
        "question": "Apa saja komponen penilaian ujian KKP?",
        "ground_truth": (
            "Komponen penilaian KKP meliputi: Orisinalitas Penulisan, Sistematika "
            "dan Tata Cara Penulisan Laporan, Penguasaan Materi Sesuai Capaian "
            "Pembelajaran Mata Kuliah, Kemampuan Argumentasi dan Presentasi, serta "
            "Penampilan atau Etika. Setiap komponen diberi nilai 0-100 dan nilai "
            "akhir merupakan rata-rata dari seluruh komponen."
        ),
    },
    {
        "question": "Apa syarat kelulusan ujian KKP?",
        "ground_truth": (
            "Mahasiswa dinyatakan lulus KKP apabila: (1) KKP merupakan karya otentik, "
            "(2) memperoleh nilai minimal C, (3) telah memperbaiki KKP sesuai saran "
            "dibuktikan dengan penandatanganan halaman pengesahan, (4) telah "
            "menyerahkan jilid laporan KKP ke Perpustakaan STMIK Widya Cipta Dharma "
            "dan menyerahkan surat keterangan penyerahan ke Program Studi."
        ),
    },
    {
        "question": "Apa komponen penilaian yang diberikan oleh pembimbing lapangan KKP?",
        "ground_truth": (
            "Penilaian pembimbing lapangan KKP mencakup: Etika, Keahlian pada Bidang "
            "Ilmu, Penggunaan Teknologi Informasi, Kemampuan Berkomunikasi, Kerjasama "
            "Tim, Pengembangan Diri, dan Disiplin. Setiap aspek dinilai dalam "
            "rentang skor 0-100."
        ),
    },

    # ── Format & Tata Tulis ──────────────────────────────────────
    {
        "question": "Berapa minimal halaman laporan KKP?",
        "ground_truth": (
            "Laporan KKP minimal 40 halaman di luar cover, daftar isi, daftar tabel, "
            "daftar gambar, daftar lampiran, daftar pustaka, dan lampiran."
        ),
    },
    {
        "question": "Apa spesifikasi kertas yang digunakan untuk laporan KKP?",
        "ground_truth": (
            "Kertas laporan hardcover KKP menggunakan HVS A4 (21 cm x 29,7 cm) "
            "berat 80 gram, warna putih polos. Penulisan pada satu sisi kertas "
            "dengan tinta hitam, kecuali lambang dan gambar yang harus berwarna."
        ),
    },
    {
        "question": "Berapa jumlah minimal referensi daftar pustaka KKP?",
        "ground_truth": (
            "Jumlah referensi minimal 5 dan 80% berasal dari buku dan jurnal. "
            "Disarankan merujuk referensi kurang dari 5 tahun kecuali yang "
            "sangat penting."
        ),
    },
    {
        "question": "Apa format margin yang digunakan dalam penulisan laporan KKP?",
        "ground_truth": (
            "Margin: atas 3 cm, bawah 3 cm, kiri 4 cm, kanan 3 cm. "
            "Naskah rata kiri dan kanan."
        ),
    },

    # ── Sistematika Laporan ──────────────────────────────────────
    {
        "question": "Apa saja sistematika penulisan laporan KKP?",
        "ground_truth": (
            "Sistematika terdiri atas Bagian Awal (Cover, Pengesahan, Kata Pengantar, "
            "Daftar Isi/Tabel/Gambar/Lampiran), Bagian Utama (BAB I Pendahuluan, "
            "BAB II Sejarah dan Profil Tempat KKP, BAB III Narasi Kegiatan, "
            "BAB IV Analisis Hasil Kegiatan, BAB V Penutup), dan Bagian Akhir "
            "(Daftar Pustaka, Lampiran)."
        ),
    },
    {
        "question": "Apa isi BAB I Pendahuluan dalam laporan KKP?",
        "ground_truth": (
            "BAB I Pendahuluan berisi: Deskripsi Tempat KKP (nama instansi, bidang "
            "usaha, visi dan misi, struktur organisasi, tupoksi tiap departemen), "
            "Waktu Pelaksanaan KKP, dan Lokasi KKP (alamat lengkap dan akses lokasi)."
        ),
    },
    {
        "question": "Apa isi BAB III Narasi Kegiatan dalam laporan KKP?",
        "ground_truth": (
            "BAB III Narasi Kegiatan berisi: Rincian Tugas Selama KKP (tahap-tahap "
            "kegiatan di tempat praktik) dan Deskripsi Kegiatan (uraian setiap "
            "kegiatan dilengkapi dokumentasi foto serta gambar pendukung seperti "
            "FOD, flowchart, algoritma, use case, atau math model)."
        ),
    },
    {
        "question": "Apa yang harus dimuat dalam BAB IV Analisis Hasil Kegiatan KKP?",
        "ground_truth": (
            "BAB IV Analisis Hasil Kegiatan KKP berisi: relevansi kegiatan dengan "
            "bidang ilmu, penerapan teknologi atau metode tertentu, pengembangan "
            "keterampilan teknis dan non-teknis, dampak dan kontribusi kegiatan, "
            "serta evaluasi hasil kegiatan."
        ),
    },
    {
        "question": "Apa yang harus dimuat dalam BAB V Penutup laporan KKP?",
        "ground_truth": (
            "BAB V Penutup berisi: Kesimpulan (ringkasan hasil utama kegiatan KKP, "
            "output yang diselesaikan, dan manfaatnya) dan Saran (untuk "
            "pengembangan aplikasi atau sistem, perusahaan, kampus atau program "
            "studi, dan mahasiswa lain yang akan melaksanakan KKP)."
        ),
    },
    {
        "question": "Apa saja yang harus dimuat dalam lampiran laporan KKP?",
        "ground_truth": (
            "Bagian lampiran berisi informasi tambahan seperti surat pengantar KKP, "
            "surat balasan tempat penelitian, form penilaian, serta lampiran lain "
            "yang diperlukan. Lampiran diberi nomor halaman angka di pojok kanan bawah."
        ),
    },

    # ── Capaian Pembelajaran ─────────────────────────────────────
    {
        "question": "Apa capaian pembelajaran KKP untuk Program Studi Teknik Informatika?",
        "ground_truth": (
            "Capaian pembelajaran Program Studi Teknik Informatika untuk KKP meliputi: "
            "mampu menunjukkan sikap profesional melalui kepatuhan terhadap etika "
            "profesi dan isu sosial; mampu bekerja sama dalam tim multidisiplin dan "
            "memahami pembelajaran sepanjang hayat; mampu berkomunikasi dan melakukan "
            "presentasi secara lisan maupun tulisan; serta mampu bekerja sama dalam tim."
        ),
    },
    {
        "question": "Apa capaian pembelajaran KKP untuk Program Studi Sistem Informasi?",
        "ground_truth": (
            "Capaian pembelajaran Program Studi Sistem Informasi untuk KKP meliputi: "
            "mampu berkomunikasi dan melakukan presentasi untuk menyajikan gagasan "
            "secara lisan maupun tertulis, mampu bekerja sama dalam tim, dan mampu "
            "mengelola kelompok maupun diri sendiri dalam menyelesaikan proyek "
            "sistem informasi."
        ),
    },

    # ── Halaman Sampul & Pengesahan ──────────────────────────────
    {
        "question": "Apa saja elemen yang harus ada pada halaman sampul depan laporan KKP?",
        "ground_truth": (
            "Halaman sampul depan KKP memuat: judul (huruf kapital, tidak disingkat), "
            "jenis usulan (KULIAH KERJA PRAKTIK), nama dan NIM mahasiswa di tengah "
            "halaman, lambang STMIK Widya Cipta Dharma, nama Program Studi, nama "
            "institusi, dan tahun diterbitkan."
        ),
    },
    {
        "question": "Apa yang dimuat dalam halaman pengesahan laporan KKP?",
        "ground_truth": (
            "Halaman Pengesahan KKP memuat: judul, nama lengkap, NIM, program studi, "
            "penempatan, tanggal seminar, tanda tangan Pembimbing Lapangan (NIK), "
            "Pembimbing Laporan (NIDN/NUPTK), Ketua Penguji, Anggota Penguji, "
            "Mengetahui Ketua Program Studi, dan Mengesahkan Ketua STMIK."
        ),
    },
]


def get_eval_questions(dataset: str) -> list[dict]:
    """
    Return evaluation questions sesuai dataset (PI/KKP).
    """
    if dataset.lower() == "kkp":
        return EVAL_QUESTIONS_KKP
    return EVAL_QUESTIONS_PI


def create_evaluation_dataset(dataset: str = "pi") -> list[dict]:
    """
    Return evaluation dataset sebagai list of dicts untuk PI atau KKP.
    Args:
        dataset: "pi" atau "kkp"
    Returns:
        List of dicts dengan keys: question, ground_truth
    """
    return get_eval_questions(dataset)


def _diagnose_metric(metric_name: str, score: float) -> dict:
    """Diagnosa penyebab dan rekomendasi untuk metrik yang gagal threshold."""
    diagnosis = {"metric": metric_name, "score": score, "threshold": THRESHOLD_TARGETS[metric_name]}

    diagnoses = {
        "faithfulness": {
            "cause": "LLM menghasilkan informasi yang TIDAK didukung oleh konteks (halusinasi)",
            "component": "Generation (Prompt / LLM)",
            "recommendations": [
                "Perkuat instruksi di SYSTEM_PROMPT agar LLM hanya menjawab dari konteks",
                "Tambahkan 'Jangan menambahkan informasi di luar dokumen' di prompt",
                "Kurangi temperature LLM (gunakan 0)",
                "Pertimbangkan max_tokens yang lebih kecil agar jawaban lebih fokus",
            ],
        },
        "answer_relevancy": {
            "cause": "Jawaban LLM menyimpang dari pertanyaan yang diajukan",
            "component": "Generation (Prompt)",
            "recommendations": [
                "Pastikan pertanyaan dimasukkan dengan jelas dalam prompt",
                "Tambahkan instruksi 'Jawab LANGSUNG pertanyaan yang diajukan'",
                "Hindari informasi tambahan yang tidak diminta",
            ],
        },
        "answer_correctness": {
            "cause": "Jawaban tidak sesuai dengan ground truth (fakta kurang tepat)",
            "component": "Retrieval + Generation",
            "recommendations": [
                "Periksa apakah konteks yang di-retrieve sudah mengandung jawaban",
                "Perbaiki ground truth jika kurang akurat",
                "Tingkatkan retrieval_top_k atau rerank_top_n",
            ],
        },
        "answer_similarity": {
            "cause": "Jawaban secara semantik berbeda jauh dari ground truth",
            "component": "Generation",
            "recommendations": [
                "Instruksikan LLM untuk menjawab dengan ringkas dan langsung",
                "Kurangi elaborasi yang tidak diperlukan",
                "Pastikan format jawaban konsisten",
            ],
        },
        "context_precision": {
            "cause": "Banyak konteks yang tidak relevan masuk ke top results",
            "component": "Retrieval (Hybrid Search + Reranker)",
            "recommendations": [
                "Kurangi retrieval_top_k agar lebih selektif",
                "Tingkatkan dense_weight vs bm25_weight",
                "Pertimbangkan cross-encoder model yang lebih kuat",
            ],
        },
        "context_recall": {
            "cause": "Retrieval GAGAL menemukan informasi yang dibutuhkan",
            "component": "Retrieval (Embedding + Search)",
            "recommendations": [
                "Tingkatkan retrieval_top_k",
                "Periksa chunking strategy — apakah informasi terpecah",
                "Verifikasi data sudah ter-ingest dengan benar",
                "Cek self_query filter — mungkin terlalu ketat",
            ],
        },
    }

    info = diagnoses.get(metric_name, {})
    diagnosis["cause"] = info.get("cause", "Unknown")
    diagnosis["component"] = info.get("component", "Unknown")
    diagnosis["recommendations"] = info.get("recommendations", [])
    return diagnosis


def run_evaluation(
    pipeline_fn,
    eval_data: list[dict] | None = None,
    output_path: str | None = None,
) -> dict:
    settings = get_settings()
    eval_data = eval_data or EVAL_QUESTIONS_PI

    logger.info(f"Memulai evaluasi RAGAS dengan {len(eval_data)} pertanyaan...")

    # 1. Jalankan pipeline untuk setiap pertanyaan → buat SingleTurnSample
    samples: list[SingleTurnSample] = []
    questions = []
    answers = []
    contexts_list = []
    ground_truths = []

    for i, item in enumerate(eval_data):
        q = item["question"]
        logger.info(f"[{i+1}/{len(eval_data)}] Pipeline: {q[:60]}...")

        try:
            result = pipeline_fn(q)
            ans = result["answer"]
            ctxs = result["contexts"]
        except Exception as e:
            logger.error(f"Error pipeline '{q}': {e}")
            ans = f"Error: {e}"
            ctxs = [""]

        questions.append(q)
        answers.append(ans)
        contexts_list.append(ctxs)
        ground_truths.append(item["ground_truth"])

        samples.append(SingleTurnSample(
            user_input=q,
            response=ans,
            retrieved_contexts=ctxs,
            reference=item["ground_truth"],
        ))

    # 2. Buat EvaluationDataset (RAGAS v0.4.x)
    eval_dataset = EvaluationDataset(samples=samples)

    # 3. Setup evaluator LLM dan embeddings
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.open_api_key,
            temperature=0.0,
        )
    )
    evaluator_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.open_api_key,
        )
    )

    # 4. Jalankan evaluasi RAGAS
    logger.info("Menjalankan RAGAS evaluation...")
    result = evaluate(
        dataset=eval_dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            answer_correctness,
            answer_similarity,
            context_precision,
            context_recall,
        ],
        llm=evaluator_llm,
        embeddings=evaluator_embeddings,
    )

    # 5. Extract aggregate scores
    def _safe_score(value) -> float:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            values = [v for v in value if v is not None and not (isinstance(v, float) and math.isnan(v))]
            return mean(values) if values else 0.0
        val = float(value)
        return 0.0 if math.isnan(val) else val

    scores = {m: _safe_score(result[m]) for m in METRIC_NAMES}
    scores["overall"] = sum(scores.values()) / len(scores)

    # 6. Print aggregate results
    logger.info("=" * 60)
    logger.info("HASIL EVALUASI RAGAS")
    logger.info("=" * 60)
    all_pass = True
    for metric in METRIC_NAMES:
        score = scores[metric]
        threshold = THRESHOLD_TARGETS[metric]
        status = "PASS" if score >= threshold else "FAIL"
        if score < threshold:
            all_pass = False
        bar = "#" * int(score * 20) + "." * (20 - int(score * 20))
        logger.info(f"  {metric:>20s}: {score:.4f} |{bar}| {status} (threshold={threshold})")
    logger.info(f"  {'overall':>20s}: {scores['overall']:.4f}")
    logger.info("=" * 60)

    if all_pass:
        logger.success("SEMUA METRIK PASS (>= 0.85)!")
    else:
        logger.warning("Ada metrik yang FAIL (< 0.85) - lihat diagnostik di bawah")

    # 7. Per-question metrics
    result_df = result.to_pandas()
    per_question_metrics: list[dict] = []
    for i in range(len(questions)):
        row = result_df.iloc[i]
        metrics_row = {}
        for col in METRIC_NAMES:
            value = row.get(col)
            if isinstance(value, float) and math.isnan(value):
                value = None
            metrics_row[col] = value
        per_question_metrics.append(metrics_row)

    # 8. Diagnostik per metrik yang gagal
    diagnostics: list[dict] = []
    for metric, threshold in THRESHOLD_TARGETS.items():
        if scores[metric] >= threshold:
            continue

        diagnosis = _diagnose_metric(metric, scores[metric])

        # Cari pertanyaan yang paling bermasalah
        failing_questions = []
        for idx in range(len(questions)):
            q_score = per_question_metrics[idx].get(metric)
            if q_score is not None and q_score < threshold:
                failing_questions.append({
                    "index": idx + 1,
                    "question": questions[idx],
                    "score": round(q_score, 4),
                    "answer_preview": answers[idx][:150],
                })

        failing_questions.sort(key=lambda x: x["score"])
        diagnosis["failing_questions"] = failing_questions
        diagnosis["num_failing"] = len(failing_questions)
        diagnosis["num_total"] = len(questions)
        diagnostics.append(diagnosis)

        logger.warning(
            f"DIAGNOSTIK {metric}: {len(failing_questions)}/{len(questions)} "
            f"pertanyaan gagal (avg={scores[metric]:.4f})"
        )
        logger.warning(f"  Penyebab: {diagnosis['cause']}")
        logger.warning(f"  Komponen: {diagnosis['component']}")
        for rec in diagnosis["recommendations"][:2]:
            logger.warning(f"  -> {rec}")
        for item in failing_questions[:3]:
            logger.warning(
                f"  [{item['index']}] score={item['score']:.4f} q={item['question'][:80]}"
            )

    # 9. Simpan hasil ke file
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"evaluation_results_{timestamp}.json"

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "num_questions": len(eval_data),
        "threshold": THRESHOLD_TARGETS,
        "all_pass": all_pass,
        "scores": scores,
        "diagnostics": diagnostics,
        "details": [
            {
                "index": i + 1,
                "question": q,
                "answer": a,
                "ground_truth": gt,
                "contexts": c,
                "metrics": per_question_metrics[i],
            }
            for i, (q, a, c, gt) in enumerate(
                zip(questions, answers, contexts_list, ground_truths)
            )
        ],
    }

    output_file = Path(output_path)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Hasil evaluasi disimpan ke: {output_file}")
    return scores
