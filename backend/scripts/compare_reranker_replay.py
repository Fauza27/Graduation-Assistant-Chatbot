"""Summarize a manually reviewed, paired reranker replay.

The grading file contains only deviations from the default grade ("benar").
This script validates question alignment before comparing quality and runtime.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median


GRADE_SCORE = {"salah": 0, "sebagian": 1, "benar": 2}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], percent: float) -> float:
    sorted_values = sorted(values)
    position = (len(sorted_values) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (position - lower) * (
        sorted_values[upper] - sorted_values[lower]
    )


def summarize_runtime(interactions: list[dict]) -> dict:
    latency = [float(item["elapsed_seconds"]) for item in interactions]
    reranking = [
        float(item["metrics"].get("stage_reranking_ms") or 0) / 1000
        for item in interactions
    ]
    return {
        "mean_seconds": round(mean(latency), 3),
        "median_seconds": round(median(latency), 3),
        "p95_seconds": round(percentile(latency, 0.95), 3),
        "median_reranking_seconds": round(median(reranking), 3),
        "input_tokens": sum(item["usage"]["input_tokens"] for item in interactions),
        "output_tokens": sum(item["usage"]["output_tokens"] for item in interactions),
        "llm_cost_usd": round(
            sum(float(item["metrics"].get("llm_cost_usd") or 0) for item in interactions),
            6,
        ),
        "embedding_cost_usd": round(
            sum(float(item["metrics"].get("embedding_cost_usd") or 0) for item in interactions),
            6,
        ),
    }


def compare(on: dict, off: dict, review: dict) -> dict:
    assert on["reranker_enabled"] is True and off["reranker_enabled"] is False
    assert on["question_file_sha256"] == off["question_file_sha256"]
    assert len(on["sessions"]) == len(off["sessions"]) == 20
    assert review["reviewed_sessions"] == list(range(1, 21))

    all_on, all_off, grades = [], [], []
    for session_index, (on_session, off_session) in enumerate(
        zip(on["sessions"], off["sessions"], strict=True), start=1
    ):
        assert on_session["name"] == off_session["name"]
        for on_item, off_item in zip(
            on_session["interactions"], off_session["interactions"], strict=True
        ):
            assert on_item["index"] == off_item["index"]
            assert on_item["question"] == off_item["question"]
            assert not on_item.get("error") and not off_item.get("error")

            case_id = f"S{session_index:02}Q{on_item['index']:02}"
            override = review["exceptions"].get(case_id, {})
            on_grade = override.get("on", review["default_grade"])
            off_grade = override.get("off", review["default_grade"])
            assert on_grade in (*GRADE_SCORE, "ambigu")
            assert off_grade in (*GRADE_SCORE, "ambigu")

            grades.append(
                {
                    "id": case_id,
                    "session": on_session["name"],
                    "question": on_item["question"],
                    "on": on_grade,
                    "off": off_grade,
                    "reason": override.get("reason"),
                }
            )
            all_on.append(on_item)
            all_off.append(off_item)

    assert len(grades) == len(all_on) == len(all_off) == 163
    results = {
        "question_file_sha256": on["question_file_sha256"],
        "question_count": len(grades),
        "grading": {
            "on": dict(Counter(item["on"] for item in grades)),
            "off": dict(Counter(item["off"] for item in grades)),
        },
        "paired": dict(
            Counter(
                "ambiguous"
                if "ambigu" in (item["on"], item["off"])
                else "on_better"
                if GRADE_SCORE[item["on"]] > GRADE_SCORE[item["off"]]
                else "off_better"
                if GRADE_SCORE[item["on"]] < GRADE_SCORE[item["off"]]
                else "tie"
                for item in grades
            )
        ),
        "runtime": {
            "on": summarize_runtime(all_on),
            "off": summarize_runtime(all_off),
        },
        "cases": grades,
    }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("on", type=Path)
    parser.add_argument("off", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    results = compare(load_json(args.on), load_json(args.off), load_json(args.review))
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: results[key] for key in ("grading", "paired", "runtime")}, indent=2))


if __name__ == "__main__":
    main()
