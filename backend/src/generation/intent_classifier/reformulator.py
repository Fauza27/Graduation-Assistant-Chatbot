"""Query processing and reformulation utilities."""

import re
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import get_settings
from src.generation.memory import ConversationMemory
from .constants import IMPLICIT_REFERENCE_SIGNALS, REFORMULATION_PROMPT

def normalize_query(query: str) -> str:
    """Normalize common academic acronyms using regex."""
    # KKP aliases
    query = re.sub(r"(?i)\bkp\b|\bk\.p\.\b|\bmagang\b", "KKP", query)
    # PI aliases
    query = re.sub(r"(?i)\bpi\b|\bp\.i\.\b", "Penulisan Ilmiah", query)
    
    # Aggressive Regex Rule: "apa itu X" -> "Apa yang dimaksud dengan X?"
    query = re.sub(r"(?i)^apa\s+itu\s+(.+)", r"Apa yang dimaksud dengan \1", query)
    
    # Remove extra spaces
    return re.sub(r"\s+", " ", query).strip()

def needs_rewrite(query: str) -> bool:
    """Check if query contains implicit references that require history context."""
    query_lower = query.lower()
    
    # Exclude explicitly self-contained phrases like "apa itu kkp"
    if "apa itu" in query_lower or "siapa itu" in query_lower:
        if len(query_lower.split()) > 2:
            # Contains an object, so it's not an implicit reference (e.g. "apa itu kkp")
            query_lower = query_lower.replace("apa itu", "").replace("siapa itu", "")
            
    # Use word boundaries for exact matching to prevent substring bugs ("itu" matching inside a word)
    for ref in IMPLICIT_REFERENCE_SIGNALS:
        if re.search(r"\b" + re.escape(ref) + r"\b", query_lower):
            return True
            
    return False

class QueryReformulator:
    """Processes and reformulates queries based on rules and LLM."""
    
    def __init__(self, llm: ChatOpenAI = None):
        if llm is None:
            settings = get_settings()
            from src.monitoring.openai_client import build_instrumented_http_client
            self._llm = ChatOpenAI(
                model=settings.llm_model,
                http_client=build_instrumented_http_client(),
                temperature=0,
                api_key=settings.open_api_key,  
                max_tokens=100,
            )
        else:
            self._llm = llm
            
    def _extract_last_topic(self, memory: ConversationMemory) -> str | None:
        """Extract the last discussed academic domain from history."""
        # Look backwards to find the most recent topic
        for turn in reversed(memory._turns):
            content = turn.content.lower()
            if "penulisan ilmiah" in content or " pi " in content or content.startswith("pi ") or content.endswith(" pi"): 
                return "Penulisan Ilmiah"
            if "kkp" in content or "kuliah kerja praktik" in content: 
                return "KKP"
        return None

    def _apply_rule_rewrite(self, message: str, last_topic: str) -> str | None:
        """Apply simple rule-based rewrites if possible."""
        message_lower = message.lower()
        
        # Rule 1: Questions starting with "kalau", "bagaimana dengan", "terus"
        if message_lower.startswith("kalau") or message_lower.startswith("bagaimana dengan") or message_lower.startswith("terus"):
            # Ensure it doesn't already contain the topic
            if last_topic.lower() not in message_lower:
                return f"{message} untuk {last_topic}?"
                
        # Rule 2: Implicit suffixes like "syaratnya", "durasinya", "formatnya"
        if "nya" in message_lower:
            words = message.split()
            rewritten_words = []
            applied = False
            for w in words:
                if w.lower() in ["syaratnya", "syaratnya?", "durasinya", "durasinya?", "formatnya", "formatnya?"]:
                    # Replace "nya" with " {last_topic}"
                    w = w.replace("nya", f" {last_topic}")
                    applied = True
                rewritten_words.append(w)
            
            if applied:
                return " ".join(rewritten_words)
                
        # Rule 3: "itu" reference
        if " itu" in message_lower:
            if last_topic.lower() not in message_lower:
                return message_lower.replace(" itu", f" {last_topic}")
                
        return None

    def reformulate_query(self, message: str, memory: ConversationMemory) -> tuple[str, str]:
        """
        Reformulate query to be self-contained.
        Returns: (resolved_query, rewrite_method)
        where rewrite_method in ["None", "Rule", "LLM"]
        """
        if memory.is_empty:
            return message, "None"
        
        # Rule-based Rewrite Attempt
        last_topic = self._extract_last_topic(memory)
        if last_topic:
            rule_rewritten = self._apply_rule_rewrite(message, last_topic)
            if rule_rewritten:
                logger.info(f"🔄 [Rewrite] Rule: '{message}' → '{rule_rewritten}'")
                return rule_rewritten, "Rule"
        
        # Fallback to LLM Rewrite
        history_text = memory.get_conversation_summary()
        prompt = REFORMULATION_PROMPT.format(
            history=history_text,
            question=message,
        )
        
        try:
            response = self._llm.invoke([HumanMessage(content=prompt)])
            reformulated = response.content.strip()
            
            if reformulated and reformulated != message:
                logger.info(f"🔄 [Rewrite] LLM: '{message}' → '{reformulated}'")
                return reformulated, "LLM"
            
            return message, "LLM"
        
        except Exception as e:
            logger.warning(f"LLM Reformulation failed: {e} → using original query")
            return message, "None"

# Backward compatibility (or just alias)
def reformulate_query(
    message: str,
    memory: ConversationMemory,
    llm: ChatOpenAI | None = None,
) -> tuple[str, str]:
    reformulator = QueryReformulator(llm)
    return reformulator.reformulate_query(message, memory)