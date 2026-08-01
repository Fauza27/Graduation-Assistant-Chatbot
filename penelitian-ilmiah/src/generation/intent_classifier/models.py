"""Data models for intent classification."""

from dataclasses import dataclass
from enum import Enum
from src.generation.memory import IntentType


class SwitchType(Enum):
    NONE = "none"
    TOPIC = "topic"
    DOMAIN = "domain"
    ASPECT = "aspect"


@dataclass
class ClassificationResult:
    intent: IntentType
    confidence: float
    reason: str
    switch_type: SwitchType = SwitchType.NONE
    switch_reason: str = ""


@dataclass
class SwitchDetectionResult:
    has_switch: bool
    switch_type: SwitchType
    reason: str