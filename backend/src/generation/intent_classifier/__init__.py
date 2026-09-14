"""Intent classification module."""

from .classifier import (
    IntentClassifier,
    ClassificationResult,
    SwitchDetectionResult,
    SwitchType,
)
from .reformulator import QueryReformulator, reformulate_query, normalize_query, needs_rewrite

__all__ = [
    "IntentClassifier",
    "QueryReformulator",
    "reformulate_query",
    "normalize_query",
    "needs_rewrite",
    "ClassificationResult",
    "SwitchDetectionResult",
    "SwitchType",
]
