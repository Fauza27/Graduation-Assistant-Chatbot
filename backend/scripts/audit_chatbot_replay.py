"""Attach a dated manual review to a saved chatbot replay.

The review entries below are manual judgments by the assistant against the
four source guides. They are an exploratory review, not a blinded answer key.
This script only joins those judgments to the replay; it does not infer
correctness from model output or call an API.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "results/chatbot_repair/replay-quality-full-20260929.json"
OUTPUT = ROOT / "results/chatbot_repair/review-manual-20260929.csv"

# Status: salah = inti jawaban salah/tidak menjawab; sebagian = inti benar tetapi
# ada klaim tambahan, cakupan, atau rujukan yang bermasalah; ambigu = ketentuan
# atau maksud tidak cukup jelas untuk diputuskan; sesuai = tidak ditemukan
# masalah materi dalam audit awal ini.
ISSUES: dict[str, tuple[str, str, str, str]] = {
    "S01Q08": ("sebagian", "Konsekuensi melewati batas satu minggu tidak dijelaskan; respons memberi prosedur menghubungi pembimbing/Kaprodi yang tidak tercantum.", "Skripsi 2.6.1 Bimbingan Proposal poin 1", "generation"),
    "S03Q02": ("sebagian", "Konteks percakapan adalah Skripsi, tetapi jawaban menggabungkan syarat IPK Non-Skripsi sehingga berkas yang diminta tampak berlaku untuk dua jalur.", "Skripsi 2.6.1 Prosedur Pendaftaran Seminar Proposal", "generation"),
    "S03Q05": ("salah", "Jawaban mengatakan tidak ada batas halaman; panduan menetapkan proposal Skripsi minimal 40 halaman.", "Skripsi 2.6.1 Seminar Proposal poin 2", "retrieval+generation"),
    "S04Q02": ("salah", "Pertanyaan lanjutan dari sempro dijawab sebagai PI dan ditambah saran tanpa aturan perpanjangan yang jelas.", "Skripsi 2.6.1 poin 8: proposal berlaku satu tahun akademik", "conversation+generation"),
    "S04Q03": ("salah", "Konteks sempro/penelitian bergeser ke PI; panduan Skripsi justru mewajibkan surat pengantar penelitian.", "Skripsi 2.6.2 Pelaksanaan Penelitian poin 1", "conversation+retrieval"),
    "S04Q04": ("salah", "Tidak menjawab siapa penerbit surat; surat penelitian Skripsi diterbitkan BAAK.", "Skripsi 2.6.2 Pelaksanaan Penelitian poin 1", "conversation+generation"),
    "S04Q05": ("salah", "Jawaban mengesankan Pembimbing dan Kaprodi sebagai penandatangan; panduan Skripsi menyebut paraf Pembimbing dan tanda tangan Wakil Ketua I.", "Skripsi 2.6.2 Pelaksanaan Penelitian poin 1", "conversation+retrieval+generation"),
    "S04Q06": ("salah", "Jawaban memakai aturan minimal dua laporan PI, sedangkan pertanyaan berada pada alur penelitian setelah sempro Skripsi.", "Skripsi 2.6.2 Pelaksanaan Penelitian poin 3", "conversation+retrieval"),
    "S04Q07": ("salah", "Jawaban menyatakan surat pengantar tidak diperlukan pada PI tanpa instansi; panduan PI tetap menyebut penerbitan surat BAAK, dengan pengecualian pada penyerahannya ke instansi.", "PI 2.7.1 Pengajuan Tempat Penelitian poin 5-6", "generation"),
    "S04Q08": ("salah", "Jawaban mengulang bahwa PI tanpa instansi tidak perlu surat pengantar, bertentangan dengan poin 5 dan 6 panduan PI.", "PI 2.7.1 Pengajuan Tempat Penelitian poin 5-6", "generation"),
    "S04Q09": ("sebagian", "Dua seminar di semester berbeda mungkin terjadi, tetapi jawaban memastikan kebolehan tanpa menyinggung masa berlaku proposal satu tahun akademik.", "Skripsi 2.6.1 Seminar Proposal poin 8", "generation"),
    "S05Q06": ("sebagian", "Isi aturan video sesuai dengan Skripsi, tetapi jawaban menisbahkannya hanya ke panduan Non-Skripsi di tengah sesi Skripsi.", "Skripsi 2.6.2 Ketentuan Pembuatan Video", "citation"),
    "S06Q06": ("salah", "Jawaban menyebut halaman pengesahan ditandatangani sebelum pendadaran; panduan menempatkannya setelah revisi ujian diterima Pembimbing dan Penguji.", "Skripsi 2.6.4 Tahap Akhir poin 4", "retrieval+generation"),
    "S07Q05": ("salah", "Panduan mengharuskan minimal 80% dari 15 referensi berasal dari buku dan jurnal; jawaban menyimpulkan seluruh sumber harus buku/jurnal.", "PI Ketentuan Daftar Pustaka poin 2", "generation"),
    "S07Q07": ("sebagian", "Jawaban mula-mula mengatakan tidak ada syarat khusus tempat PI lalu menyebut syarat resmi/kesesuaian bidang dari definisi tempat penelitian. Perbedaan ketentuan dan deskripsi perlu diperjelas.", "PI 2.6 Tempat Penelitian PI", "generation"),
    "S07Q08": ("salah", "Tidak ada izin atau kuota beberapa mahasiswa per tempat PI dalam panduan, tetapi jawaban menyatakan penggunaan bersama dapat dianggap sah.", "PI 2.6 Tempat Penelitian PI", "generation"),
    "S09Q01": ("sebagian", "Daftar berkas mengikuti 2.7.3, tetapi menyatakan semua berkas berlaku tanpa membahas pengecualian PI tanpa instansi untuk surat balasan/daftar wawancara yang tidak diperjelas dalam pasal itu.", "PI 2.7.1 poin 5-8 dan 2.7.3", "source-ambiguity+generation"),
    "S11Q01": ("salah", "Mahasiswa baru mendapatkan tempat KKP, tetapi jawaban langsung menyuruh menyiapkan berkas ujian; tahap yang relevan ialah form usulan, persetujuan Pembimbing/Kaprodi, dan surat pengantar BAAK.", "KKP 2.7.1 Tahap Awal Pengajuan KKP", "retrieval+generation"),
    "S11Q07": ("sebagian", "Dua pasal bimbingan yang bertentangan memang perlu dicatat, tetapi jawaban tidak memberi jawaban langsung bahwa bimbingan juga dilakukan saat pelaksanaan KKP.", "KKP 2.4.2 poin 3; 2.7.2 poin 1(3)", "generation"),
    "S12Q02": ("salah", "Jawaban mengambil BAB I pendahuluan buku panduan, bukan BAB I laporan KKP. Isi laporan semestinya deskripsi tempat, waktu pelaksanaan, dan lokasi KKP.", "KKP Tabel 3.1; 4.2.1 BAB I PENDAHULUAN", "retrieval+generation"),
    "S12Q07": ("sebagian", "Surat balasan memang dicontohkan sebagai lampiran, tetapi jawaban menyatakan harus tanpa membedakan frasa 'antara lain' dari kewajiban eksplisit.", "KKP 4.3 Bagian Akhir", "generation"),
    "S12Q08": ("sebagian", "Daftar 'antara lain' dinyatakan semuanya wajib dan ditambah foto/laporan harian yang tidak disebut pada bagian lampiran itu.", "KKP 4.3 Bagian Akhir", "generation"),
    "S13Q01": ("sebagian", "Panduan mewajibkan hadir tiga seminar sebelum melaksanakan seminar KKP; jawaban mencampur syarat pelaksanaan dengan waktu pendaftaran dan menambah kata 'mungkin'.", "KKP 2.7.2 Setelah Selesai KKP poin 4", "generation"),
    "S15Q08": ("ambigu", "Panduan berbunyi 'berstatus AKTIF atau DIPUBLIKASI dalam 2 tahun terakhir'. Tanpa definisi status aktif, publikasi tiga tahun lalu tidak cukup untuk menyimpulkan penolakan mutlak.", "Non-Skripsi 3.1.2 poin 4", "source-ambiguity"),
    "S18Q01": ("sebagian", "Kelayakan dinyatakan bersyarat, tetapi rangkuman syarat tidak menyebut dokumen kepemilikan, NPWP perusahaan, laporan pajak, dan company profile.", "Non-Skripsi 3.3.2 dan 3.3.3", "generation"),
    "S18Q04": ("sebagian", "Jawaban tentang legalitas melewatkan izin operasional/NIB yang dinyatakan pada 3.3.3; company profile juga bukan dokumen legalitas dalam arti sempit.", "Non-Skripsi 3.3.2 dan 3.3.3 poin 2", "retrieval+generation"),
    "S18Q05": ("salah", "Panduan secara eksplisit mensyaratkan NPWP atas nama perusahaan; jawaban menyatakan tidak disebut eksplisit dan memberi dugaan bahwa NPWP pribadi mungkin bisa.", "Non-Skripsi 3.3.2 poin 4", "retrieval+generation"),
    "S18Q07": ("sebagian", "Pernah mengikuti inkubasi memenuhi salah satu alternatif khusus startup tanpa omzet, tetapi jawaban tidak mengingatkan syarat usaha umum yang tetap harus dipenuhi.", "Non-Skripsi 3.3.2 dan 3.3.3 poin 3", "generation"),
    "S18Q08": ("sebagian", "Panduan mencantumkan media sosial sebagai bentuk company profile, tetapi jawaban hanya menyatakan akun media sosial bisa menjadi bagian profil dan tidak menjawab jelas apakah itu dapat menjadi satu-satunya bentuk profil.", "Non-Skripsi 3.3.2 poin 6", "generation"),
    "S19Q02": ("sebagian", "Pertanyaan mengikuti perbandingan Profesional dan Wirausaha, tetapi jawaban hanya menjelaskan proposal Profesional. Keduanya berakhir pada BAB II menurut tabel masing-masing.", "Non-Skripsi Tabel 3.7 dan 3.11", "conversation+generation"),
    "S19Q03": ("sebagian", "Pertanyaan masih merujuk Profesional dan Wirausaha, tetapi jawaban hanya membahas laporan Profesional. Keduanya berakhir pada BAB IV.", "Non-Skripsi Tabel 3.8 dan 3.12", "conversation+generation"),
}


# These historical manual labels apply only to the exact reviewed responses.
REVIEWED_REPLAY_SHA256 = "fe4883350d36d3ccbf9af19c274aff7cd50af295f6556e8ce0f87d02d603aa71"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("Historical review already exists; do not overwrite it")
    if hashlib.sha256(REPLAY.read_bytes()).hexdigest() != REVIEWED_REPLAY_SHA256:
        raise ValueError("These manual judgments do not apply to this replay snapshot")
    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    rows = []
    seen = set()
    for session in replay["sessions"]:
        session_id = int(session["name"].split("_", 1)[0])
        for interaction in session["interactions"]:
            case_id = f"S{session_id:02d}Q{interaction['index']:02d}"
            status, reason, evidence, cause = ISSUES.get(
                case_id,
                ("sesuai", "Pokok jawaban cocok dengan bagian panduan yang diperiksa pada audit ini.",
                 " | ".join(source.get("section", "") for source in interaction.get("sources", [])), ""),
            )
            rows.append({
                "case_id": case_id,
                "session": session["name"],
                "question": interaction["question"],
                "answer": interaction["answer"],
                "status": status,
                "reason": reason,
                "evidence": evidence,
                "likely_cause": cause,
            })
            seen.add(case_id)
    unknown = set(ISSUES) - seen
    if unknown:
        raise ValueError(f"Unknown case IDs: {sorted(unknown)}")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Reviewed {len(rows)} responses: {dict(Counter(row['status'] for row in rows))}")
    print(OUTPUT)


if __name__ == "__main__":
    main()
