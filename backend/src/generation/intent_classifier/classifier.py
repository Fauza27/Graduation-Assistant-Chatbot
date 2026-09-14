"""
Intent classification for the academic Q&A system.

@deprecated
Catatan Arsitektur:
Modul ini merupakan komponen dari sistem intent-first versi terdahulu.
Pada arsitektur Retrieval-First aktif saat ini, intent classification di awal
sengaja ditiadakan (semua query masuk ke retrieval & reranker, lalu LLM akhir
yang menentukan respons berdasarkan relevansi dokumen). Modul ini dipertahankan
hanya sebagai referensi/utilitas dan tidak dipanggil dalam alur produksi utama.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import get_settings
from src.generation.memory import ConversationMemory, IntentType
from src.monitoring.openai_client import build_instrumented_http_client

TOPIC_SWITCH_SIGNALS = {
    "explicit": [
        "sekarang", "now", "bagaimana dengan", "how about", "kalau untuk", "what about", 
        "lalu untuk", "then for", "selanjutnya", "next", "ganti topik", "change topic", 
        "berbeda", "different", "lain", "other", "bukan", "not", "tapi", "but",
    ],
    "domain_keywords": {
        "non_skripsi": [
            "non skripsi",
            "non-skripsi",
            "tugas akhir non skripsi",
            "tugas akhir non-skripsi",
            "karya ilmiah",
            "profesional",
            "wirausaha",
        ],
        "skripsi": [
            "skripsi",
            "tugas akhir skripsi",
            "ta",
        ],
        "kkp": [
            "kkp",
            "kuliah kerja praktik",
            "kuliah kerja praktek",
            "magang",
            "internship",
            "praktik",
            "praktek",
        ],
        "pi": [
            "pi",
            "penulisan ilmiah",
            "penulisan imliah",
            "penelitian",
            "thesis",
        ],
    },
}

CLARIFICATION_SIGNALS = [
    "lebih detail", "more detail", "jelaskan lagi", "explain again", "elaborasi", 
    "elaborate", "contoh", "example", "maksudnya", "meaning", "mengapa", "why", 
    "kenapa", "bagaimana cara", "how to", "bisa dijelaskan", "can you explain", 
    "apa maksud", "what does it mean",
]

CONVERSATIONAL_PATTERNS = [
    "halo", "hai", "hello", "hi", "hey", "selamat pagi", "selamat siang", "selamat sore", 
    "selamat malam", "terima kasih", "makasih", "thanks", "thank you", "oke", "baik", 
    "siap", "mengerti", "paham", "sampai jumpa", "bye", "dadah",
]

QUESTION_KEYWORDS = [
    "apa", "bagaimana", "berapa", "kapan", "siapa", "kenapa", "mengapa", "dimana",
]

ASPECT_KEYWORDS = {
    "syarat": [ "syarat", "requirement", "persyaratan", "kondisi", "minimal", ], 
    "format": [ "format", "struktur", "template", "bentuk", "susunan", "penulisan", ], 
    "durasi": [ "durasi", "lama", "waktu", "periode", "jangka", ], 
    "prosedur": [ "prosedur", "tahap", "langkah", "proses", "cara", "tahapan", "alur", "pendaftaran", ], 
    "dosen": [ "dosen", "pembimbing", "supervisor", "penguji", ], 
    "tempat": [ "tempat", "lokasi", "instansi", "perusahaan", ], 
    "ujian": [ "ujian", "seminar", "sidang", "presentasi", ], 
    "laporan": [ "laporan", "bab", "halaman", "margin", "font", ], 
    "nilai": [ "nilai", "penilaian", "predikat", "skor", "lulus", "ipk", ], 
    "plagiarisme": [ "plagiarisme", "plagiat", "turnitin", "kemiripan", "orisinalitas", ], 
    "pustaka": [ "daftar pustaka", "referensi", "rujukan", "kutipan", "sitasi", "APA", ], 
    "administrasi": [ "formulir", "berkas", "administrasi", "lampiran", "surat", ],
}

CLASSIFIER_SYSTEM_PROMPT = """
Anda adalah classifier yang menganalisis pesan user
dalam sistem Q&A akademik STMIK Widya Cipta Dharma.

Terdapat 4 domain sistem:
- Kuliah Kerja Praktik (KKP)
- Penulisan Ilmiah (PI)
- Skripsi
- Tugas Akhir Non Skripsi

PENTING:
Perhatikan context switching dan topic switching dengan cermat.

Tentukan intent pesan user dan kembalikan HANYA JSON.

Tiga kategori intent:

1. "needs_retrieval"
   → Pertanyaan spesifik yang membutuhkan informasi dari dokumen pedoman.
   → Pertanyaan tentang topik BARU yang berbeda dari history.
   → Pertanyaan yang beralih domain.
   → Pertanyaan yang beralih aspek dalam domain yang sama.
   → Mengandung signal switching seperti:
     "sekarang", "bagaimana dengan", "kalau untuk", "lalu untuk".
   → Permintaan contoh format, lampiran, atau dokumen.

2. "conversational"
   → Sapaan, ucapan terima kasih, pertanyaan sangat umum.
   → Perintah yang tidak membutuhkan dokumen pedoman.

3. "clarification"
   → HANYA untuk elaborasi atau penjelasan lanjutan
     dari jawaban yang sama persis.
   → Pertanyaan yang jawabannya sudah ada di history.
   → BUKAN topic switching atau domain switching.

ATURAN KHUSUS:
- Jika ada signal switching → selalu "needs_retrieval".
- Jika beralih domain → selalu "needs_retrieval".
- Jika beralih aspek → selalu "needs_retrieval".
- Clarification hanya untuk elaborasi topik yang sama persis.

FORMAT OUTPUT WAJIB:
{
  "intent": "needs_retrieval" | "conversational" | "clarification",
  "reason": "alasan singkat dalam 1 kalimat",
  "confidence": 0.0,
  "topic_switch_detected": true,
  "domain_switch_detected": false
}
""".strip()

class SwitchType(Enum):
    """Jenis perpindahan konteks yang terdeteksi."""

    NONE = "none"
    TOPIC = "topic"
    DOMAIN = "domain"
    ASPECT = "aspect"


@dataclass(frozen=True)
class ClassificationResult:
    """Hasil klasifikasi intent."""

    intent: IntentType
    confidence: float
    reason: str
    switch_type: SwitchType = SwitchType.NONE
    switch_reason: str = ""


@dataclass(frozen=True)
class SwitchDetectionResult:
    """Hasil deteksi perpindahan topik/domain/aspek."""

    has_switch: bool
    switch_type: SwitchType
    reason: str

def contains_word(text: str, word: str) -> bool:
    """Check whether a complete word/phrase exists in text."""

    return (
        re.search(
            rf"\b{re.escape(word)}\b",
            text,
            re.IGNORECASE,
        )
        is not None
    )


def contains_any_word(text: str, words: list[str]) -> bool:
    """Check whether any complete word/phrase exists in text."""

    return any(contains_word(text, word) for word in words)

class SwitchDetector:
    """Detect topic, domain, and aspect switches."""

    @staticmethod
    def detect_explicit_switch(message: str) -> Optional[str]:
        """Detect explicit topic-switching signals."""

        message_lower = message.lower()

        for signal in TOPIC_SWITCH_SIGNALS["explicit"]:
            if contains_word(message_lower, signal):
                return signal

        return None

    @staticmethod
    def detect_domain_switch(
        message: str,
        memory: ConversationMemory,
    ) -> tuple[bool, str]:
        """Detect domain switching."""

        if not memory.has_prior_context:
            return False, "No prior context"

        current_domain = SwitchDetector._detect_domain(message)

        previous_text = " ".join(
            filter(
                None,
                [
                    memory.get_last_answer(),
                    memory.get_last_question(),
                ],
            )
        )

        previous_domain = SwitchDetector._detect_domain(previous_text)

        if (
            current_domain
            and previous_domain
            and current_domain != previous_domain
        ):
            return (
                True,
                f"Domain switch: {previous_domain} → {current_domain}",
            )

        return False, "No domain switch"

    @staticmethod
    def _detect_domain(text: str) -> Optional[str]:
        """Detect the most likely academic domain."""

        text_lower = text.lower()
        domain_keywords = TOPIC_SWITCH_SIGNALS["domain_keywords"]

        # 1. Non-skripsi first
        non_skripsi_keywords = domain_keywords.get("non_skripsi", [])
        if contains_any_word(text_lower, non_skripsi_keywords):
            return "non_skripsi"

        # 2. Skripsi (after stripping non-skripsi phrases to prevent partial false matches)
        cleaned_skripsi = text_lower
        for kw in non_skripsi_keywords:
            cleaned_skripsi = cleaned_skripsi.replace(kw, " ")

        skripsi_keywords = domain_keywords.get("skripsi", [])
        if contains_any_word(cleaned_skripsi, skripsi_keywords):
            return "skripsi"

        # 3. KKP
        kkp_keywords = domain_keywords.get("kkp", [])
        if contains_any_word(text_lower, kkp_keywords):
            return "kkp"

        # 4. PI
        pi_keywords = domain_keywords.get("pi", [])
        if contains_any_word(text_lower, pi_keywords):
            return "pi"

        return None

    @staticmethod
    def detect_aspect_switch(
        message: str,
        memory: ConversationMemory,
    ) -> tuple[bool, str]:
        """Detect aspect switching within the same domain."""

        if not memory.has_prior_context:
            return False, "No prior context"

        current_aspect = SwitchDetector._detect_aspect(message)
        previous_question = memory.get_last_question() or ""
        previous_aspect = SwitchDetector._detect_aspect(
            previous_question
        )

        if (
            current_aspect
            and previous_aspect
            and current_aspect != previous_aspect
        ):
            last_answer = memory.get_last_answer() or ""

            if not contains_any_word(
                last_answer.lower(),
                ASPECT_KEYWORDS.get(current_aspect, []),
            ):
                return (
                    True,
                    f"Aspect switch: "
                    f"{previous_aspect} → {current_aspect}",
                )

        return False, "No aspect switch"

    @staticmethod
    def _detect_aspect(text: str) -> Optional[str]:
        """Detect the most likely aspect."""

        text_lower = text.lower()

        for aspect, keywords in ASPECT_KEYWORDS.items():
            if contains_any_word(text_lower, keywords):
                return aspect

        return None

    def detect_switch(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> SwitchDetectionResult:
        """Detect the first applicable switch."""

        explicit_signal = self.detect_explicit_switch(message)

        if explicit_signal:
            return SwitchDetectionResult(
                has_switch=True,
                switch_type=SwitchType.TOPIC,
                reason=f"Explicit switch signal: {explicit_signal}",
            )

        domain_switch, domain_reason = self.detect_domain_switch(
            message,
            memory,
        )

        if domain_switch:
            return SwitchDetectionResult(
                has_switch=True,
                switch_type=SwitchType.DOMAIN,
                reason=domain_reason,
            )

        aspect_switch, aspect_reason = self.detect_aspect_switch(
            message,
            memory,
        )

        if aspect_switch:
            return SwitchDetectionResult(
                has_switch=True,
                switch_type=SwitchType.ASPECT,
                reason=aspect_reason,
            )

        return SwitchDetectionResult(
            has_switch=False,
            switch_type=SwitchType.NONE,
            reason="No switch detected",
        )


class ClarificationDetector:
    """Detect true clarification requests."""

    @staticmethod
    def detect_signal(message: str) -> Optional[str]:
        """Detect clarification signal."""

        message_lower = message.lower()

        for signal in CLARIFICATION_SIGNALS:
            if contains_word(message_lower, signal):
                return signal

        return None

    def is_true_clarification(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> tuple[bool, str]:
        """Determine whether a message is a true clarification."""

        if not memory.has_prior_context:
            return False, "No prior context for clarification"

        signal = self.detect_signal(message)

        if not signal:
            return False, "No clarification signals found"

        switch_result = SwitchDetector().detect_switch(
            message,
            memory,
        )

        if switch_result.has_switch:
            return (
                False,
                f"Switch detected: {switch_result.reason}",
            )

        return (
            True,
            f"True clarification signal: {signal}",
        )


class ConversationalDetector:
    """Detect conversational messages that do not require retrieval."""

    @staticmethod
    def is_short_message(message: str) -> bool:
        """Return True for very short messages."""

        return len(message.strip()) <= 9

    @staticmethod
    def has_question_keywords(message: str) -> bool:
        """Return True when question keywords are present."""

        return contains_any_word(
            message.lower(),
            QUESTION_KEYWORDS,
        )

    @staticmethod
    def matches_pattern(message: str) -> Optional[str]:
        """Return the matching conversational pattern."""

        message_lower = message.lower()

        for pattern in CONVERSATIONAL_PATTERNS:
            if contains_word(message_lower, pattern):
                return pattern

        return None

    def is_conversational(
        self,
        message: str,
    ) -> tuple[bool, str]:
        """Determine whether the message is conversational."""

        if (
            self.is_short_message(message)
            and not self.has_question_keywords(message)
        ):
            return True, "Message too short for retrieval"

        pattern = self.matches_pattern(message)

        if (
            pattern
            and not self.has_question_keywords(message)
        ):
            return (
                True,
                f"Conversational pattern: {pattern}",
            )

        return False, "Not conversational"


@lru_cache(maxsize=1)
def _get_default_llm() -> ChatOpenAI:
    """Create and cache the default LLM client."""

    settings = get_settings()

    return ChatOpenAI(
        model=settings.llm_model,
        http_client=build_instrumented_http_client(),
        temperature=0,
        api_key=settings.open_api_key,
        max_tokens=200,
    )

def _create_cache_key(
    message: str,
    memory: ConversationMemory,
) -> str:
    """
    Create a context-aware cache key.

    Turn count alone is insufficient because two conversations can have
    the same number of turns but completely different context.
    """

    context = "\n".join(
        [
            message,
            str(memory.turn_count),
            memory.get_last_question() or "",
            memory.get_last_answer() or "",
        ]
    )

    digest = hashlib.md5(
        context.encode("utf-8")
    ).hexdigest()

    return digest


def _build_classifier_prompt(
    current_message: str,
    memory: ConversationMemory,
) -> str:
    """Build prompt for LLM classification."""

    parts: list[str] = []

    last_question = memory.get_last_question()
    last_answer = memory.get_last_answer()

    if last_question and last_answer:
        question_preview = (
            last_question[:150] + "..."
            if len(last_question) > 150
            else last_question
        )

        answer_preview = (
            last_answer[:200] + "..."
            if len(last_answer) > 200
            else last_answer
        )

        parts.extend(
            [
                "=== PERCAKAPAN TERAKHIR ===",
                f"User sebelumnya: {question_preview}",
                f"Asisten menjawab: {answer_preview}",
                "",
            ]
        )

    parts.extend(
        [
            "=== PESAN USER SEKARANG ===",
            current_message,
            "",
            "Tentukan intent pesan user sekarang.",
            "Output hanya JSON.",
        ]
    )

    return "\n".join(parts)


class IntentClassifier:
    """
    Hybrid intent classifier.

    Urutan:
        1. Conversational rules
        2. First-turn rule
        3. Topic/domain/aspect switch
        4. Clarification rule
        5. LLM fallback
    """

    def __init__(self) -> None:
        self._llm = _get_default_llm()

        self._cache: dict[str, IntentType] = {}
        self._cache_max_size = 1000

        self._switch_detector = SwitchDetector()
        self._clarification_detector = ClarificationDetector()
        self._conversational_detector = ConversationalDetector()

    def classify(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> Tuple[IntentType, float, str]:
        """Classify a user message."""

        is_conversational, reason = (
            self._conversational_detector.is_conversational(
                message
            )
        )

        if is_conversational:
            logger.debug(
                "Shortcut → CONVERSATIONAL: {}",
                reason,
            )
            return (
                IntentType.CONVERSATIONAL,
                0.95,
                reason,
            )

        if not memory.has_prior_context:
            logger.debug(
                "Shortcut → NEEDS_RETRIEVAL "
                "(no prior context)"
            )
            return (
                IntentType.NEEDS_RETRIEVAL,
                0.99,
                "First question needs retrieval",
            )

        switch_result = self._switch_detector.detect_switch(
            message,
            memory,
        )

        if switch_result.has_switch:
            logger.info(
                "Switch detected → NEEDS_RETRIEVAL: {}",
                switch_result.reason,
            )

            return (
                IntentType.NEEDS_RETRIEVAL,
                0.95,
                switch_result.reason,
            )

        is_clarification, reason = (
            self._clarification_detector.is_true_clarification(
                message,
                memory,
            )
        )

        if is_clarification:
            logger.info(
                "Clarification detected → CLARIFICATION: {}",
                reason,
            )

            return (
                IntentType.CLARIFICATION,
                0.90,
                reason,
            )

        return self._classify_with_llm(
            message,
            memory,
        )

    def _classify_with_llm(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> Tuple[IntentType, float, str]:
        """Classify complex cases using the LLM."""

        cache_key = _create_cache_key(
            message,
            memory,
        )

        cached_intent = self._cache.get(cache_key)

        if cached_intent is not None:
            logger.debug(
                "Cache hit → {}",
                cached_intent.value,
            )

            return (
                cached_intent,
                0.90,
                "From cache",
            )

        self._evict_cache_if_needed()

        prompt = _build_classifier_prompt(
            message,
            memory,
        )

        try:
            response = self._llm.invoke(
                [
                    SystemMessage(
                        content=CLASSIFIER_SYSTEM_PROMPT
                    ),
                    HumanMessage(content=prompt),
                ]
            )

            raw = response.content.strip()

            if raw.startswith("```"):
                raw = re.sub(
                    r"^```(?:json)?\s*",
                    "",
                    raw,
                    flags=re.IGNORECASE,
                )
                raw = re.sub(
                    r"\s*```$",
                    "",
                    raw,
                )

            parsed = json.loads(raw)

            intent_str = parsed.get(
                "intent",
                IntentType.NEEDS_RETRIEVAL.value,
            )

            confidence = float(
                parsed.get("confidence", 0.80)
            )

            reason = str(
                parsed.get("reason", "")
            )

            try:
                intent = IntentType(intent_str)
            except ValueError:
                logger.warning(
                    "Unknown intent '{}'; "
                    "fallback to NEEDS_RETRIEVAL",
                    intent_str,
                )
                intent = IntentType.NEEDS_RETRIEVAL

            self._cache[cache_key] = intent

            logger.info(
                "Intent: {} | confidence={:.2f} | {}",
                intent.value,
                confidence,
                reason,
            )

            return (
                intent,
                confidence,
                reason,
            )

        except Exception as exc:
            logger.warning(
                "Classifier error: {} → "
                "fallback NEEDS_RETRIEVAL",
                exc,
            )

            return (
                IntentType.NEEDS_RETRIEVAL,
                0.50,
                f"Fallback due to error: {exc}",
            )

    def _evict_cache_if_needed(self) -> None:
        """Prevent unbounded classifier cache growth."""

        if len(self._cache) < self._cache_max_size:
            return

        remove_count = self._cache_max_size // 2

        for key in list(self._cache.keys())[:remove_count]:
            del self._cache[key]


@lru_cache(maxsize=1)
def get_intent_classifier() -> IntentClassifier:
    """Return the shared classifier instance."""

    return IntentClassifier()