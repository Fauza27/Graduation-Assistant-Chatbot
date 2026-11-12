"""Compare two paired chatbot replays using a manually reviewed candidate."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from compare_reranker_replay import GRADE_SCORE, summarize_runtime


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare(baseline: dict, candidate: dict, baseline_review: dict, candidate_review: dict) -> dict:
    assert baseline["question_file_sha256"] == candidate["question_file_sha256"]
    assert baseline["reranker_enabled"] is candidate["reranker_enabled"] is False
    assert len(baseline["sessions"]) == len(candidate["sessions"]) == 20
    assert candidate_review["reviewed_sessions"] == list(range(1, 21))

    baseline_rows, candidate_rows, cases = [], [], []
    prior_cases = {case["id"]: case for case in baseline_review["cases"]}
    for session_index, (prior, current) in enumerate(
        zip(baseline["sessions"], candidate["sessions"], strict=True), start=1
    ):
        assert prior["name"] == current["name"]
        for old, new in zip(prior["interactions"], current["interactions"], strict=True):
            assert old["index"] == new["index"] and old["question"] == new["question"]
            assert not old.get("error") and not new.get("error")
            case_id = f"S{session_index:02}Q{old['index']:02}"
            baseline_grade = prior_cases[case_id]["off"]
            override = candidate_review["exceptions"].get(case_id, {})
            candidate_grade = override.get("grade", candidate_review["default_grade"])
            assert baseline_grade in (*GRADE_SCORE, "ambigu")
            assert candidate_grade in (*GRADE_SCORE, "ambigu")
            assert (baseline_grade == "ambigu") == (candidate_grade == "ambigu")

            cases.append({
                "id": case_id,
                "session": prior["name"],
                "question": old["question"],
                "baseline": baseline_grade,
                "candidate": candidate_grade,
                "reason": override.get("reason"),
            })
            baseline_rows.append(old)
            candidate_rows.append(new)

    assert len(cases) == len(baseline_rows) == len(candidate_rows) == 163
    paired = Counter(
        "ambiguous" if case["baseline"] == "ambigu"
        else "candidate_better" if GRADE_SCORE[case["candidate"]] > GRADE_SCORE[case["baseline"]]
        else "baseline_better" if GRADE_SCORE[case["candidate"]] < GRADE_SCORE[case["baseline"]]
        else "tie"
        for case in cases
    )
    return {
        "question_file_sha256": baseline["question_file_sha256"],
        "question_count": len(cases),
        "grading": {
            "baseline": dict(Counter(case["baseline"] for case in cases)),
            "candidate": dict(Counter(case["candidate"] for case in cases)),
        },
        "paired": dict(paired),
        "runtime": {
            "baseline": summarize_runtime(baseline_rows),
            "candidate": summarize_runtime(candidate_rows),
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("baseline_review", type=Path)
    parser.add_argument("candidate_review", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = compare(
        load(args.baseline), load(args.candidate),
        load(args.baseline_review), load(args.candidate_review),
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("grading", "paired", "runtime")}, indent=2))


if __name__ == "__main__":
    main()
