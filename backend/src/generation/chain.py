from __future__ import annotations

import re
from typing import Iterator

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from operator import itemgetter

from config.settings import get_settings
from src.retrieval.source_utils import detect_panduan_type
from src.monitoring.context import set_field
from src.monitoring.pricing import calculate_llm_cost
from src.monitoring.openai_client import build_instrumented_http_client

settings = get_settings()

SYSTEM_PROMPT = """Anda adalah asisten akademik resmi STMIK Widya Cipta Dharma yang membantu mahasiswa memahami panduan KKP (Kuliah Kerja Praktik) dan PI (Penulisan Ilmiah).

ATURAN MENJAWAB:
1. Jika pengguna hanya menyapa (contoh: "halo", "terima kasih"), balaslah dengan ramah dan tawarkan bantuan terkait panduan akademik.
2. Jika pertanyaan akademik, jawab HANYA berdasarkan KONTEKS DOKUMEN yang diberikan dan riwayat percakapan.
3. DILARANG KERAS menggunakan pengetahuan internal Anda untuk menjawab substansi pertanyaan.
4. Jika tidak ada dokumen relevan ("Relevant documents found: NO") dan pertanyaan BUKAN sapaan, tolak dengan sopan dan jelaskan bahwa informasi tidak ditemukan pada knowledge base.
5. Selalu SEBUTKAN SUMBER jawaban Anda di awal untuk pertanyaan akademik (contoh: "Menurut BAB II...").
6. Berikan jawaban yang LENGKAP dan INFORMATIF — jangan terlalu singkat.
7. Untuk pertanyaan daftar/prosedur: gunakan poin bernomor atau bullet points.
"""

HUMAN_PROMPT_WITH_HISTORY = """KONTEKS DOKUMEN:
{context}

---

PERTANYAAN: {question}

INSTRUKSI:
1. Jika pertanyaan adalah sapaan/percakapan biasa, balas dengan ramah.
2. Jika pertanyaan akademik, jawab berdasarkan KONTEKS DOKUMEN di atas dan sebutkan sumbernya di awal.
3. Gunakan seluruh dokumen yang relevan sebagai dasar jawaban. Prioritaskan dokumen dengan relevansi tertinggi, namun gunakan dokumen lain apabila diperlukan untuk melengkapi atau memverifikasi informasi.
4. Gunakan format yang sesuai: paragraf untuk penjelasan, poin-poin untuk daftar.
5. Pastikan setiap informasi akademik BENAR-BENAR ada di konteks dokumen. Dilarang mengarang jawaban.

JAWABAN:"""


def _format_context(documents: list[Document] | list[dict] | str) -> str:
    if isinstance(documents, str):
        return documents if documents.strip() else "Tidak ada dokumen konteks yang tersedia."

    if not documents:
        return """=== Retrieval Status ===
Status: NO_RELEVANT_DOCUMENT
Reason: Tidak memenuhi batas minimum relevansi (Minimum Evidence Triggered)

Retrieved Context:
Tidak ditemukan dokumen akademik yang cukup relevan untuk menjawab pertanyaan ini.

INSTRUKSI KHUSUS:
- Jika pertanyaan merupakan percakapan umum (salam, ucapan terima kasih), jawablah secara normal.
- Jika pertanyaan meminta informasi akademik, katakan dengan sopan bahwa Anda tidak menemukan informasi yang relevan pada dokumen panduan yang tersedia dan DILARANG KERAS mengarang jawaban berdasarkan pengetahuan umum.
========================"""

    formatted_parts: list[str] = []

    for i, doc in enumerate(documents, start=1):
        if isinstance(doc, Document):
            content = doc.page_content
            meta = doc.metadata or {}
        elif isinstance(doc, dict):
            content = doc.get("content", "") or doc.get("page_content", "")
            meta = doc
        else:
            content = str(doc)
            meta = {}

        section = meta.get("section", "")
        title = meta.get("title", "")
        matched_children = meta.get("matched_children", [])

        # Build header
        panduan_type = detect_panduan_type(meta)
        header = f"[Sumber: Buku Panduan {panduan_type}]"
        if section:
            header += f" — {section}"
        if title and title != section:
            header += f" — {title}"

        score = meta.get("cross_encoder_score")
        if score is not None:
            header += f" | Relevansi: {score:.2f}"

        if matched_children:
            header += f" | Child Chunks: {len(matched_children)}"

        formatted_parts.append(f"{header}\n{content}")

    return "\n\n---\n\n".join(formatted_parts)


def _postprocess_answer(answer: str) -> str:
    # Strip leading/trailing whitespace
    answer = answer.strip()

    # Rapikan baris kosong berlebih dan spasi ganda
    answer = re.sub(r'\n{3,}', '\n\n', answer)
    answer = re.sub(r'  +', ' ', answer)

    return answer.strip()


def _build_sources(context_documents: list[Document] | list[dict] | str, limit: int = 3) -> list[dict]:
    if isinstance(context_documents, str):
        return []

    sources: list[dict] = []

    for doc in context_documents[:limit]:
        if isinstance(doc, Document):
            meta = doc.metadata or {}
            content = doc.page_content
        elif isinstance(doc, dict):
            meta = doc
            content = doc.get("content", "") or doc.get("page_content", "")
        else:
            continue

        sources.append(
            {
                "parent_id": meta.get("parent_id", ""),
                "title": meta.get("title", ""),
                "section": meta.get("section", ""),
                "source": meta.get("source", ""),
                "relevance_score": meta.get("cross_encoder_score"),
                "chunk_preview": (content[:200] + "...") if content else "",
                "matched_children": meta.get("matched_children", []),
            }
        )

    return sources


def build_rag_chain(streaming: bool = False):
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.open_api_key,
        temperature=0,
        max_tokens=1200,
        streaming=streaming,
        http_client=build_instrumented_http_client(),
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT_WITH_HISTORY),
    ])

    output_parser = StrOutputParser()

    chain = (
        {
            "context": lambda x: _format_context(x["context"]),
            "question": itemgetter("question"),
        }
        | prompt
        | llm
        | output_parser
    )

    return chain


class RAGChain:

    def __init__(self):
        self._chain = build_rag_chain(streaming=False)
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.open_api_key,
            temperature=0,
            http_client=build_instrumented_http_client(),
        )

    def invoke_with_history(
        self,
        question: str,
        context_documents: list[Document] | list[dict] | str,
        conversation_history: list[dict],
        return_sources: bool = True,
    ) -> dict[str, str | list]:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        import tiktoken
        
        # Setup tokenizer for profiling
        try:
            encoder = tiktoken.encoding_for_model(settings.llm_model)
        except KeyError:
            encoder = tiktoken.encoding_for_model("gpt-4o")

        def count_tokens(text: str) -> int:
            return len(encoder.encode(text))

        logger.info(
            "Generating answer for: '{question}' (history: {count} messages)".format(
                question=question[:60],
                count=len(conversation_history),
            )
        )

        if not context_documents:
            logger.info("Minimum Evidence Triggered. Continuing to LLM with empty context for conversation handling.")
            # Adaptive History: Truncate history to only 1 turn (last 2 messages) for conversational queries
            if len(conversation_history) > 2:
                conversation_history = conversation_history[-2:]

        context_str = _format_context(context_documents)
        
        # Perform Token Profiling
        system_tokens = count_tokens(SYSTEM_PROMPT)
        history_tokens = sum(count_tokens(m.get("content", "")) for m in conversation_history)
        context_tokens = count_tokens(context_str)
        query_tokens = count_tokens(question)

        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        for msg in conversation_history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg.get("content", "")))

        human_content = HUMAN_PROMPT_WITH_HISTORY.format(
            context=context_str,
            question=question,
        )
        messages.append(HumanMessage(content=human_content))

        response = self._llm.invoke(messages)
        answer = _postprocess_answer(response.content)

        # Token usage AKTUAL dari OpenAI (bukan estimasi tiktoken lagi).
        # `usage_metadata` adalah field resmi langchain-openai berisi
        # {"input_tokens": int, "output_tokens": int, "total_tokens": int}.
        # Fallback ke estimasi tiktoken kalau field ini tidak tersedia
        # (mis. versi langchain-openai lama, atau provider non-OpenAI).
        usage = getattr(response, "usage_metadata", None)
        if usage:
            actual_input_tokens = usage.get("input_tokens")
            actual_output_tokens = usage.get("output_tokens")
        else:
            logger.warning("response.usage_metadata tidak tersedia, fallback ke estimasi tiktoken.")
            actual_input_tokens = system_tokens + history_tokens + context_tokens + query_tokens
            actual_output_tokens = count_tokens(answer)

        llm_cost = calculate_llm_cost(settings.llm_model, actual_input_tokens, actual_output_tokens)
        set_field(
            input_tokens=actual_input_tokens,
            output_tokens=actual_output_tokens,
            llm_cost_usd=llm_cost,
        )

        profile_log = (
            f"\n========== PROMPT PROFILE ==========\n"
            f"System Prompt     : {system_tokens} tokens (estimasi)\n"
            f"History           : {history_tokens} tokens (estimasi)\n"
            f"Retrieved Context : {context_tokens} tokens (estimasi)\n"
            f"User Query        : {query_tokens} tokens (estimasi)\n"
            f"------------------------------------\n"
            f"Input Aktual (API): {actual_input_tokens} tokens\n"
            f"Output Aktual (API): {actual_output_tokens} tokens\n"
            f"Cost              : ${llm_cost:.6f}\n"
            f"===================================="
        )
        logger.info(profile_log)

        result: dict[str, str | list] = {"answer": answer}

        if return_sources:
            result["sources"] = _build_sources(context_documents)

        logger.success(f"Generation complete: {len(answer)} chars")
        return result


_rag_chain_instance: object | None = None

def _get_rag_chain():
    global _rag_chain_instance
    if _rag_chain_instance is None:
        _rag_chain_instance = build_rag_chain(streaming=False)
    return _rag_chain_instance


def generate_answer(question: str, context: str) -> str:
    chain = _get_rag_chain() 

    logger.info(f"Generating answer for: '{question[:80]}...'")
    logger.debug(f"Context length: {len(context)} chars")

    answer = chain.invoke({
        "context": context,
        "question": question,
    })
    
    answer = _postprocess_answer(answer)
    logger.info(f"Answer generated: {len(answer)} chars")
    return answer