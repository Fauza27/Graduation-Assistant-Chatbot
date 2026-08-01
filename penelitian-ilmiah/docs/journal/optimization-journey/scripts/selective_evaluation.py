"""
Selective Re-evaluation: Hanya evaluasi pertanyaan dengan score rendah
Menghemat biaya API dan waktu dengan fokus pada pertanyaan yang bermasalah
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from loguru import logger

from src.evaluation.ragas_eval import get_eval_questions, THRESHOLD_TARGETS, METRIC_NAMES


def load_previous_results(result_file: str) -> Dict:
    """Load hasil evaluasi sebelumnya"""
    with open(result_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def identify_problematic_questions(
    result_file: str,
    threshold_criteria: Dict[str, float] = None
) -> List[Dict]:
    """
    Identifikasi pertanyaan yang bermasalah berdasarkan threshold
    
    Args:
        result_file: Path ke file hasil evaluasi sebelumnya
        threshold_criteria: Dict dengan metrik dan threshold-nya
            Contoh: {
                "faithfulness": 0.5,  # Halusinasi
                "answer_relevancy": 0.5,  # Jawaban tidak relevan
                "answer_correctness": 0.5,  # Jawaban salah
                "context_recall": 0.5,  # Retrieval gagal
            }
    
    Returns:
        List of problematic questions dengan metadata
    """
    if threshold_criteria is None:
        # Default: ambil pertanyaan dengan score < 0.5 di metrik apapun
        threshold_criteria = {
            "faithfulness": 0.5,
            "answer_relevancy": 0.5,
            "answer_correctness": 0.5,
            "answer_similarity": 0.5,
            "context_precision": 0.5,
            "context_recall": 0.5,
        }
    
    results = load_previous_results(result_file)
    problematic = []
    
    for item in results['details']:
        is_problematic = False
        failing_metrics = []
        
        for metric, threshold in threshold_criteria.items():
            if item['metrics'][metric] < threshold:
                is_problematic = True
                failing_metrics.append({
                    'metric': metric,
                    'score': item['metrics'][metric],
                    'threshold': threshold
                })
        
        if is_problematic:
            problematic.append({
                'index': item['index'],
                'question': item['question'],
                'ground_truth': item['ground_truth'],
                'previous_answer': item['answer'],
                'previous_metrics': item['metrics'],
                'failing_metrics': failing_metrics,
                'contexts': item.get('contexts', [])
            })
    
    return problematic


def create_selective_dataset(problematic_questions: List[Dict]) -> List[Dict]:
    """
    Buat dataset untuk re-evaluasi hanya pertanyaan bermasalah
    
    Returns:
        List of questions dalam format RAGAS
    """
    dataset = []
    
    for pq in problematic_questions:
        dataset.append({
            'question': pq['question'],
            'ground_truth': pq['ground_truth'],
            'index': pq['index'],  # Simpan index asli untuk tracking
        })
    
    return dataset


def run_selective_evaluation(
    previous_result_file: str,
    threshold_criteria: Dict[str, float] = None,
    dataset_type: str = "both"
) -> Dict:
    """
    Jalankan evaluasi selektif hanya pada pertanyaan bermasalah
    
    Args:
        previous_result_file: Path ke hasil evaluasi sebelumnya
        threshold_criteria: Kriteria untuk menentukan pertanyaan bermasalah
        dataset_type: "pi", "kkp", atau "both"
    
    Returns:
        Dict dengan hasil evaluasi baru
    """
    logger.info(f"🔍 Menganalisis hasil evaluasi sebelumnya: {previous_result_file}")
    
    # Identifikasi pertanyaan bermasalah
    problematic = identify_problematic_questions(previous_result_file, threshold_criteria)
    
    logger.info(f"📊 Ditemukan {len(problematic)} pertanyaan bermasalah")
    
    # Breakdown per metrik
    metric_breakdown = {}
    for pq in problematic:
        for fm in pq['failing_metrics']:
            metric = fm['metric']
            if metric not in metric_breakdown:
                metric_breakdown[metric] = 0
            metric_breakdown[metric] += 1
    
    logger.info("📉 Breakdown per metrik:")
    for metric, count in sorted(metric_breakdown.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"   - {metric}: {count} pertanyaan")
    
    if len(problematic) == 0:
        logger.success("✅ Tidak ada pertanyaan bermasalah! Semua sudah di atas threshold.")
        return None
    
    # Buat dataset selektif
    selective_dataset = create_selective_dataset(problematic)
    
    logger.info(f"🚀 Menjalankan re-evaluasi pada {len(selective_dataset)} pertanyaan...")
    
    # Jalankan evaluasi RAGAS hanya pada pertanyaan bermasalah
    # Kita perlu modifikasi run_ragas_evaluation untuk menerima custom dataset
    results = run_ragas_evaluation_custom(selective_dataset, dataset_type)
    
    # Tambahkan metadata
    results['selective_evaluation'] = True
    results['previous_result_file'] = previous_result_file
    results['num_problematic_questions'] = len(problematic)
    results['threshold_criteria'] = threshold_criteria
    results['metric_breakdown'] = metric_breakdown
    
    # Simpan hasil
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"selective_evaluation_results_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.success(f"✅ Hasil selective evaluation disimpan ke: {output_file}")
    
    return results


def run_ragas_evaluation_custom(questions: List[Dict], dataset_type: str = "both") -> Dict:
    """
    Wrapper untuk evaluasi RAGAS dengan custom dataset
    """
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
    from config.settings import get_settings
    from main import run_rag_pipeline  # Import full RAG pipeline
    
    settings = get_settings()
    
    logger.info(f"📝 Generating answers untuk {len(questions)} pertanyaan...")
    
    # Generate answers menggunakan full RAG pipeline
    samples = []
    for i, q in enumerate(questions, 1):
        logger.info(f"   [{i}/{len(questions)}] {q['question'][:60]}...")
        
        # Jalankan full RAG pipeline
        result = run_rag_pipeline(q['question'], debug=False)
        
        sample = SingleTurnSample(
            user_input=q['question'],
            response=result['answer'],
            retrieved_contexts=result['contexts'],
            reference=q['ground_truth']
        )
        samples.append(sample)
    
    # Buat dataset
    dataset = EvaluationDataset(samples=samples)
    
    logger.info("🔬 Menjalankan evaluasi RAGAS...")
    
    # Setup LLM dan embeddings untuk RAGAS
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.open_api_key,
    )
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.open_api_key,
        dimensions=2000,
    )
    
    # Wrap untuk RAGAS
    ragas_llm = LangchainLLMWrapper(llm)
    ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)
    
    # Evaluasi
    result = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            answer_correctness,
            answer_similarity,
            context_precision,
            context_recall,
        ],
        llm=ragas_llm,
        embeddings=ragas_embeddings,
    )
    
    # Convert hasil ke format yang sama dengan evaluasi normal
    df = result.to_pandas()
    
    eval_results = []
    for idx, row in df.iterrows():
        eval_results.append({
            'index': questions[idx].get('index', idx),
            'question': questions[idx]['question'],
            'answer': samples[idx].response,
            'ground_truth': questions[idx]['ground_truth'],
            'contexts': samples[idx].retrieved_contexts,
            'metrics': {
                'faithfulness': row['faithfulness'],
                'answer_relevancy': row['answer_relevancy'],
                'answer_correctness': row['answer_correctness'],
                'answer_similarity': row['answer_similarity'],
                'context_precision': row['context_precision'],
                'context_recall': row['context_recall'],
            }
        })
    
    # Hitung scores
    scores = {}
    for metric in METRIC_NAMES:
        scores[metric] = df[metric].mean()
    
    scores['overall'] = sum(scores.values()) / len(scores)
    
    # Check threshold
    all_pass = all(scores[m] >= THRESHOLD_TARGETS[m] for m in METRIC_NAMES)
    
    return {
        'timestamp': datetime.now().isoformat(),
        'num_questions': len(questions),
        'dataset_type': dataset_type,
        'threshold': THRESHOLD_TARGETS,
        'all_pass': all_pass,
        'scores': scores,
        'details': eval_results
    }


def compare_results(previous_file: str, new_file: str) -> None:
    """
    Bandingkan hasil evaluasi sebelum dan sesudah perbaikan
    """
    prev = load_previous_results(previous_file)
    new = load_previous_results(new_file)
    
    print("\n" + "="*80)
    print("📊 PERBANDINGAN HASIL EVALUASI")
    print("="*80)
    
    print(f"\n📁 Previous: {previous_file}")
    print(f"📁 New: {new_file}")
    
    if new.get('selective_evaluation'):
        print(f"\n🎯 Selective Evaluation: {new['num_problematic_questions']} pertanyaan")
    
    print("\n" + "-"*80)
    print(f"{'Metric':<25} {'Previous':<12} {'New':<12} {'Change':<12} {'Status'}")
    print("-"*80)
    
    for metric in ['faithfulness', 'answer_relevancy', 'answer_correctness', 
                   'answer_similarity', 'context_precision', 'context_recall', 'overall']:
        prev_score = prev['scores'][metric]
        new_score = new['scores'][metric]
        change = new_score - prev_score
        
        status = "✅" if change > 0 else "❌" if change < 0 else "➡️"
        change_str = f"{change:+.4f}"
        
        print(f"{metric:<25} {prev_score:<12.4f} {new_score:<12.4f} {change_str:<12} {status}")
    
    print("-"*80)
    
    # Improvement summary
    improved = sum(1 for m in ['faithfulness', 'answer_relevancy', 'answer_correctness', 
                               'answer_similarity', 'context_precision', 'context_recall']
                   if new['scores'][m] > prev['scores'][m])
    
    print(f"\n📈 Improved metrics: {improved}/6")
    print(f"🎯 Overall change: {new['scores']['overall'] - prev['scores']['overall']:+.4f}")
    
    if new['all_pass']:
        print("\n🎉 SEMUA METRIK MENCAPAI THRESHOLD! ✅")
    else:
        failing = [m for m in ['faithfulness', 'answer_relevancy', 'answer_correctness', 
                               'answer_similarity', 'context_precision', 'context_recall']
                   if new['scores'][m] < new['threshold'][m]]
        print(f"\n⚠️  Metrik yang masih di bawah threshold: {', '.join(failing)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Selective Re-evaluation untuk pertanyaan bermasalah")
    parser.add_argument(
        "--previous",
        type=str,
        required=True,
        help="Path ke file hasil evaluasi sebelumnya"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Threshold untuk menentukan pertanyaan bermasalah (default: 0.5)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["pi", "kkp", "both"],
        default="both",
        help="Dataset yang akan di-evaluasi"
    )
    parser.add_argument(
        "--compare",
        type=str,
        help="Path ke file hasil evaluasi baru untuk dibandingkan"
    )
    
    args = parser.parse_args()
    
    if args.compare:
        # Mode comparison
        compare_results(args.previous, args.compare)
    else:
        # Mode selective evaluation
        threshold_criteria = {
            "faithfulness": args.threshold,
            "answer_relevancy": args.threshold,
            "answer_correctness": args.threshold,
            "answer_similarity": args.threshold,
            "context_precision": args.threshold,
            "context_recall": args.threshold,
        }
        
        results = run_selective_evaluation(
            args.previous,
            threshold_criteria,
            args.dataset
        )
        
        if results:
            print("\n" + "="*80)
            print("✅ SELECTIVE EVALUATION SELESAI")
            print("="*80)
            print(f"\nHasil disimpan di: selective_evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            print(f"\nJalankan dengan --compare untuk membandingkan hasil:")
            print(f"python selective_evaluation.py --previous {args.previous} --compare <new_file>")
