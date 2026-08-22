"""Main intent classifier implementation."""

import json
from typing import Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import get_settings
from src.generation.memory import ConversationMemory, IntentType
from .constants import CLASSIFIER_SYSTEM_PROMPT
from .detectors import SwitchDetector, ClarificationDetector, ConversationalDetector


def _build_classifier_prompt(
    current_message: str,
    memory: ConversationMemory,
) -> str:
    """Build prompt for LLM classification."""
    parts = []
 
    if not memory.is_empty:
        last_q = memory.get_last_question()
        last_a = memory.get_last_answer()
 
        if last_q and last_a:
            q_short = last_q[:150] + "..." if len(last_q) > 150 else last_q
            a_short = last_a[:200] + "..." if len(last_a) > 200 else last_a
 
            parts.append("=== PERCAKAPAN TERAKHIR ===")
            parts.append(f"User sebelumnya: {q_short}")
            parts.append(f"Asisten menjawab: {a_short}")
            parts.append("")
 
    parts.append(f"=== PESAN USER SEKARANG ===")
    parts.append(current_message)
    parts.append("")
    parts.append("Tentukan intent pesan user sekarang. Output hanya JSON.")
 
    return "\n".join(parts)


class IntentClassifier:
    """Main intent classifier using rule-based and LLM approaches."""
 
    def __init__(self):
        settings = get_settings()
        from src.monitoring.openai_client import build_instrumented_http_client
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            http_client=build_instrumented_http_client(),
            temperature=0,
            api_key=settings.open_api_key,  
            max_tokens=200,
        )
        self._cache: dict[str, IntentType] = {}
        
        # Initialize detectors
        self._switch_detector = SwitchDetector()
        self._clarification_detector = ClarificationDetector()
        self._conversational_detector = ConversationalDetector()
 
    def classify(
        self,
        message: str,
        memory: ConversationMemory,
    ) -> Tuple[IntentType, float, str]:
        """Classify user message intent."""
        
        # Quick conversational check
        is_conv, conv_reason = self._conversational_detector.is_conversational(message)
        if is_conv:
            logger.debug(f"Shortcut → CONVERSATIONAL: {conv_reason}")
            return IntentType.CONVERSATIONAL, 0.95, conv_reason
        
        # First question always needs retrieval
        if not memory.has_prior_context:
            logger.debug("Shortcut → NEEDS_RETRIEVAL (no prior context)")
            return IntentType.NEEDS_RETRIEVAL, 0.99, "First question needs retrieval"
        
        # Detect switches
        switch_result = self._switch_detector.detect_switch(message, memory)
        
        if switch_result.has_switch:
            logger.info(f"🔄 Switch detected → NEEDS_RETRIEVAL: {switch_result.reason}")
            return IntentType.NEEDS_RETRIEVAL, 0.95, switch_result.reason
        
        # Check for clarification
        is_clarif, clarif_reason = self._clarification_detector.is_true_clarification(message, memory)
        
        if is_clarif:
            logger.info(f"💬 Clarification detected → CLARIFICATION: {clarif_reason}")
            return IntentType.CLARIFICATION, 0.90, clarif_reason
        
        # Use LLM for complex cases
        return self._classify_with_llm(message, memory)
    
    def _classify_with_llm(
        self, 
        message: str, 
        memory: ConversationMemory,
    ) -> Tuple[IntentType, float, str]:
        """Use LLM for classification when rules are insufficient."""
        
        cache_key = f"{message[:50]}|{memory.turn_count}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.debug(f"Cache hit → {cached.value}")
            return cached, 0.9, "From cache"
 
        prompt = _build_classifier_prompt(message, memory)
 
        try:
            response = self._llm.invoke([
                SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
 
            raw = response.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
 
            parsed = json.loads(raw)
 
            intent_str = parsed.get("intent", "needs_retrieval")
            confidence = float(parsed.get("confidence", 0.8))
            reason = parsed.get("reason", "")
 
            try:
                intent = IntentType(intent_str)
            except ValueError:
                logger.warning(f"Unknown intent '{intent_str}', fallback to NEEDS_RETRIEVAL")
                intent = IntentType.NEEDS_RETRIEVAL
 
            self._cache[cache_key] = intent
 
            logger.info(f"🎯 Intent: {intent.value} (conf: {confidence:.2f}) | {reason}")
 
            return intent, confidence, reason
 
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning(f"Classifier error: {e} → fallback NEEDS_RETRIEVAL")
            return IntentType.NEEDS_RETRIEVAL, 0.5, f"Fallback due to error: {e}"