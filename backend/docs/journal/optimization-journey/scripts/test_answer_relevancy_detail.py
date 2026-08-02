"""
Test untuk memahami apa yang RAGAS answer_relevancy sebenarnya ukur
"""

from main import run_rag_pipeline
from loguru import logger

def test_different_answers():
    """Test dengan pertanyaan yang sama tapi analisis jawaban berbeda"""
    
    question = "Apa syarat SKS minimal untuk mengambil PI?"
    
    logger.info(f"\n{'='*80}")
    logger.info(f"PERTANYAAN: {question}")
    logger.info(f"{'='*80}")
    
    # Run RAG pipeline
    result = run_rag_pipeline(question, debug=False)
    answer = result["answer"]
    
    logger.info(f"\n📝 JAWABAN YANG DIHASILKAN:")
    logger.info(f"{answer}")
    logger.info(f"\nPanjang: {len(answer)} karakter")
    logger.info(f"Jumlah kata: {len(answer.split())} kata")
    
    # Analisis struktur jawaban
    logger.info(f"\n🔍 ANALISIS STRUKTUR:")
    
    # Cek apakah jawaban mengulang pertanyaan
    question_words = set(question.lower().split())
    answer_words = set(answer.lower().split())
    overlap = question_words & answer_words
    
    logger.info(f"- Kata yang sama dengan pertanyaan: {overlap}")
    logger.info(f"- Overlap ratio: {len(overlap) / len(question_words):.2%}")
    
    # Cek apakah jawaban langsung menjawab
    if "syarat" in answer.lower() and "sks" in answer.lower() and "pi" in answer.lower():
        logger.info(f"- ✅ Jawaban mengandung kata kunci utama")
    else:
        logger.info(f"- ❌ Jawaban tidak mengandung semua kata kunci")
    
    # Cek apakah jawaban dimulai dengan konteks yang tepat
    if answer.lower().startswith(("syarat", "untuk mengambil pi", "mahasiswa")):
        logger.info(f"- ✅ Jawaban dimulai dengan konteks yang tepat")
    else:
        logger.info(f"- ⚠️  Jawaban tidak dimulai dengan konteks langsung")
    
    logger.info(f"\n💡 HIPOTESIS MASALAH ANSWER RELEVANCY:")
    logger.info(f"Answer relevancy mengukur seberapa baik jawaban 'menjawab pertanyaan'.")
    logger.info(f"Bukan hanya panjang, tapi juga:")
    logger.info(f"1. Apakah jawaban langsung address pertanyaan?")
    logger.info(f"2. Apakah jawaban mengandung kata kunci dari pertanyaan?")
    logger.info(f"3. Apakah jawaban fokus atau terlalu melebar?")
    logger.info(f"4. Apakah jawaban terstruktur dengan baik?")
    
    logger.info(f"\n📊 CONTOH JAWABAN IDEAL:")
    logger.info(f"Pertanyaan: 'Apa syarat SKS minimal untuk mengambil PI?'")
    logger.info(f"Jawaban IDEAL: 'Syarat SKS minimal untuk mengambil PI adalah 100 SKS dengan IP Kumulatif minimal 2,00.'")
    logger.info(f"- Langsung menjawab")
    logger.info(f"- Mengandung semua kata kunci")
    logger.info(f"- Fokus pada yang ditanyakan")
    logger.info(f"- Sertakan konteks relevan (IPK)")

if __name__ == "__main__":
    test_different_answers()
