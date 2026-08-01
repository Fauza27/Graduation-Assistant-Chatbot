"""
Analisis mendalam untuk masalah answer_relevancy yang rendah
"""

from main import run_rag_pipeline
from loguru import logger
import json

def analyze_answer_quality():
    """Analisis kualitas jawaban untuk beberapa pertanyaan"""
    
    test_questions = [
        "Apa syarat SKS minimal untuk mengambil PI?",
        "Berapa IP Kumulatif minimal untuk mengambil PI?",
        "Siapa yang menjadi dosen pembimbing PI?",
        "Berapa lama maksimal masa bimbingan PI?",
        "Berapa jumlah minimal referensi yang harus ada dalam laporan PI?",
    ]
    
    results = []
    
    for i, question in enumerate(test_questions, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"PERTANYAAN {i}: {question}")
        logger.info(f"{'='*80}")
        
        # Run RAG pipeline
        result = run_rag_pipeline(question, debug=False)
        answer = result["answer"]
        contexts = result["contexts"]
        
        # Analisis
        analysis = {
            "question": question,
            "answer": answer,
            "answer_length": len(answer),
            "answer_word_count": len(answer.split()),
            "num_contexts": len(contexts),
            "contexts_preview": [ctx[:200] + "..." for ctx in contexts[:2]],
        }
        
        results.append(analysis)
        
        # Print analisis
        logger.info(f"\n📝 JAWABAN:")
        logger.info(f"   {answer}")
        logger.info(f"\n📊 STATISTIK:")
        logger.info(f"   - Panjang: {analysis['answer_length']} karakter")
        logger.info(f"   - Jumlah kata: {analysis['answer_word_count']} kata")
        logger.info(f"   - Jumlah context: {analysis['num_contexts']} chunks")
        
        # Analisis kualitas
        if analysis['answer_word_count'] < 10:
            logger.warning(f"   ⚠️  MASALAH: Jawaban terlalu SINGKAT (< 10 kata)")
            logger.warning(f"   💡 SARAN: Jawaban harus lebih lengkap dan informatif")
        elif analysis['answer_word_count'] < 20:
            logger.warning(f"   ⚠️  PERHATIAN: Jawaban cukup singkat (< 20 kata)")
        else:
            logger.info(f"   ✅ Panjang jawaban OK")
        
        logger.info(f"\n📚 CONTEXT PREVIEW (Top 2):")
        for j, ctx in enumerate(analysis['contexts_preview'], 1):
            logger.info(f"   Context {j}: {ctx}")
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"RINGKASAN ANALISIS")
    logger.info(f"{'='*80}")
    
    avg_length = sum(r['answer_length'] for r in results) / len(results)
    avg_words = sum(r['answer_word_count'] for r in results) / len(results)
    short_answers = sum(1 for r in results if r['answer_word_count'] < 10)
    
    logger.info(f"\n📊 STATISTIK KESELURUHAN:")
    logger.info(f"   - Rata-rata panjang: {avg_length:.1f} karakter")
    logger.info(f"   - Rata-rata jumlah kata: {avg_words:.1f} kata")
    logger.info(f"   - Jawaban terlalu singkat: {short_answers}/{len(results)}")
    
    if avg_words < 15:
        logger.warning(f"\n⚠️  DIAGNOSIS: Jawaban terlalu SINGKAT!")
        logger.warning(f"\n🔍 KEMUNGKINAN PENYEBAB:")
        logger.warning(f"   1. Prompt terlalu menekankan 'singkat dan padat'")
        logger.warning(f"   2. Model cenderung memberikan jawaban minimal")
        logger.warning(f"   3. Tidak ada instruksi untuk elaborasi")
        
        logger.info(f"\n💡 REKOMENDASI PERBAIKAN:")
        logger.info(f"   1. Ubah prompt untuk mendorong jawaban lebih lengkap")
        logger.info(f"   2. Tambahkan instruksi: 'Berikan penjelasan lengkap'")
        logger.info(f"   3. Minta model untuk elaborasi dengan contoh jika perlu")
        logger.info(f"   4. Set min_length atau target word count di prompt")
    
    # Save results
    with open("answer_relevancy_analysis.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ Analisis disimpan ke: answer_relevancy_analysis.json")
    
    return results

if __name__ == "__main__":
    analyze_answer_quality()
