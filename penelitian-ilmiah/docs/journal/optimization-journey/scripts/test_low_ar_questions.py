"""
Test script untuk 20 pertanyaan dengan Answer Relevancy terendah.
Digunakan untuk memverifikasi perbaikan FASE 3A dan 3B.
"""

import json
from loguru import logger
from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.parent_child import ParentChildFetcher
from src.generation.chain import RAGChain

# 20 pertanyaan dengan AR terendah dari evaluation_results_no_gt_20260501_132931.json
LOW_AR_QUESTIONS = [
    "Apa saja elemen yang harus ada di halaman sampul depan PI?",
    "Berapa minimal halaman laporan KKP?",
    "Apa saja elemen yang harus ada di halaman sampul depan KKP?",
    "Berapa IP Kumulatif minimal untuk mengambil PI?",
    "Apa hak mahasiswa dalam proses bimbingan PI?",
    "Berapa spasi yang digunakan untuk penulisan naskah utama PI?",
    "Bagaimana aturan penulisan judul bab dalam PI?",
    "Bagaimana cara menulis referensi yang tidak dipublikasikan dalam daftar pustaka PI?",
    "Bagaimana cara menulis referensi website dalam daftar pustaka PI?",
    "Apa saja berkas yang harus dilampirkan saat mendaftar ujian PI?",
    "Apa isi dari BAB III Metode Penelitian dalam laporan PI?",
    "Bagaimana cara menulis referensi jurnal dalam daftar pustaka PI?",
    "Bagaimana aturan penulisan judul tabel dalam PI?",
    "Bagaimana cara menulis referensi buku dalam daftar pustaka PI?",
    "Dalam kondisi apa mahasiswa dapat mengajukan penggantian dosen pembimbing PI?",
    "Berapa jumlah kata kunci yang harus ada dalam abstrak PI?",
    "Apa isi dari BAB IV Hasil Penelitian dan Pembahasan dalam laporan PI?",
    "Apa isi dari BAB V Penutup dalam laporan PI?",
    "Apa syarat jabatan fungsional minimal untuk menjadi dosen pembimbing atau penguji PI?",
    "Berapa lama maksimal masa bimbingan PI?",
]


def test_low_ar_questions():
    """Test 20 pertanyaan dengan AR terendah."""
    
    logger.info("=" * 100)
    logger.info("TEST 20 PERTANYAAN DENGAN ANSWER RELEVANCY TERENDAH")
    logger.info("=" * 100)
    logger.info(f"Total questions: {len(LOW_AR_QUESTIONS)}")
    logger.info("")
    
    # Initialize components
    logger.info("Initializing components...")
    hybrid_search = HybridSearcher()
    reranker = CrossEncoderReranker()
    parent_child = ParentChildFetcher()
    rag_chain = RAGChain()
    
    results = []
    tidak_ditemukan_count = 0
    
    for i, question in enumerate(LOW_AR_QUESTIONS, 1):
        logger.info("-" * 100)
        logger.info(f"[{i}/{len(LOW_AR_QUESTIONS)}] Question: {question}")
        
        try:
            # Retrieval pipeline
            child_chunks = hybrid_search.search(question, top_k=10)
            parent_chunks = parent_child.fetch_parents(child_chunks)
            reranked_parents = reranker.rerank(question, parent_chunks, top_n=5)
            
            # Generate answer
            response = rag_chain.invoke(
                question=question,
                context_documents=reranked_parents,
                return_sources=True
            )
            
            answer = response["answer"]
            word_count = len(answer.split())
            
            # Check if "tidak ditemukan"
            is_not_found = "tidak ditemukan" in answer.lower()
            if is_not_found:
                tidak_ditemukan_count += 1
            
            logger.info(f"Answer ({word_count} words): {answer[:150]}...")
            if is_not_found:
                logger.warning("⚠️ JAWABAN 'TIDAK DITEMUKAN'")
            
            results.append({
                "question": question,
                "answer": answer,
                "word_count": word_count,
                "is_not_found": is_not_found,
                "num_contexts": len(reranked_parents)
            })
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            results.append({
                "question": question,
                "answer": f"ERROR: {str(e)}",
                "word_count": 0,
                "is_not_found": False,
                "num_contexts": 0
            })
    
    # Summary
    logger.info("")
    logger.info("=" * 100)
    logger.info("📊 SUMMARY")
    logger.info("=" * 100)
    logger.info(f"Total questions tested: {len(results)}")
    logger.info(f"❌ 'Tidak ditemukan' answers: {tidak_ditemukan_count}/{len(results)} ({tidak_ditemukan_count/len(results)*100:.1f}%)")
    
    # Word count distribution
    word_counts = [r["word_count"] for r in results if not r["is_not_found"]]
    if word_counts:
        avg_words = sum(word_counts) / len(word_counts)
        logger.info(f"📝 Average word count (excluding 'tidak ditemukan'): {avg_words:.1f}")
        logger.info(f"   - Optimal (15-30 words): {sum(1 for w in word_counts if 15 <= w <= 30)}/{len(word_counts)}")
        logger.info(f"   - Too short (<15 words): {sum(1 for w in word_counts if w < 15)}/{len(word_counts)}")
        logger.info(f"   - Too long (>50 words): {sum(1 for w in word_counts if w > 50)}/{len(word_counts)}")
    
    # Save results
    output_file = "test_low_ar_questions_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info("")
    logger.info(f"✅ Results saved to: {output_file}")
    logger.info("")
    logger.info("=" * 100)
    logger.info("EXPECTED IMPROVEMENT:")
    logger.info("  - FASE 3A: 'Tidak ditemukan' should be 0/20 (currently 3/20 in old eval)")
    logger.info("  - FASE 3B: Average word count should be 15-30 words")
    logger.info("  - FASE 3B: Answers should be DIRECT without unnecessary preambles")
    logger.info("=" * 100)


if __name__ == "__main__":
    test_low_ar_questions()
