"""Replay real scores to check evidence delivery, not generated-answer accuracy."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.retrieval.pipeline import _select_reranked_documents


CASES = json.loads(
    (Path(__file__).parent / "fixtures/chatbot_gate_regressions.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[case["question"] for case in CASES])
def test_historical_supported_evidence_survives_negative_scores(case):
    settings = SimpleNamespace(
        rerank_min_top_score=None, rerank_relative_gap=2.5, rerank_top_n=5,
    )
    candidates = [dict(row) for row in case["candidates"]]
    selected, _, _ = _select_reranked_documents(candidates, settings)
    assert case["expected_parent_id"] in {row["parent_id"] for row in selected}
    settings.rerank_min_top_score = 0.0
    assert _select_reranked_documents(candidates, settings)[0] == []
