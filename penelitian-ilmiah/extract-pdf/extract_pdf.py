import argparse
import sys
from pathlib import Path

import pdfplumber
from loguru import logger


def extract_text(pdf_path: str, output_path: str) -> None:
    pdf_file = Path(pdf_path)
    out_file = Path(output_path)

    if not pdf_file.exists():
        logger.error(f"File PDF tidak ditemukan: {pdf_file}")
        sys.exit(1)

    logger.info(f"Memulai ekstraksi dari: {pdf_file.name}")
    all_text = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Total halaman: {total_pages}")
            
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                text = page.extract_text()
                
                all_text.append(f"{'='*60}")
                if text:
                    all_text.append(f"HALAMAN {page_num}")
                    all_text.append(f"{'='*60}")
                    all_text.append(text)
                else:
                    all_text.append(f"HALAMAN {page_num} (tidak ada teks yang bisa diekstrak)")
                    all_text.append(f"{'='*60}")
                    logger.warning(f"Halaman {page_num} kosong/tidak bisa diekstrak")
                    
                all_text.append("")
                
                if page_num % 10 == 0 or page_num == total_pages:
                    logger.debug(f"Progress: {page_num}/{total_pages} halaman selesai")
        
        full_text = "\n".join(all_text)
        
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        logger.success(f"Ekstraksi selesai! Output disimpan ke: {out_file}")
        logger.info(f"Total karakter: {len(full_text)}")

    except Exception as e:
        logger.error(f"Gagal mengekstrak PDF: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ekstrak teks dari file PDF dan simpan ke dalam file TXT."
    )
    parser.add_argument(
        "pdf_path",
        type=str,
        help="Path ke file PDF input"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="hasil_ekstrak.txt",
        help="Path ke file TXT output (default: hasil_ekstrak.txt)"
    )
    
    args = parser.parse_args()
    extract_text(args.pdf_path, args.output)


if __name__ == "__main__":
    main()
