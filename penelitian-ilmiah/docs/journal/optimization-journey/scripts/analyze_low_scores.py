"""
Analisis Detail untuk Pertanyaan dengan Skor Rendah
Fokus pada answer_relevancy dan context_precision
"""

import json
from loguru import logger
from typing import List, Dict

def analyze_low_scores(
    json_file: str = "evaluation_results_no_gt_20260501_120903.json",
    answer_relevancy_threshold: float = 0.85,
    context_precision_threshold: float = 0.80
):
    """
    Analisis pertanyaan dengan skor rendah
    
    Args:
        json_file: Path ke file hasil evaluasi
        answer_relevancy_threshold: Threshold untuk answer relevancy
        context_precision_threshold: Threshold untuk context precision
    """
    
    # Load results
    with open(json_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    details = results['details']
    
    # Filter pertanyaan dengan skor rendah
    low_answer_relevancy = []
    low_context_precision = []
    low_both = []
    
    for item in details:
        metrics = item['metrics']
        ar_score = metrics.get('answer_relevancy', 1.0)
        cp_score = metrics.get('llm_context_precision_without_reference', 1.0)
        
        is_low_ar = ar_score < answer_relevancy_threshold
        is_low_cp = cp_score < context_precision_threshold
        
        if is_low_ar and is_low_cp:
            low_both.append(item)
        elif is_low_ar:
            low_answer_relevancy.append(item)
        elif is_low_cp:
            low_context_precision.append(item)
    
    # Sort by score (lowest first)
    low_answer_relevancy.sort(key=lambda x: x['metrics']['answer_relevancy'])
    low_context_precision.sort(key=lambda x: x['metrics']['llm_context_precision_without_reference'])
    low_both.sort(key=lambda x: (
        x['metrics']['answer_relevancy'] + 
        x['metrics']['llm_context_precision_without_reference']
    ) / 2)
    
    # Print summary
    logger.info("="*100)
    logger.info("ANALISIS PERTANYAAN DENGAN SKOR RENDAH")
    logger.info("="*100)
    logger.info(f"Total pertanyaan: {len(details)}")
    logger.info(f"Answer Relevancy < {answer_relevancy_threshold}: {len(low_answer_relevancy) + len(low_both)}")
    logger.info(f"Context Precision < {context_precision_threshold}: {len(low_context_precision) + len(low_both)}")
    logger.info(f"Keduanya rendah: {len(low_both)}")
    logger.info("="*100)
    
    # Analyze LOW BOTH (paling kritis)
    if low_both:
        logger.info("\n" + "="*100)
        logger.info("🔴 KRITIS: KEDUA METRIK RENDAH (Answer Relevancy + Context Precision)")
        logger.info("="*100)
        
        for i, item in enumerate(low_both[:10], 1):  # Top 10 terburuk
            metrics = item['metrics']
            logger.info(f"\n[{i}] Index: {item['index']}")
            logger.info(f"Question: {item['question']}")
            logger.info(f"Answer ({len(item['answer'])} chars, {len(item['answer'].split())} words):")
            logger.info(f"  {item['answer']}")
            logger.info(f"Metrics:")
            logger.info(f"  - Answer Relevancy: {metrics['answer_relevancy']:.4f} ❌")
            logger.info(f"  - Context Precision: {metrics['llm_context_precision_without_reference']:.4f} ❌")
            logger.info(f"  - Faithfulness: {metrics['faithfulness']:.4f}")
            logger.info(f"Contexts: {len(item['contexts'])} chunks")
            logger.info(f"First context preview: {item['contexts'][0][:200]}...")
            logger.info("-"*100)
    
    # Analyze LOW ANSWER RELEVANCY
    if low_answer_relevancy:
        logger.info("\n" + "="*100)
        logger.info("🟡 ANSWER RELEVANCY RENDAH (tapi Context Precision OK)")
        logger.info("="*100)
        
        for i, item in enumerate(low_answer_relevancy[:10], 1):  # Top 10 terburuk
            metrics = item['metrics']
            answer = item['answer']
            word_count = len(answer.split())
            
            logger.info(f"\n[{i}] Index: {item['index']}")
            logger.info(f"Question: {item['question']}")
            logger.info(f"Answer ({len(answer)} chars, {word_count} words):")
            logger.info(f"  {answer}")
            logger.info(f"Metrics:")
            logger.info(f"  - Answer Relevancy: {metrics['answer_relevancy']:.4f} ❌")
            logger.info(f"  - Context Precision: {metrics['llm_context_precision_without_reference']:.4f} ✅")
            logger.info(f"  - Faithfulness: {metrics['faithfulness']:.4f}")
            
            # Analisis pola jawaban
            issues = []
            if word_count < 10:
                issues.append("Terlalu singkat (<10 kata)")
            elif word_count > 50:
                issues.append("Terlalu panjang (>50 kata)")
            
            if "Berdasarkan" in answer or "Dokumen" in answer:
                issues.append("Menyebut sumber (tidak perlu)")
            
            if len(answer.split('.')) > 3:
                issues.append("Terlalu banyak kalimat (>3)")
            
            if issues:
                logger.info(f"Possible issues: {', '.join(issues)}")
            
            logger.info("-"*100)
    
    # Analyze LOW CONTEXT PRECISION
    if low_context_precision:
        logger.info("\n" + "="*100)
        logger.info("🟠 CONTEXT PRECISION RENDAH (tapi Answer Relevancy OK)")
        logger.info("="*100)
        
        for i, item in enumerate(low_context_precision[:10], 1):  # Top 10 terburuk
            metrics = item['metrics']
            logger.info(f"\n[{i}] Index: {item['index']}")
            logger.info(f"Question: {item['question']}")
            logger.info(f"Answer: {item['answer'][:150]}...")
            logger.info(f"Metrics:")
            logger.info(f"  - Answer Relevancy: {metrics['answer_relevancy']:.4f} ✅")
            logger.info(f"  - Context Precision: {metrics['llm_context_precision_without_reference']:.4f} ❌")
            logger.info(f"  - Faithfulness: {metrics['faithfulness']:.4f}")
            logger.info(f"Contexts: {len(item['contexts'])} chunks")
            logger.info(f"Context previews:")
            for j, ctx in enumerate(item['contexts'][:3], 1):
                logger.info(f"  [{j}] {ctx[:150]}...")
            logger.info("-"*100)
    
    # Statistical analysis
    logger.info("\n" + "="*100)
    logger.info("📊 ANALISIS STATISTIK")
    logger.info("="*100)
    
    # Answer length analysis for low AR
    if low_answer_relevancy or low_both:
        all_low_ar = low_answer_relevancy + low_both
        word_counts = [len(item['answer'].split()) for item in all_low_ar]
        avg_words = sum(word_counts) / len(word_counts)
        min_words = min(word_counts)
        max_words = max(word_counts)
        
        logger.info(f"\nAnswer Relevancy Rendah - Panjang Jawaban:")
        logger.info(f"  - Average: {avg_words:.1f} kata")
        logger.info(f"  - Min: {min_words} kata")
        logger.info(f"  - Max: {max_words} kata")
        logger.info(f"  - Target: 15-25 kata untuk faktual, 30-50 untuk prosedural")
        
        # Count by length category
        too_short = sum(1 for w in word_counts if w < 10)
        optimal = sum(1 for w in word_counts if 15 <= w <= 30)
        too_long = sum(1 for w in word_counts if w > 50)
        
        logger.info(f"\nDistribusi:")
        logger.info(f"  - Terlalu singkat (<10 kata): {too_short} ({too_short/len(word_counts)*100:.1f}%)")
        logger.info(f"  - Optimal (15-30 kata): {optimal} ({optimal/len(word_counts)*100:.1f}%)")
        logger.info(f"  - Terlalu panjang (>50 kata): {too_long} ({too_long/len(word_counts)*100:.1f}%)")
    
    # Context count analysis for low CP
    if low_context_precision or low_both:
        all_low_cp = low_context_precision + low_both
        context_counts = [len(item['contexts']) for item in all_low_cp]
        avg_contexts = sum(context_counts) / len(context_counts)
        
        logger.info(f"\nContext Precision Rendah - Jumlah Context:")
        logger.info(f"  - Average: {avg_contexts:.1f} chunks")
        logger.info(f"  - Min: {min(context_counts)} chunks")
        logger.info(f"  - Max: {max(context_counts)} chunks")
    
    # Save detailed analysis
    analysis_result = {
        "summary": {
            "total_questions": len(details),
            "low_answer_relevancy_count": len(low_answer_relevancy) + len(low_both),
            "low_context_precision_count": len(low_context_precision) + len(low_both),
            "low_both_count": len(low_both)
        },
        "low_both": low_both[:20],
        "low_answer_relevancy": low_answer_relevancy[:20],
        "low_context_precision": low_context_precision[:20]
    }
    
    output_file = "low_scores_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ Detailed analysis saved to: {output_file}")
    
    return analysis_result


if __name__ == "__main__":
    analyze_low_scores()
