"""Replay saved student sessions with fresh local memory and no database writes.

This calls the paid chat/embedding APIs, but never starts the evaluation agent.
Old answers are retained for comparison and are not inserted into new memory.
"""

# ruff: noqa: E402 -- executable script adds the repository root before imports

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.generation.chain import get_rag_generator
from src.generation.memory import ConversationMemory
from src.generation.summarizer import get_conversation_summarizer
from src.monitoring.context import clear_current, new_collector
from src.retrieval.pipeline import run_retrieval
from src.retrieval.query_planner import build_query_plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--sessions", nargs="+", type=int, required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.output.exists():
        parser.error("Choose a new output path; existing research data is never overwritten")
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if any(i < 1 or i > len(baseline["sessions"]) for i in args.sessions):
        parser.error("Invalid session index")
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "baseline": str(args.baseline),
        "sessions": [],
        "scope": "Live RAG components; local memory; no HTTP/auth/session persistence test",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for index in args.sessions:
        old_session = baseline["sessions"][index - 1]
        session = {"name": old_session["name"], "interactions": []}
        report["sessions"].append(session)
        memory = ConversationMemory()
        for old in old_session["interactions"][:args.limit]:
            started = time.perf_counter()
            collector = new_collector(session_id=None, channel="local_replay", question=old["question"])
            row = {"index": old["index"], "question": old["question"], "baseline_answer": old["answer"]}
            try:
                plan = build_query_plan(old["question"], memory)
                row["query_plan"] = asdict(plan)
                retrieval = run_retrieval(plan.resolved_query, plan.rerank_query, plan.search_queries)
                memory.add_user_turn(plan.normalized_query)
                result = get_rag_generator().generate(
                    old["question"], retrieval.parent_documents,
                    memory.get_history_for_llm(), memory.summary,
                    resolved_question=plan.resolved_query,
                )
                memory.add_assistant_turn(result["answer"])
                if memory.needs_compaction:
                    turns = memory.get_turns_to_summarize()
                    summary = get_conversation_summarizer().summarize(memory.summary, turns)
                    memory.apply_summary(summary, turns)
                row.update(result)
                row["num_docs"] = retrieval.num_docs
            except Exception as exc:
                row["error"] = str(exc)
                raise
            finally:
                row["elapsed_seconds"] = round(time.perf_counter() - started, 2)
                row["trace"] = collector.to_trace_row()
                row["metrics"] = collector.to_row()
                session["interactions"].append(row)
                clear_current()
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            print(f"{session['name']} #{row['index']}: {row['num_docs']} docs, {row['elapsed_seconds']}s", flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
