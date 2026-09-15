"""Replay all cases from an evaluation run after approved fixes are applied."""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        required=True,
        help="ID evaluation run yang akan diuji ulang",
    )
    args = parser.parse_args()

    from src.evaluation_agent.regression import RegressionRunner

    results = RegressionRunner().run(args.run_id)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
