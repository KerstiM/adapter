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
    report = run_pipeline(data_dir, output_dir)

    status = report["outcome"]["status"]
    counts = report["summary"]["counts"]
    print(f"Outcome: {status}")
    print(f"  accounts:     {counts['accounts_total']}")
    print(f"  transactions: {counts['transactions_total']}")
    print(f"  emitted (SV): {counts['transactions_emitted_sv']}")
    print(f"  dropped:      {counts['transactions_dropped']}")

    if report["issues"]:
        print(f"  issues:       {len(report['issues'])}")
    else:
        print("  issues:       0")


if __name__ == "__main__":
    main()
