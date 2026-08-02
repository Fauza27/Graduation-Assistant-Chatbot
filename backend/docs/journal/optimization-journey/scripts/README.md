# Optimization Test Scripts

This folder contains test and analysis scripts used during the optimization process.

## 📁 Files Overview

### Test Scripts

**test_low_ar_questions.py**
- Tests 20 questions with lowest Answer Relevancy scores
- Used to verify improvements before running full evaluation
- Fast feedback loop (2-3 minutes vs 20 minutes for full eval)

**test_ragas_no_gt_single.py**
- Tests single question with RAGAS metrics
- Used for quick debugging and testing prompt changes
- Prevents wasting time on errors

**test_failed_questions.py**
- Tests specific failed questions from evaluation
- Used in Phase 1 and Phase 2 to verify fixes
- Tracks improvement on problematic questions

### Analysis Scripts

**analyze_low_answer_relevancy.py**
- Analyzes 20 questions with lowest AR scores
- Identifies patterns: word count, format, preambles
- Generates recommendations for improvements

**analyze_low_scores.py**
- Analyzes questions with low scores across all metrics
- Identifies "tidak ditemukan" answers
- Used in Phase 1 to identify root causes

**flag_suspicious_scores.py** ⭐ **NEW**
- Identifies potential false negatives in RAGAS evaluation
- Flags suspicious patterns (AR=0 but long answer, F=0 but high CP, etc.)
- Generates report of likely RAGAS limitations
- **Usage**: `python tests/optimization/flag_suspicious_scores.py`
- **Output**: `results/evaluations/suspicious_scores_analysis.json`

**selective_evaluation.py**
- Runs evaluation on subset of questions
- Used for faster iteration during optimization
- Allows testing specific question types

## 🚀 Usage

### Quick Test (2-3 minutes)
```bash
python tests/optimization/test_low_ar_questions.py
```

### Single Question Test (30 seconds)
```bash
python tests/optimization/test_ragas_no_gt_single.py
```

### Full Evaluation (20 minutes)
```bash
python main.py --evaluate-no-gt --dataset both
```

### Analyze Results
```bash
python tests/optimization/analyze_low_answer_relevancy.py
```

## 📊 Expected Results

After Phase 4 optimization:
- 'Tidak ditemukan' answers: 0/20 (0.0%)
- Average word count: ~30 words
- Optimal (15-30 words): 35-40%
- Echo principle: Answers contain question's key terms

## 🔗 Main Documentation
See [OPTIMIZATION_JOURNEY_COMPLETE.md](../../docs/OPTIMIZATION_JOURNEY_COMPLETE.md) for context.
