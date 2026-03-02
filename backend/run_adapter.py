"""
Entry point for the adapter pipeline.

Usage:
    python run_adapter.py --data D4
    python run_adapter.py --data D1_public_valid_small
    python run_adapter.py --data ../datasets/D4_synth_errors_seed42
    python run_adapter.py                          # defaults to D1_public_valid_small
"""
import argparse
from pathlib import Path

from entrypoints.wiring_fs import run_pipeline_fs

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = [ROOT / "datasets"]


def _resolve_data_dir(name: str) -> Path:
    """Resolve a dataset name or path to an actual directory.

    Tries in order:
      1. Exact path (absolute or relative)
      2. Exact folder name under datasets/
      3. Prefix match: folder equals *name* (case-insensitive) or starts
         with *name* + ``"_"`` (case-insensitive).  The ``"_"`` fence
         prevents ``D1`` from matching ``D10_*``.
    """
    # 1. Direct path
    p = Path(name)
    if p.is_dir() and (p / "accounts.json").exists():
        return p

    # 2 & 3. Search known dirs
    name_upper = name.upper()
    for search_dir in SEARCH_DIRS:
        if not search_dir.is_dir():
            continue
        # Exact folder-name match
        candidate = search_dir / name
        if candidate.is_dir() and (candidate / "accounts.json").exists():
            return candidate
        # Prefix match – require name + "_" so "D1" won't match "D10_*"
        matches = sorted(
            d for d in search_dir.iterdir()
            if d.is_dir()
            and (d.name.upper() == name_upper
                 or d.name.upper().startswith(name_upper + "_"))
            and (d / "accounts.json").exists()
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(m.name for m in matches)
            raise SystemExit(f"Ambiguous dataset '{name}', matches: {names}")

    raise SystemExit(f"Dataset '{name}' not found. Checked: {', '.join(str(d) for d in SEARCH_DIRS)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the adapter pipeline.")
    parser.add_argument("--data", "-d", default=None,
                        help="Dataset name (e.g. D1, D4) or path. "
                             "Default: D1_public_valid_small")
    parser.add_argument("--out", "-o", default=None,
                        help="Output directory. Default: <repo>/.backend/out/")
    args = parser.parse_args()

    if args.data:
        data_dir = _resolve_data_dir(args.data)
    else:
        data_dir = _resolve_data_dir("D1_public_valid_small")

    output_dir = Path(args.out) if args.out else ROOT / ".backend" / "out"

    print(f"Dataset:    {data_dir}")
    print(f"Output to:  {output_dir}")
    print()

    summary = run_pipeline_fs(data_dir, output_dir, spec_dir=ROOT / "spec")

    print(f"Outcome:    {summary['outcome']}")
    print(f"stop_reason: {summary.get('stop_reason', '?')}")
    print(f"Run folder: {summary['run_folder']}")
    counts = summary["counts"]
    print(f"  accounts:     {counts['accounts_total']}")
    print(f"  transactions: {counts['transactions_total']}")
    print(f"  emitted (SV): {counts['transactions_emitted_sv']}")
    print(f"  dropped:      {counts['transactions_dropped']}")
    print(f"  ML rows:      {counts['ml_rows']}")
    print(f"  LLM contexts: {counts['llm_contexts']}")

    sev = summary.get("by_severity", {})
    if any(v > 0 for v in sev.values()):
        print(f"  by_severity:  {sev}")

    if summary.get("dropped_details"):
        print(f"  dropped_details:")
        for d in summary["dropped_details"]:
            print(f"    {d.get('input_path', '?')} ({d.get('source_file', '?')}): {d.get('drop_reason', '?')}")

    if summary["run_flags"]:
        print(f"  run_flags:    {len(summary['run_flags'])}")
        for flag in summary["run_flags"]:
            print(f"    [{flag['severity']}] {flag['id']}: {flag['message']}")

    if summary["issues"]:
        print(f"  issues:       {len(summary['issues'])}")
        for issue in summary["issues"]:
            if isinstance(issue, dict):
                print(f"    [{issue.get('severity', '?')}] {issue.get('code', '?')}: {issue.get('message', '')}")
            else:
                print(f"    {issue}")
    else:
        print("  issues:       0")


if __name__ == "__main__":
    main()
