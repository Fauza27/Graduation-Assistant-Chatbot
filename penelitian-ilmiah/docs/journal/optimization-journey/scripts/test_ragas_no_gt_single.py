"""
Test RAGAS evaluation tanpa ground truth untuk 1 pertanyaan
Untuk memastikan tidak ada error di akhir
"""

from src.evaluation.ragas_eval_no_gt import evaluate_rag_no_ground_truth
from main import run_rag_pipeline
from loguru import logger

def test_single_question():
    """Test dengan 1 pertanyaan saja"""
    
    # Test question
    question = "Apa syarat SKS minimal untuk mengambil PI?"
    
    logger.info(f"Testing with question: {question}")
    
    # Run RAG pipeline
    result = run_rag_pipeline(question, debug=False)
    answer = result["answer"]
    contexts = result["contexts"]
    
    logger.info(f"Answer: {answer[:100]}...")
    logger.info(f"Contexts: {len(contexts)} chunks")
    
    # Evaluate
    results = evaluate_rag_no_ground_truth(
        questions=[question],
        answers=[answer],
        contexts=[contexts],
        dataset_name="test"
    )
    
    logger.info("\n" + "="*80)
    logger.info("RESULTS:")
    logger.info(f"Scores: {results['scores']}")
    logger.info(f"All Pass: {results['all_pass']}")
    logger.info("="*80)
    
    return results

if __name__ == "__main__":
    test_single_question()
