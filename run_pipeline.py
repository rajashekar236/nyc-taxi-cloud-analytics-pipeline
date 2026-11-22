"""Run the whole pipeline, or chosen steps.

    python run_pipeline.py                       # everything
    python run_pipeline.py --steps transform dq  # just those steps
"""
from __future__ import annotations

import argparse
import sys
import time

STEPS = ["extract_load", "transform", "dq", "analyze"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS)
    args = parser.parse_args()

    for step in STEPS:
        if step not in args.steps:
            continue
        start = time.time()
        print(f"\n=== {step} ===")
        if step == "extract_load":
            from pipeline import extract_load
            extract_load.main()
        elif step == "transform":
            from pipeline import transform
            transform.main()
        elif step == "dq":
            from pipeline import data_quality
            data_quality.main()  # exits non-zero on failure, stopping the run
        elif step == "analyze":
            sys.argv = [sys.argv[0]]
            from analysis import stats_analysis
            stats_analysis.main()
        print(f"--- {step} finished in {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
