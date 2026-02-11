"""
Entry point for the adapter pipeline.

Usage:
    python run_adapter.py [data_dir] [output_dir]

Defaults:
    data_dir   = ../data/D1
    output_dir = out/
"""
import sys
from pathlib import Path

from adapter.pipeline import run_pipeline


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data" / "D1"
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent / "out"

    print(f"Pipeline: {data_dir} -> {output_dir}")
    summary = run_pipeline(data_dir, output_dir)

    print(f"Outcome: {summary['outcome']}")
    counts = summary["counts"]
    print(f"  accounts:     {counts['accounts_total']}")
    print(f"  transactions: {counts['transactions_total']}")
    print(f"  emitted (SV): {counts['transactions_emitted_sv']}")
    print(f"  dropped:      {counts['transactions_dropped']}")
    print(f"  ML rows:      {counts['ml_rows']}")
    print(f"  LLM contexts: {counts['llm_contexts']}")

    if summary["run_flags"]:
        print(f"  run_flags:    {len(summary['run_flags'])}")
        for flag in summary["run_flags"]:
            print(f"    [{flag['severity']}] {flag['id']}: {flag['message']}")

    if summary["issues"]:
        print(f"  issues:       {len(summary['issues'])}")
        for issue in summary["issues"]:
            print(f"    {issue}")
    else:
        print("  issues:       0")


if __name__ == "__main__":
    main()
