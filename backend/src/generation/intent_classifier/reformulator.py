"""Query reformulation for context-dependent academic questions."""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import get_settings
from src.generation.memory import ConversationMemory
from src.monitoring.openai_client import build_instrumented_http_client

IMPLICIT_REFERENCE_SIGNALS = [
    "yang itu",
    "hal itu",
    "tentang itu",
    "mengenai itu",
    "seperti itu",
    "tersebut",
    "tadi",
    "yang tadi",
    "lebih detail",
    "jelaskan lagi",
    "elaborasi",
    "lanjutkan",
    "bagaimana dengan",
    "kalau untuk",
    "dan untuk",
    "gimana kalau",
]

REFORMULATION_PROMPT = """
Anda membantu sistem pencarian dokumen internal akademik.

Gunakan istilah baku institusi:
- Penulisan Ilmiah (PI)
- Kuliah Kerja Praktik (KKP)
- Skripsi
- Tugas Akhir Non Skripsi

Riwayat percakapan:
{history}

Pertanyaan terkini user:
"{question}"

Jika pertanyaan terkini menggunakan referensi implisit seperti:
"itu", "tersebut", "yang tadi", "lebih detail tentang itu",
tulis ulang menjadi pertanyaan yang berdiri sendiri dan lengkap
untuk digunakan sebagai query pencarian.

Pertahankan domain yang disebut user. Istilah "seminar proposal",
"seminar hasil", dan "pendadaran" digunakan pada panduan Skripsi maupun
Non Skripsi, sehingga jangan menebak salah satu domain hanya dari istilah itu.

Jika pertanyaan sudah jelas dan mandiri,
kembalikan persis sama.

Output:
HANYA pertanyaan yang sudah ditulis ulang,
tanpa penjelasan apa pun.
""".strip()


class RewriteMethod(str, Enum):
    """Method used to rewrite a query."""

    NONE = "None"
    RULE = "Rule"
    LLM = "LLM"


SUFFIX_REWRITES = {
    "syaratnya": "syarat",
    "durasinya": "durasi",
    "formatnya": "format",
    "prosedurnya": "prosedur",
    "pendaftarannya": "pendaftaran",
    "dosennya": "dosen",
    "pembimbingnya": "pembimbing",
    "pengujinya": "penguji",
    "tempatnya": "tempat",
    "ujiannya": "ujian",
    "laporannya": "laporan",
    "nilainya": "nilai",
    "plagiarismenya": "plagiarisme",
    "referensinya": "referensi",
    "berkasnya": "berkas",
    "dokumennya": "dokumen",
    "batasnya": "batas",
    "tahapnya": "tahap",
    "alurnya": "alur",
    "bobotnya": "bobot",
    "komponennya": "komponen",
    "marginnya": "margin",
    "spasinya": "spasi",
    "fontnya": "font",
    "posternya": "poster",
    "videonya": "video",
    "sertifikatnya": "sertifikat",
    "publikasinya": "publikasi",
}

FOLLOW_UP_PREFIXES = (
    "kalau",
    "bagaimana dengan",
    "terus",
)

def contains_word(text: str, word: str) -> bool:
    """Check whether a complete word/phrase exists."""

    return (
        re.search(
            rf"\b{re.escape(word)}\b",
            text,
            re.IGNORECASE,
        )
        is not None
    )


def normalize_query(query: str) -> str:
    """
    Normalize common academic terminology.

    Examples:
        "apa syarat magang?" → "apa syarat KKP?"
        "apa itu kp"          → "Apa yang dimaksud dengan KKP"
    """

    # Bare "praktik" is intentionally not treated as KKP. It also appears in
    # unrelated phrases such as "praktik plagiarisme" and "praktik bisnis".
    query = re.sub(
        r"(?i)(?<!\w)(?:kp|k\.?\s*p\.?|magang|internship|pkl|"
        r"praktik\s+kerja\s+lapangan|praktek\s+kerja\s+lapangan|"
        r"kerja\s+praktik|kerja\s+praktek)(?!\w)",
        "KKP",
        query,
    )

    query = re.sub(
        r"(?i)(?<!\w)(?:pi|p\.?\s*i\.?)(?!\w)",
        "Penulisan Ilmiah",
        query,
    )

    query = re.sub(
        r"(?i)\b(?:tugas\s+akhir\s+)?non[\s-]*skripsi\b",
        "Tugas Akhir Non Skripsi",
        query,
    )

    query = re.sub(
        r"(?i)\bpenulisan\s+imliah\b",
        "Penulisan Ilmiah",
        query,
    )

    query = re.sub(
        r"(?i)\bapa\s+itu\s+(.+)",
        r"Apa yang dimaksud dengan \1",
        query,
    )

    return re.sub(
        r"\s+",
        " ",
        query,
    ).strip()


def needs_rewrite(query: str) -> bool:
    """
    Check whether a query contains implicit references or follow-up signals
    that require contextual reformulation using conversation history.
    """
    query_lower = query.lower().strip()

    # Cek kata/frasa pemicu referensi implisit
    for signal in IMPLICIT_REFERENCE_SIGNALS:
        if " " in signal:
            if signal in query_lower:
                return True
        else:
            if contains_word(query_lower, signal):
                return True

    # Cek kata berakhiran -nya yang ada di SUFFIX_REWRITES
    words = query_lower.split()
    for word in words:
        clean_word = word.lower().rstrip("?.,!")
        if clean_word in SUFFIX_REWRITES:
            return True

    # Cek awalan pertanyaan lanjutan
    if query_lower.startswith(FOLLOW_UP_PREFIXES):
        return True

    return False


def _extract_last_topic(
    memory: ConversationMemory,
) -> Optional[str]:
    """Find the most recently discussed academic topic."""

    for turn in reversed(memory.turns):
        content = turn.content.lower()

        if (
            "non skripsi" in content
            or "non-skripsi" in content
            or "nonskripsi" in content
            or "tugas akhir non skripsi" in content
            or "jalur karya ilmiah" in content
            or "wirausaha" in content
            or "profesional" in content
            or "business model canvas" in content
        ):
            return "Tugas Akhir Non Skripsi"

        if (
            contains_word(content, "skripsi")
            and "non skripsi" not in content
        ):
            return "Skripsi"

        if (
            contains_word(content, "pi")
            or "penulisan ilmiah" in content
        ):
            return "Penulisan Ilmiah"

        if (
            contains_word(content, "kkp")
            or "kuliah kerja praktik" in content
            or "kuliah kerja praktek" in content
            or contains_word(content, "magang")
        ):
            return "KKP"

    return None

@lru_cache(maxsize=1)
def _get_default_llm() -> ChatOpenAI:
    """Create and cache the reformulation LLM."""

    settings = get_settings()

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.open_api_key,
        http_client=build_instrumented_http_client(),
        temperature=0,
        max_tokens=200,
    )

class QueryReformulator:
    """
    Reformulate context-dependent queries.

    Priority:
        1. Normalize
        2. Deterministic rules
        3. LLM fallback
    """

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
    ) -> None:
        self._llm = llm or _get_default_llm()

    def reformulate(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> tuple[str, RewriteMethod]:
        """Return a self-contained retrieval query."""

        message = normalize_query(message)

        if memory.is_empty:
            return message, RewriteMethod.NONE

        last_topic = _extract_last_topic(memory)

        if last_topic:
            rewritten = self._rewrite_with_rules(
                message,
                last_topic,
            )

            if rewritten:
                self._log_rewrite(
                    RewriteMethod.RULE,
                    message,
                    rewritten,
                )
                return (
                    rewritten,
                    RewriteMethod.RULE,
                )

        rewritten = self._rewrite_with_llm(
            message,
            memory,
        )

        if rewritten:
            self._log_rewrite(
                RewriteMethod.LLM,
                message,
                rewritten,
            )
            return (
                rewritten,
                RewriteMethod.LLM,
            )

        return message, RewriteMethod.NONE

    def _rewrite_with_rules(
        self,
        message: str,
        last_topic: str,
    ) -> Optional[str]:
        """Apply deterministic rewrites."""

        message_lower = message.lower().strip()

        # Cek apakah topik sudah secara spesifik disebut dalam pesan saat ini
        topic_already_present = self._mentions_topic(
            message_lower,
            last_topic,
        )

        if topic_already_present:
            return None

        suffix_rewritten = self._rewrite_suffix(
            message,
            last_topic,
        )

        base = suffix_rewritten or message
        base_lower = base.lower().strip()

        if base_lower.startswith(FOLLOW_UP_PREFIXES):
            base_has_topic = self._mentions_topic(
                base_lower,
                last_topic,
            )
            if not base_has_topic:
                return (
                    f"{base.rstrip('?')} "
                    f"terkait {last_topic}?"
                )

            return base

        if suffix_rewritten:
            return suffix_rewritten

        return self._rewrite_implicit_reference(
            message,
            last_topic,
        )

    @staticmethod
    def _mentions_topic(
        message_lower: str,
        topic: str,
    ) -> bool:
        """Return whether a message already names the resolved domain."""

        aliases = {
            "tugas akhir non skripsi": (
                "tugas akhir non skripsi",
                "non skripsi",
                "non-skripsi",
                "nonskripsi",
                "jalur karya ilmiah",
                "jalur profesional",
                "jalur wirausaha",
            ),
            "penulisan ilmiah": (
                "penulisan ilmiah",
                "laporan pi",
                "ujian pi",
                "seminar pi",
            ),
            "kkp": (
                "kkp",
                "kuliah kerja praktik",
                "kuliah kerja praktek",
                "magang",
            ),
            "skripsi": ("skripsi",),
        }

        topic_lower = topic.lower()
        terms = aliases.get(topic_lower, (topic_lower,))

        if topic_lower == "skripsi" and any(
            phrase in message_lower
            for phrase in ("non skripsi", "non-skripsi", "nonskripsi")
        ):
            return False

        return any(
            contains_word(message_lower, term)
            for term in terms
        )

    @staticmethod
    def _rewrite_suffix(
        message: str,
        topic: str,
    ) -> Optional[str]:
        """Rewrite known '-nya' follow-up forms."""

        words = message.split()
        changed = False
        rewritten_words: list[str] = []

        for word in words:
            match = re.search(
                r"([?.,!]+)$",
                word,
            )

            punctuation = (
                match.group(1)
                if match
                else ""
            )

            normalized = (
                word.lower()
                .rstrip("?.,!")
            )

            replacement = SUFFIX_REWRITES.get(
                normalized
            )

            if replacement:
                rewritten_words.append(
                    f"{replacement} {topic}{punctuation}"
                )
                changed = True
            else:
                rewritten_words.append(word)

        if not changed:
            return None

        return " ".join(rewritten_words)

    @staticmethod
    def _rewrite_implicit_reference(
        message: str,
        topic: str,
    ) -> Optional[str]:
        """Resolve common implicit references without an LLM call."""

        rewritten, count = re.subn(
            r"\b(?:yang\s+)?(?:itu|tersebut|tadi)\b",
            topic,
            message,
            count=1,
            flags=re.IGNORECASE,
        )

        if count:
            return rewritten

        message_lower = message.lower().strip()
        contextual_follow_ups = (
            "lebih detail",
            "jelaskan lagi",
            "elaborasi",
            "lanjutkan",
        )

        if any(signal in message_lower for signal in contextual_follow_ups):
            return f"{message.rstrip('?')} terkait {topic}?"

        return None

    def _rewrite_with_llm(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> Optional[str]:
        """Use the LLM as the final fallback."""

        history = memory.get_conversation_summary()

        prompt = REFORMULATION_PROMPT.format(
            history=history,
            question=message,
        )

        try:
            response = self._llm.invoke(
                [HumanMessage(content=prompt)]
            )

        except Exception as exc:
            logger.warning(
                "LLM query reformulation failed: {}",
                exc,
            )
            return None

        reformulated = response.content.strip()

        if (
            not reformulated
            or reformulated == message
        ):
            return None

        return reformulated

    @staticmethod
    def _log_rewrite(
        method: RewriteMethod,
        original: str,
        rewritten: str,
    ) -> None:
        """Log successful query rewrites."""

        logger.info(
            "[Rewrite:{}] '{}' → '{}'",
            method.value,
            original,
            rewritten,
        )


@lru_cache(maxsize=1)
def _get_default_reformulator() -> QueryReformulator:
    """Return the shared reformulator."""

    return QueryReformulator()


def reformulate_query(
    message: str,
    memory: ConversationMemory,
    llm: ChatOpenAI | None = None,
) -> tuple[str, RewriteMethod]:
    """
    Backward-compatible helper.

    Existing callers can continue using:
        reformulate_query(message, memory)
    """

    reformulator = (
        _get_default_reformulator()
        if llm is None
        else QueryReformulator(llm)
    )

    return reformulator.reformulate(
        message,
        memory,
    )
