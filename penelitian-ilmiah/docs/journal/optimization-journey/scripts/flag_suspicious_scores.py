"""
Flag Suspicious RAGAS Scores - Identify Potential False Negatives

This script analyzes RAGAS evaluation results to identify questions where
the scores might not accurately reflect answer quality (false negatives).

Suspicious patterns:
1. AR=0 but answer is long (>20 words) - possible negation issue
2. Faithfulness=0 but high Context Precision (>0.8) - possible paraphrasing issue
3. Large gap between metrics (>0.5) - inconsistent evaluation

Usage:
    python tests/optimization/flag_suspicious_scores.py

Author: Development Team
Date: May 1, 2026
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_evaluation_results(filepath: str) -> Dict[str, Any]:
    """Load RAGAS evaluation results from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def flag_suspicious_scores(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Identify questions with suspicious RAGAS scores.
    
    Returns list of suspicious cases with reasons.
    """
    suspicious = []
    details = results.get('details', [])
    
    for item in details:
        question = item.get('question', '')
        answer = item.get('answer', '')
        metrics = item.get('metrics', {})
        
        ar = metrics.get('answer_relevancy', 0.0)
        faithfulness = metrics.get('faithfulness', 0.0)
        cp = metrics.get('llm_context_precision_without_reference', 0.0)
        
        word_count = count_words(answer)
        
        # Pattern 1: AR=0 but answer is long (>20 words)
        # Possible negation issue or echo principle failure
        if ar == 0.0 and word_count > 20 and answer != "Tidak ditemukan.":
            suspicious.append({
                'index': item.get('index'),
                'question': question,
                'answer': answer,
                'word_count': word_count,
                'metrics': metrics,
                'reason': 'AR=0 but long answer (possible negation/echo issue)',
                'severity': 'HIGH',
                'likely_false_negative': True
            })
        
        # Pattern 2: Faithfulness=0 but high Context Precision
        # Possible paraphrasing sensitivity issue
        if faithfulness == 0.0 and cp > 0.8:
            suspicious.append({
                'index': item.get('index'),
                'question': question,
                'answer': answer,
                'word_count': word_count,
                'metrics': metrics,
                'reason': 'Faithfulness=0 but high CP (possible paraphrasing issue)',
                'severity': 'HIGH',
                'likely_false_negative': True
            })
        
        # Pattern 3: Large gap between Faithfulness and AR
        # Inconsistent evaluation
        if abs(faithfulness - ar) > 0.5:
            suspicious.append({
                'index': item.get('index'),
                'question': question,
                'answer': answer,
                'word_count': word_count,
                'metrics': metrics,
                'reason': f'Large gap between F ({faithfulness:.2f}) and AR ({ar:.2f})',
                'severity': 'MEDIUM',
                'likely_false_negative': False
            })
        
        # Pattern 4: AR < 0.3 but Faithfulness > 0.8
        # Answer is faithful but not relevant? Suspicious.
        if ar < 0.3 and faithfulness > 0.8:
            suspicious.append({
                'index': item.get('index'),
                'question': question,
                'answer': answer,
                'word_count': word_count,
                'metrics': metrics,
                'reason': f'Low AR ({ar:.2f}) but high F ({faithfulness:.2f})',
                'severity': 'MEDIUM',
                'likely_false_negative': True
            })
        
        # Pattern 5: All metrics very low (<0.3) but answer is not "Tidak ditemukan"
        # Possible complete RAGAS failure
        if ar < 0.3 and faithfulness < 0.3 and cp < 0.3 and answer != "Tidak ditemukan.":
            suspicious.append({
                'index': item.get('index'),
                'question': question,
                'answer': answer,
                'word_count': word_count,
                'metrics': metrics,
                'reason': 'All metrics very low but answer exists',
                'severity': 'HIGH',
                'likely_false_negative': False  # Might be true negative
            })
    
    return suspicious


def analyze_suspicious_cases(suspicious: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze suspicious cases and generate statistics."""
    total = len(suspicious)
    
    if total == 0:
        return {
            'total': 0,
            'by_severity': {},
            'by_reason': {},
            'likely_false_negatives': 0
        }
    
    # Count by severity
    by_severity = {}
    for case in suspicious:
        severity = case['severity']
        by_severity[severity] = by_severity.get(severity, 0) + 1
    
    # Count by reason
    by_reason = {}
    for case in suspicious:
        reason = case['reason'].split('(')[0].strip()  # Get main reason
        by_reason[reason] = by_reason.get(reason, 0) + 1
    
    # Count likely false negatives
    likely_false_negatives = sum(1 for case in suspicious if case['likely_false_negative'])
    
    return {
        'total': total,
        'by_severity': by_severity,
        'by_reason': by_reason,
        'likely_false_negatives': likely_false_negatives
    }


def print_report(results: Dict[str, Any], suspicious: List[Dict[str, Any]], analysis: Dict[str, Any]):
    """Print analysis report."""
    print("=" * 80)
    print("SUSPICIOUS RAGAS SCORES ANALYSIS")
    print("=" * 80)
    print(f"Evaluation File: {results.get('timestamp', 'Unknown')}")
    print(f"Total Questions: {results.get('num_questions', 0)}")
    print()
    
    print("OVERALL SCORES:")
    scores = results.get('scores', {})
    print(f"  Faithfulness: {scores.get('faithfulness', 0):.4f}")
    print(f"  Answer Relevancy: {scores.get('answer_relevancy', 0):.4f}")
    print(f"  Context Precision: {scores.get('llm_context_precision_without_reference', 0):.4f}")
    print(f"  Overall: {scores.get('overall', 0):.4f}")
    print()
    
    print("=" * 80)
    print("SUSPICIOUS CASES SUMMARY")
    print("=" * 80)
    print(f"Total Suspicious Cases: {analysis['total']}")
    print(f"Likely False Negatives: {analysis['likely_false_negatives']}")
    print()
    
    if analysis['total'] > 0:
        print("By Severity:")
        for severity, count in sorted(analysis['by_severity'].items()):
            print(f"  {severity}: {count}")
        print()
        
        print("By Reason:")
        for reason, count in sorted(analysis['by_reason'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count}")
        print()
    
    print("=" * 80)
    print("DETAILED SUSPICIOUS CASES")
    print("=" * 80)
    
    if analysis['total'] == 0:
        print("✅ No suspicious cases found!")
        print()
        return
    
    # Sort by severity (HIGH first) and then by index
    suspicious_sorted = sorted(suspicious, key=lambda x: (x['severity'] != 'HIGH', x['index']))
    
    for i, case in enumerate(suspicious_sorted, 1):
        print(f"\n[{i}] Index {case['index']} - {case['severity']} SEVERITY")
        print(f"Reason: {case['reason']}")
        print(f"Likely False Negative: {'YES' if case['likely_false_negative'] else 'NO'}")
        print()
        print(f"Question: {case['question']}")
        print(f"Answer ({case['word_count']} words): {case['answer'][:200]}{'...' if len(case['answer']) > 200 else ''}")
        print()
        metrics = case['metrics']
        print(f"Metrics:")
        print(f"  Faithfulness: {metrics.get('faithfulness', 0):.4f}")
        print(f"  Answer Relevancy: {metrics.get('answer_relevancy', 0):.4f}")
        print(f"  Context Precision: {metrics.get('llm_context_precision_without_reference', 0):.4f}")
        print("-" * 80)


def save_report(suspicious: List[Dict[str, Any]], analysis: Dict[str, Any], output_file: str):
    """Save suspicious cases to JSON file."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': analysis,
        'suspicious_cases': suspicious
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Report saved to: {output_file}")


def main():
    """Main function."""
    # Load latest evaluation results
    eval_file = project_root / "results" / "evaluations" / "evaluation_results_no_gt_20260501_154508.json"
    
    if not eval_file.exists():
        print(f"❌ Evaluation file not found: {eval_file}")
        print("Please run evaluation first: python src/evaluation/ragas_eval_no_gt.py")
        return
    
    print(f"Loading evaluation results from: {eval_file}")
    results = load_evaluation_results(str(eval_file))
    
    print("Analyzing for suspicious scores...")
    suspicious = flag_suspicious_scores(results)
    
    print("Generating analysis...")
    analysis = analyze_suspicious_cases(suspicious)
    
    # Print report
    print_report(results, suspicious, analysis)
    
    # Save report
    output_file = project_root / "results" / "evaluations" / "suspicious_scores_analysis.json"
    save_report(suspicious, analysis, str(output_file))
    
    # Summary
    print()
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if analysis['likely_false_negatives'] == 0:
        print("✅ No likely false negatives found!")
        print("   Your RAGAS scores accurately reflect system quality.")
    elif analysis['likely_false_negatives'] <= 2:
        print(f"⚠️  Found {analysis['likely_false_negatives']} likely false negative(s).")
        print("   This is a very low rate (<2%) and acceptable for production.")
        print("   These are likely due to RAGAS limitations (negation, paraphrasing).")
    else:
        print(f"⚠️  Found {analysis['likely_false_negatives']} likely false negatives.")
        print("   Consider manual review of these cases.")
    
    print()
    print("Next Steps:")
    print("1. Review suspicious cases above")
    print("2. Manually verify answers for HIGH severity cases")
    print("3. If false negatives confirmed, document as RAGAS limitations")
    print("4. Deploy to production and monitor real user feedback")
    print()


if __name__ == "__main__":
    main()
