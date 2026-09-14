"""
Kalkulasi cost dari token usage, berdasarkan config/pricing.yaml.

Pola loading sama seperti `_load_section_keywords` di
src/retrieval/self_query.py — load sekali saat import, cache di module level.

Kegagalan membaca/parsing config TIDAK boleh menyebabkan aplikasi crash.
Dalam kondisi config tidak tersedia/invalid, cost dihitung sebagai 0.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PRICING_PATH = _PROJECT_ROOT / "config" / "pricing.yaml"

_EMPTY_PRICING: dict[str, dict[str, Any]] = {
    "llm": {},
    "embedding": {},
}


def _load_pricing(
    path: Path = _PRICING_PATH,
) -> dict[str, dict[str, Any]]:
    """
    Load pricing config dari YAML.

    Fungsi ini selalu mengembalikan mapping yang aman dipakai dan tidak
    melempar exception, karena dipanggil saat import time.
    """
    if not path.exists():
        logger.error(
            f"Pricing file tidak ditemukan: {path}. "
            "Cost akan selalu 0."
        )
        return _EMPTY_PRICING.copy()

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

    except yaml.YAMLError as exc:
        logger.error(
            f"Gagal mem-parse pricing file {path}: {exc}. "
            "Cost akan selalu 0 — periksa sintaks pricing.yaml."
        )
        return _EMPTY_PRICING.copy()

    except OSError as exc:
        logger.error(
            f"Gagal membaca pricing file {path}: {exc}. "
            "Cost akan selalu 0."
        )
        return _EMPTY_PRICING.copy()

    if not isinstance(data, dict):
        logger.error(
            f"Format pricing file tidak valid (bukan mapping): {path}. "
            "Cost akan selalu 0."
        )
        return _EMPTY_PRICING.copy()

    # Pastikan top-level section yang dibutuhkan selalu tersedia.
    llm = data.get("llm", {})
    embedding = data.get("embedding", {})

    if not isinstance(llm, dict):
        logger.error(
            f"Section 'llm' pada {path} tidak valid. "
            "Menggunakan empty pricing."
        )
        llm = {}

    if not isinstance(embedding, dict):
        logger.error(
            f"Section 'embedding' pada {path} tidak valid. "
            "Menggunakan empty pricing."
        )
        embedding = {}

    return {
        "llm": llm,
        "embedding": embedding,
    }


_PRICING = _load_pricing()


def calculate_llm_cost(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float:
    """
    Hitung cost generation LLM dalam USD.

    Return 0.0 jika:
    - model tidak ada di pricing.yaml;
    - token usage tidak tersedia.
    """
    pricing = _PRICING["llm"].get(model)

    if not pricing:
        logger.warning(
            f"[pricing] Model '{model}' tidak ada di "
            "config/pricing.yaml, cost dihitung 0."
        )
        return 0.0

    if input_tokens is None or output_tokens is None:
        return 0.0

    if not isinstance(pricing, dict):
        logger.warning(
            f"[pricing] Konfigurasi model '{model}' tidak valid, "
            "cost dihitung 0."
        )
        return 0.0

    input_per_1m = pricing.get("input_per_1m", 0)
    output_per_1m = pricing.get("output_per_1m", 0)

    if not isinstance(input_per_1m, (int, float)):
        logger.warning(
            f"[pricing] input_per_1m untuk model '{model}' tidak valid."
        )
        input_per_1m = 0

    if not isinstance(output_per_1m, (int, float)):
        logger.warning(
            f"[pricing] output_per_1m untuk model '{model}' tidak valid."
        )
        output_per_1m = 0

    cost = (
        input_tokens / 1_000_000 * input_per_1m
        + output_tokens / 1_000_000 * output_per_1m
    )

    return round(cost, 6)


def calculate_embedding_cost(
    model: str,
    tokens: int | None,
) -> float:
    """
    Hitung cost embedding dalam USD.

    Embedding hanya dikenakan charge input tokens.
    """
    pricing = _PRICING["embedding"].get(model)

    if not pricing:
        logger.warning(
            f"[pricing] Model embedding '{model}' tidak ada di "
            "config/pricing.yaml, cost dihitung 0."
        )
        return 0.0

    if tokens is None:
        return 0.0

    if not isinstance(pricing, dict):
        logger.warning(
            f"[pricing] Konfigurasi embedding model '{model}' "
            "tidak valid, cost dihitung 0."
        )
        return 0.0

    input_per_1m = pricing.get("input_per_1m", 0)

    if not isinstance(input_per_1m, (int, float)):
        logger.warning(
            f"[pricing] input_per_1m untuk embedding model "
            f"'{model}' tidak valid."
        )
        return 0.0

    cost = tokens / 1_000_000 * input_per_1m

    return round(cost, 6)