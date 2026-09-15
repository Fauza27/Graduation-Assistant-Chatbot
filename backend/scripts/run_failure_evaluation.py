"""Run the offline RAG failure evaluator for reviewed cases."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Batasi evaluasi ke case tertentu; dapat diulang.",
    )
    parser.add_argument(
        "--run-id",
        help="Jalankan batch pending yang sebelumnya dibuat melalui dashboard admin.",
    )
    args = parser.parse_args()
    if args.run_id and args.case_ids:
        parser.error("--run-id tidak dapat digabungkan dengan --case-id")

    from src.evaluation_agent.runner import EvaluationRunner

    runner = EvaluationRunner()
    if args.run_id:
        run_id, report = runner.run_existing(args.run_id)
    else:
        run_id, report = runner.run(set(args.case_ids) if args.case_ids else None)
    print(f"Evaluation selesai: {run_id}")
    print(f"Laporan: {report}")


if __name__ == "__main__":
    main()
