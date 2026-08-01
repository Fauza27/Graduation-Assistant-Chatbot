"""Detection utilities for intent classification."""

from typing import Tuple, Optional
from loguru import logger

from src.generation.memory import ConversationMemory
from .constants import (
    TOPIC_SWITCH_SIGNALS, CLARIFICATION_SIGNALS, CONVERSATIONAL_PATTERNS,
    QUESTION_KEYWORDS, ASPECT_KEYWORDS
)
from .models import SwitchDetectionResult, SwitchType


class SwitchDetector:
    """Detects topic and domain switches in conversation."""
    
    @staticmethod
    def detect_explicit_switch(message: str) -> Optional[str]:
        """Detect explicit switching signals."""
        message_lower = message.lower()
        for signal in TOPIC_SWITCH_SIGNALS["explicit"]:
            if signal in message_lower:
                return signal
        return None
    
    @staticmethod
    def detect_domain_switch(message: str, memory: ConversationMemory) -> Tuple[bool, str]:
        """Detect domain switching (PI ↔ KKP)."""
        if not memory.has_prior_context:
            return False, "No prior context"
        
        message_lower = message.lower()
        
        # Detect current domain
        current_domain = None
        for domain, keywords in TOPIC_SWITCH_SIGNALS["domain_keywords"].items():
            if any(keyword in message_lower for keyword in keywords):
                current_domain = domain
                break
        
        # Detect previous domain
        last_answer = memory.get_last_answer() or ""
        previous_question = memory.get_previous_question() or ""
        previous_context = (last_answer + " " + previous_question).lower()
        
        previous_domain = None
        for domain, keywords in TOPIC_SWITCH_SIGNALS["domain_keywords"].items():
            if any(keyword in previous_context for keyword in keywords):
                previous_domain = domain
                break
        
        if current_domain and previous_domain and current_domain != previous_domain:
            return True, f"Domain switch: {previous_domain} → {current_domain}"
        
        return False, "No domain switch"
    
    @staticmethod
    def detect_aspect_switch(message: str, memory: ConversationMemory) -> Tuple[bool, str]:
        """Detect aspect switching within same domain."""
        if not memory.has_prior_context:
            return False, "No prior context"
        
        message_lower = message.lower()
        previous_question = memory.get_previous_question() or ""
        prev_q_lower = previous_question.lower()
        
        # Detect current aspect
        current_aspect = None
        for aspect, keywords in ASPECT_KEYWORDS.items():
            if any(keyword in message_lower for keyword in keywords):
                current_aspect = aspect
                break
        
        # Detect previous aspect
        previous_aspect = None
        for aspect, keywords in ASPECT_KEYWORDS.items():
            if any(keyword in prev_q_lower for keyword in keywords):
                previous_aspect = aspect
                break
        
        if current_aspect and previous_aspect and current_aspect != previous_aspect:
            # Check if current aspect is already covered in last answer
            last_answer = memory.get_last_answer() or ""
            last_answer_lower = last_answer.lower()
            
            current_aspect_in_answer = any(
                keyword in last_answer_lower 
                for keyword in ASPECT_KEYWORDS.get(current_aspect, [])
            )
            
            if not current_aspect_in_answer:
                return True, f"Aspect switch: {previous_aspect} → {current_aspect}"
        
        return False, "No aspect switch"
    
    def detect_switch(self, message: str, memory: ConversationMemory) -> SwitchDetectionResult:
        """Main switch detection method."""
        # Check explicit signals first
        explicit_signal = self.detect_explicit_switch(message)
        if explicit_signal:
            return SwitchDetectionResult(
                has_switch=True,
                switch_type=SwitchType.TOPIC,
                reason=f"Explicit switch signal: {explicit_signal}"
            )
        
        # Check domain switch
        domain_switch, domain_reason = self.detect_domain_switch(message, memory)
        if domain_switch:
            return SwitchDetectionResult(
                has_switch=True,
                switch_type=SwitchType.DOMAIN,
                reason=domain_reason
            )
        
        # Check aspect switch
        aspect_switch, aspect_reason = self.detect_aspect_switch(message, memory)
        if aspect_switch:
            return SwitchDetectionResult(
                has_switch=True,
                switch_type=SwitchType.ASPECT,
                reason=aspect_reason
            )
        
        return SwitchDetectionResult(
            has_switch=False,
            switch_type=SwitchType.NONE,
            reason="No switch detected"
        )


class ClarificationDetector:
    """Detects true clarification requests."""
    
    @staticmethod
    def detect_clarification_signals(message: str) -> Optional[str]:
        """Detect clarification signals in message."""
        message_lower = message.lower()
        for signal in CLARIFICATION_SIGNALS:
            if signal in message_lower:
                return signal
        return None
    
    def is_true_clarification(self, message: str, memory: ConversationMemory) -> Tuple[bool, str]:
        """Check if message is a true clarification request."""
        if not memory.has_prior_context:
            return False, "No prior context for clarification"
        
        # Check for clarification signals
        clarification_signal = self.detect_clarification_signals(message)
        if not clarification_signal:
            return False, "No clarification signals found"
        
        # Ensure no topic/domain switch
        switch_detector = SwitchDetector()
        switch_result = switch_detector.detect_switch(message, memory)
        
        if switch_result.has_switch:
            return False, f"Switch detected: {switch_result.reason}"
        
        return True, f"True clarification signal: {clarification_signal}"


class ConversationalDetector:
    """Detects conversational messages."""
    
    @staticmethod
    def is_short_message(message: str) -> bool:
        """Check if message is too short to need retrieval."""
        return len(message.strip()) <= 9
    
    @staticmethod
    def has_question_keywords(message: str) -> bool:
        """Check if message contains question keywords."""
        message_lower = message.lower()
        return any(kw in message_lower for kw in QUESTION_KEYWORDS)
    
    @staticmethod
    def matches_conversational_pattern(message: str) -> Optional[str]:
        """Check if message matches conversational patterns."""
        message_lower = message.lower()
        for pattern in CONVERSATIONAL_PATTERNS:
            if pattern in message_lower:
                return pattern
        return None
    
    def is_conversational(self, message: str) -> Tuple[bool, str]:
        """Check if message is conversational."""
        # Very short messages without question keywords
        if self.is_short_message(message) and not self.has_question_keywords(message):
            return True, "Message too short for retrieval"
        
        # Conversational patterns without question keywords
        pattern = self.matches_conversational_pattern(message)
        if pattern and not self.has_question_keywords(message):
            return True, f"Conversational pattern: {pattern}"
        
        return False, "Not conversational"