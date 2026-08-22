"""
Kalkulasi cost dari token usage, berdasarkan config/pricing.yaml.

Pola loading sama seperti `_load_section_keywords` di
src/retrieval/self_query.py — load sekali saat import, cache di module level.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PRICING_PATH = _PROJECT_ROOT / "config" / "pricing.yaml"


def _load_pricing(path: Path = _PRICING_PATH) -> dict:
    if not path.exists():
        logger.error(f"Pricing file tidak ditemukan: {path}. Cost akan selalu 0.")
        return {"llm": {}, "embedding": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


_PRICING = _load_pricing()


def calculate_llm_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    """Hitung cost generation LLM dalam USD. Return 0.0 kalau model tidak ada di pricing.yaml."""
    pricing = _PRICING.get("llm", {}).get(model)
    if not pricing or input_tokens is None or output_tokens is None:
        if not pricing:
            logger.warning(f"[pricing] Model '{model}' tidak ada di config/pricing.yaml, cost dihitung 0.")
        return 0.0
    cost = (input_tokens / 1_000_000 * pricing.get("input_per_1m", 0)) + (
        output_tokens / 1_000_000 * pricing.get("output_per_1m", 0)
    )
    return round(cost, 6)


def calculate_embedding_cost(model: str, tokens: int | None) -> float:
    """Hitung cost embedding dalam USD. Embedding cuma charge input tokens."""
    pricing = _PRICING.get("embedding", {}).get(model)
    if not pricing or tokens is None:
        if not pricing:
            logger.warning(f"[pricing] Model embedding '{model}' tidak ada di config/pricing.yaml, cost dihitung 0.")
        return 0.0
    cost = tokens / 1_000_000 * pricing.get("input_per_1m", 0)
    return round(cost, 6)