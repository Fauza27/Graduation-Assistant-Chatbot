from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config.settings import get_settings
from src.generation.memory import Turn
from src.generation.token_utils import count_tokens
from src.monitoring.context import get_current
from src.monitoring.openai_client import build_instrumented_http_client
from src.monitoring.pricing import calculate_llm_cost


SUMMARY_SYSTEM_PROMPT = """
Anda merangkum percakapan chatbot akademik dalam bahasa Indonesia.
Pertahankan topik, pertanyaan, jawaban yang sudah diberikan, preferensi atau
kondisi yang dinyatakan user, serta hal yang belum selesai. Bedakan pernyataan
user dari informasi yang berasal dari jawaban assistant. Jangan menambah fakta
baru. Tulis ringkasan padat dalam paragraf biasa tanpa judul pembuka.
""".strip()


class ConversationSummarizer:
    """Menggabungkan summary lama dengan complete exchanges yang dipadatkan."""

    def __init__(self, llm: ChatOpenAI) -> None:
        self._llm = llm

    def summarize(
        self,
        existing_summary: str,
        turns: tuple[Turn, ...],
    ) -> str:
        transcript = "\n".join(
            f"{'User' if turn.role == 'user' else 'Assistant'}: {turn.content}"
            for turn in turns
        )
        prompt = (
            "RINGKASAN SEBELUMNYA:\n"
            f"{existing_summary or '-'}\n\n"
            "PERCAKAPAN LAMA YANG PERLU DIGABUNGKAN:\n"
            f"{transcript}\n\n"
            "Tulis ringkasan gabungan yang menggantikan ringkasan sebelumnya."
        )
        response = self._llm.invoke(
            [
                SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        summary = str(response.content).strip()
        self._record_usage(response, prompt, summary)
        return summary

    @staticmethod
    def _record_usage(response: object, prompt: str, summary: str) -> None:
        """Tambahkan biaya summarization ke metrik request yang sama."""
        collector = get_current()
        if collector is None:
            return

        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = usage.get("input_tokens") or count_tokens(
            SUMMARY_SYSTEM_PROMPT + prompt
        )
        output_tokens = usage.get("output_tokens") or count_tokens(summary)
        model = get_settings().llm_model

        collector.input_tokens = (collector.input_tokens or 0) + input_tokens
        collector.output_tokens = (collector.output_tokens or 0) + output_tokens
        collector.llm_cost_usd = (
            (collector.llm_cost_usd or 0)
            + calculate_llm_cost(model, input_tokens, output_tokens)
        )


@lru_cache(maxsize=1)
def get_conversation_summarizer() -> ConversationSummarizer:
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.open_api_key,
        temperature=0,
        max_tokens=settings.MEMORY_SUMMARY_MAX_TOKENS,
        http_client=build_instrumented_http_client(),
    )
    return ConversationSummarizer(llm)
