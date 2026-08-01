"""
Test 10 pertanyaan yang sebelumnya gagal (mendapat score 0.0000)
untuk memverifikasi perbaikan Fase 1
"""

from loguru import logger
from main import run_rag_pipeline
from src.evaluation.ragas_eval_no_gt import evaluate_rag_no_ground_truth
import json
from datetime import datetime


# 10 pertanyaan yang sebelumnya mendapat score 0.0000 atau sangat rendah
FAILED_QUESTIONS = [
    "Apa ketentuan pakaian saat ujian PI untuk mahasiswa pria?",
    "Berapa maksimal kata dalam abstrak PI?",
    "Berapa jumlah kata kunci yang harus ada dalam abstrak PI?",
    "Apa saja elemen yang harus ada di halaman sampul depan PI?",
    "Berapa minimal halaman laporan KKP?",
    "Berapa jumlah minimal referensi yang harus ada dalam laporan KKP?",
    "Berapa jumlah kata kunci yang harus ada dalam abstrak KKP?",
    "Apa saja elemen yang harus ada di halaman sampul depan KKP?",
    "Apa ketentuan pakaian saat ujian KKP untuk mahasiswa pria?",
    "Apa ketentuan pakaian saat ujian KKP untuk mahasiswi berjilbab?",
]


def test_failed_questions():
    """Test pertanyaan yang sebelumnya gagal"""
    
    logger.info("="*100)
    logger.info("TESTING 10 PERTANYAAN YANG SEBELUMNYA GAGAL")
    logger.info("="*100)
    
    answers = []
    contexts = []
    
    for i, question in enumerate(FAILED_QUESTIONS, 1):
        logger.info(f"\n[{i}/10] Testing: {question}")
        logger.info("-"*100)
        
        try:
            result = run_rag_pipeline(question, debug=False)
            answer = result["answer"]
            context_list = result["contexts"]
            
            answers.append(answer)
            contexts.append(context_list)
            
            # Log hasil
            logger.info(f"Answer ({len(answer)} chars, {len(answer.split())} words):")
            logger.info(f"  {answer}")
            logger.info(f"Contexts: {len(context_list)} chunks")
            
            # Check if answer is "tidak ditemukan"
            if "tidak ditemukan" in answer.lower():
                logger.warning("⚠️  MASIH JAWAB 'TIDAK DITEMUKAN'!")
            else:
                logger.success("✅ Berhasil menjawab (bukan 'tidak ditemukan')")
            
        except Exception as e:
            logger.error(f"Error: {e}")
            answers.append("Error generating answer")
            contexts.append([])
    
    # Evaluate dengan RAGAS
    logger.info("\n" + "="*100)
    logger.info("RUNNING RAGAS EVALUATION")
    logger.info("="*100)
    
    results = evaluate_rag_no_ground_truth(
        questions=FAILED_QUESTIONS,
        answers=answers,
        contexts=contexts,
        dataset_name="failed_questions_test"
    )
    
    # Analisis hasil
    logger.info("\n" + "="*100)
    logger.info("ANALISIS HASIL")
    logger.info("="*100)
    
    scores = results['scores']
    details = results['details']
    
    # Count improvements
    still_zero_ar = 0
    still_zero_cp = 0
    still_not_found = 0
    
    for detail in details:
        metrics = detail['metrics']
        answer = detail['answer']
        
        if metrics['answer_relevancy'] == 0.0:
            still_zero_ar += 1
        
        if metrics['llm_context_precision_without_reference'] == 0.0:
            still_zero_cp += 1
        
        if "tidak ditemukan" in answer.lower():
            still_not_found += 1
    
    logger.info(f"\nHasil Perbaikan:")
    logger.info(f"  - Answer Relevancy = 0.0000: {still_zero_ar}/10 (sebelumnya: 10/10)")
    logger.info(f"  - Context Precision = 0.0000: {still_zero_cp}/10 (sebelumnya: 10/10)")
    logger.info(f"  - Jawaban 'tidak ditemukan': {still_not_found}/10 (sebelumnya: 10/10)")
    
    logger.info(f"\nScore Rata-rata:")
    logger.info(f"  - Faithfulness: {scores['faithfulness']:.4f}")
    logger.info(f"  - Answer Relevancy: {scores['answer_relevancy']:.4f} (target: ≥0.85)")
    logger.info(f"  - Context Precision: {scores['llm_context_precision_without_reference']:.4f} (target: ≥0.80)")
    logger.info(f"  - Overall: {scores['overall']:.4f} (target: ≥0.85)")
    
    # Improvement percentage
    if still_zero_ar < 10:
        improvement_ar = ((10 - still_zero_ar) / 10) * 100
        logger.success(f"\n✅ Improvement Answer Relevancy: {improvement_ar:.1f}% pertanyaan diperbaiki!")
    
    if still_zero_cp < 10:
        improvement_cp = ((10 - still_zero_cp) / 10) * 100
        logger.success(f"✅ Improvement Context Precision: {improvement_cp:.1f}% pertanyaan diperbaiki!")
    
    if still_not_found < 10:
        improvement_nf = ((10 - still_not_found) / 10) * 100
        logger.success(f"✅ Improvement 'Tidak Ditemukan': {improvement_nf:.1f}% pertanyaan diperbaiki!")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_failed_questions_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ Results saved to: {filename}")
    
    return results


if __name__ == "__main__":
    test_failed_questions()
