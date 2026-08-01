"""
Jalankan test sebelumnya dan simpan hasil ke file.
"""
import sys, os, json
os.environ["PYTHONIOENCODING"] = "utf-8"

from config.settings import get_settings
from main import run_rag_pipeline
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import (
    faithfulness, answer_relevancy, answer_correctness,
    answer_similarity, context_precision, context_recall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

settings = get_settings()

TEST_Q = "Apa syarat SKS minimal untuk mengambil Penulisan Ilmiah (PI)?"
TEST_GT = (
    "Mahasiswa yang berhak mengambil PI telah menyelesaikan mata kuliah "
    "dengan jumlah SKS minimal 100 SKS dan IP Kumulatif minimal 2,00."
)

# 1. Run pipeline
result = run_rag_pipeline(TEST_Q, debug=False)

# 2. Run RAGAS
sample = SingleTurnSample(
    user_input=TEST_Q,
    response=result["answer"],
    retrieved_contexts=result["contexts"],
    reference=TEST_GT,
)

evaluator_llm = LangchainLLMWrapper(ChatOpenAI(
    model=settings.llm_model, api_key=settings.open_api_key, temperature=0.0,
))
evaluator_emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(
    model=settings.embedding_model, api_key=settings.open_api_key,
))

ragas_result = evaluate(
    dataset=EvaluationDataset(samples=[sample]),
    metrics=[faithfulness, answer_relevancy, answer_correctness,
             answer_similarity, context_precision, context_recall],
    llm=evaluator_llm, embeddings=evaluator_emb,
)

# 3. Extract scores
output = {
    "question": TEST_Q,
    "answer": result["answer"],
    "num_contexts": len(result["contexts"]),
    "scores": {},
    "threshold": 0.85,
    "all_pass": True,
}

for m in ["faithfulness", "answer_relevancy", "answer_correctness",
          "answer_similarity", "context_precision", "context_recall"]:
    score = ragas_result[m]
    if hasattr(score, "tolist"):
        score = score.tolist()
    if isinstance(score, list):
        score = score[0] if score else 0.0
    score = float(score) if score is not None else 0.0
    passed = score >= 0.85
    if not passed:
        output["all_pass"] = False
    output["scores"][m] = {"value": round(score, 4), "pass": passed}

# Save to file
with open("test_ragas_result.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("DONE - results saved to test_ragas_result.json")
