"""Export a replay as a human-review sheet without assigning accuracy scores.

The saved replay is development data. Reviewers should compare each answer
against the source documents before filling in the empty judgment columns.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = (
    "case_id",
    "session",
    "question_index",
    "question",
    "domain_label",
    "question_type",
    "context_intent",
    "answerability",
    "expected_answer",
    "evidence",
    "answer",
    "baseline_answer",
    "resolved_query",
    "source_sections",
    "source_parent_ids",
    "num_docs",
    "elapsed_seconds",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "human_status",
    "error_category",
    "reviewer_notes",
)


def export_replay(
    replay_path: Path, output_path: Path, *, reference_only: bool = False,
) -> int:
    if output_path.exists():
        raise FileExistsError(f"Review sheet already exists: {output_path}")

    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    rows = []
    for session_number, session in enumerate(replay["sessions"], start=1):
        session_id = session["name"].split("_", 1)[0]
        if not session_id.isdecimal():
            session_id = str(session_number)
        for interaction in session["interactions"]:
            sources = interaction.get("sources") or []
            usage = interaction.get("usage") or {}
            rows.append({
                "case_id": f"S{int(session_id):02d}Q{interaction['index']:02d}",
                "session": f"S{int(session_id):02d}" if reference_only else session["name"],
                "question_index": interaction["index"],
                "question": interaction["question"],
                "domain_label": "",
                "question_type": "",
                "context_intent": "",
                "answerability": "",
                "expected_answer": "",
                "evidence": "",
                "answer": "" if reference_only else interaction.get("answer", ""),
                "baseline_answer": "" if reference_only else interaction.get("baseline_answer", ""),
                "resolved_query": "" if reference_only else (
                    interaction.get("query_plan") or {}
                ).get("resolved_query", ""),
                "source_sections": "" if reference_only else " | ".join(
                    source.get("section", "") for source in sources
                ),
                "source_parent_ids": "" if reference_only else " | ".join(
                    source.get("parent_id", "") for source in sources
                ),
                "num_docs": "" if reference_only else interaction.get("num_docs", ""),
                "elapsed_seconds": "" if reference_only else interaction.get("elapsed_seconds", ""),
                "input_tokens": "" if reference_only else usage.get("input_tokens", ""),
                "output_tokens": "" if reference_only else usage.get("output_tokens", ""),
                "cost_usd": "" if reference_only else usage.get("cost_usd", ""),
                "human_status": "",
                "error_category": "",
                "reviewer_notes": "",
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--reference-only", action="store_true",
        help="Hide model answers, retrieval traces, and metrics while writing the answer key",
    )
    args = parser.parse_args()
    count = export_replay(args.replay, args.output, reference_only=args.reference_only)
    print(f"Exported {count} questions to {args.output}")


if __name__ == "__main__":
    main()
