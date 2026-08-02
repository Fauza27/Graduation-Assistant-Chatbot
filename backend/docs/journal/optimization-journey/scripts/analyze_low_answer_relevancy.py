"""
Analisis pertanyaan dengan Answer Relevancy terendah
untuk mengidentifikasi pola masalah
"""

import json
from loguru import logger
from typing import List, Dict


def analyze_low_answer_relevancy(
    json_file: str = "evaluation_results_no_gt_20260501_132931.json",
    top_n: int = 20
):
    """
    Analisis pertanyaan dengan Answer Relevancy terendah
    
    Args:
        json_file: Path ke file hasil evaluasi
        top_n: Jumlah pertanyaan dengan AR terendah yang akan dianalisis
    """
    
    # Load results
    with open(json_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    details = results['details']
    
    # Sort by answer_relevancy (lowest first)
    sorted_details = sorted(
        details, 
        key=lambda x: x['metrics'].get('answer_relevancy', 1.0)
    )
    
    # Get top N lowest
    lowest_ar = sorted_details[:top_n]
    
    logger.info("="*100)
    logger.info(f"ANALISIS {top_n} PERTANYAAN DENGAN ANSWER RELEVANCY TERENDAH")
    logger.info("="*100)
    
    # Analyze patterns
    patterns = {
        "tidak_ditemukan": 0,
        "terlalu_singkat": 0,  # <10 kata
        "terlalu_panjang": 0,  # >50 kata
        "optimal": 0,  # 15-30 kata
        "list_format": 0,
        "paragraph_format": 0,
    }
    
    for i, item in enumerate(lowest_ar, 1):
        question = item['question']
        answer = item['answer']
        ar_score = item['metrics']['answer_relevancy']
        word_count = len(answer.split())
        
        logger.info(f"\n[{i}] AR Score: {ar_score:.4f}")
        logger.info(f"Question: {question}")
        logger.info(f"Answer ({word_count} words):")
        logger.info(f"  {answer}")
        
        # Identify patterns
        issues = []
        
        if "tidak ditemukan" in answer.lower():
            patterns["tidak_ditemukan"] += 1
            issues.append("❌ Jawaban 'tidak ditemukan'")
        
        if word_count < 10:
            patterns["terlalu_singkat"] += 1
            issues.append("⚠️ Terlalu singkat (<10 kata)")
        elif word_count > 50:
            patterns["terlalu_panjang"] += 1
            issues.append("⚠️ Terlalu panjang (>50 kata)")
        elif 15 <= word_count <= 30:
            patterns["optimal"] += 1
            issues.append("✅ Panjang optimal (15-30 kata)")
        
        if answer.startswith("-") or "\n-" in answer:
            patterns["list_format"] += 1
            issues.append("📋 Format list")
        else:
            patterns["paragraph_format"] += 1
            issues.append("📝 Format paragraph")
        
        if issues:
            logger.info(f"Patterns: {', '.join(issues)}")
        
        logger.info("-"*100)
    
    # Summary
    logger.info("\n" + "="*100)
    logger.info("📊 SUMMARY POLA MASALAH")
    logger.info("="*100)
    
    total = len(lowest_ar)
    
    logger.info(f"\nPola Jawaban:")
    logger.info(f"  - ❌ 'Tidak ditemukan': {patterns['tidak_ditemukan']}/{total} ({patterns['tidak_ditemukan']/total*100:.1f}%)")
    logger.info(f"  - ⚠️ Terlalu singkat (<10 kata): {patterns['terlalu_singkat']}/{total} ({patterns['terlalu_singkat']/total*100:.1f}%)")
    logger.info(f"  - ⚠️ Terlalu panjang (>50 kata): {patterns['terlalu_panjang']}/{total} ({patterns['terlalu_panjang']/total*100:.1f}%)")
    logger.info(f"  - ✅ Optimal (15-30 kata): {patterns['optimal']}/{total} ({patterns['optimal']/total*100:.1f}%)")
    
    logger.info(f"\nFormat Jawaban:")
    logger.info(f"  - 📋 List format: {patterns['list_format']}/{total} ({patterns['list_format']/total*100:.1f}%)")
    logger.info(f"  - 📝 Paragraph format: {patterns['paragraph_format']}/{total} ({patterns['paragraph_format']/total*100:.1f}%)")
    
    # Recommendations
    logger.info("\n" + "="*100)
    logger.info("💡 REKOMENDASI PERBAIKAN")
    logger.info("="*100)
    
    if patterns['tidak_ditemukan'] > 0:
        logger.warning(f"\n1. MASALAH KRITIS: {patterns['tidak_ditemukan']} jawaban 'tidak ditemukan'")
        logger.info("   Solusi: Improve retrieval atau prompt agar LLM lebih teliti mencari informasi")
    
    if patterns['terlalu_singkat'] > total * 0.2:
        logger.warning(f"\n2. MASALAH: {patterns['terlalu_singkat']} jawaban terlalu singkat")
        logger.info("   Solusi: Prompt harus encourage jawaban lebih lengkap dengan konteks")
    
    if patterns['terlalu_panjang'] > total * 0.2:
        logger.warning(f"\n3. MASALAH: {patterns['terlalu_panjang']} jawaban terlalu panjang")
        logger.info("   Solusi: Prompt harus emphasize FOKUS dan tidak elaborasi berlebihan")
    
    # Calculate average AR for each pattern
    logger.info("\n" + "="*100)
    logger.info("📈 AVERAGE AR SCORE BY PATTERN")
    logger.info("="*100)
    
    tidak_ditemukan_scores = [
        item['metrics']['answer_relevancy'] 
        for item in lowest_ar 
        if "tidak ditemukan" in item['answer'].lower()
    ]
    
    singkat_scores = [
        item['metrics']['answer_relevancy'] 
        for item in lowest_ar 
        if len(item['answer'].split()) < 10 and "tidak ditemukan" not in item['answer'].lower()
    ]
    
    panjang_scores = [
        item['metrics']['answer_relevancy'] 
        for item in lowest_ar 
        if len(item['answer'].split()) > 50
    ]
    
    if tidak_ditemukan_scores:
        avg = sum(tidak_ditemukan_scores) / len(tidak_ditemukan_scores)
        logger.info(f"  - 'Tidak ditemukan': {avg:.4f} (n={len(tidak_ditemukan_scores)})")
    
    if singkat_scores:
        avg = sum(singkat_scores) / len(singkat_scores)
        logger.info(f"  - Terlalu singkat: {avg:.4f} (n={len(singkat_scores)})")
    
    if panjang_scores:
        avg = sum(panjang_scores) / len(panjang_scores)
        logger.info(f"  - Terlalu panjang: {avg:.4f} (n={len(panjang_scores)})")
    
    return lowest_ar, patterns


if __name__ == "__main__":
    analyze_low_answer_relevancy()
