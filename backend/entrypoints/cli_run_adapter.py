"""
CLI driving adapter for the pipeline.

Examples (run from repo root):

    # Single dataset — short prefix name (D1 → D1_synth_valid_small)
    python backend/entrypoints/cli_run_adapter.py --data D1

    # Full folder name or path also work
    python backend/entrypoints/cli_run_adapter.py --data D1_synth_valid_small
    python backend/entrypoints/cli_run_adapter.py --data datasets/D4_synth_errors_seed42

    # No args → defaults to D1_synth_valid_small
    python backend/entrypoints/cli_run_adapter.py

    # All datasets under datasets/
    for d in datasets/D*; do
        python backend/entrypoints/cli_run_adapter.py --data "$d"
    done

    # With target models
    python backend/entrypoints/cli_run_adapter.py --data D1 \\
        --target-llm llama3.1-8b-instruct --target-ml xgboost

    # Custom output folder (default: <repo>/.pipeline_out/, gitignored)
    python backend/entrypoints/cli_run_adapter.py --data D1 --out backend/out

From the backend/ directory:
    python -m entrypoints.cli_run_adapter --data D1

Full flag reference: --help.
"""
import argparse
import os
import sys
from pathlib import Path

# When this file is executed directly as a script (python backend/entrypoints/cli_run_adapter.py),
# Python puts the script's own directory on sys.path instead of backend/. Add backend/ so the
# absolute `from entrypoints.wiring_fs import ...` below resolves in both invocation modes.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from entrypoints.wiring_fs import run_pipeline_fs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
SEARCH_DIRS = [ROOT / "datasets"]

# Color handling — emit ANSI only when stdout is a real terminal and the
# user hasn't opted out via NO_COLOR (https://no-color.org).
_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
_BOLD = "\033[1m" if _USE_COLOR else ""
_CYAN = "\033[96m" if _USE_COLOR else ""
_GREEN = "\033[92m" if _USE_COLOR else ""
_YELLOW = "\033[93m" if _USE_COLOR else ""
_RED = "\033[91m" if _USE_COLOR else ""
_RESET = "\033[0m" if _USE_COLOR else ""

_OUTCOME_COLOR = {"SUCCESS": _GREEN, "PARTIAL_SUCCESS": _YELLOW, "FAIL": _RED}
_SEVERITY_COLOR = {"ERROR": _RED, "WARN": _YELLOW, "INFO": _CYAN}


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
                             "Default: D1_synth_valid_small")
    parser.add_argument("--out", "-o", default=None,
                        help="Output directory (relative to repo root unless "
                             "absolute). Default: .pipeline_out/ (gitignored)")
    parser.add_argument("--target-llm", nargs="*", default=None,
                        metavar="MODEL",
                        help="LLM model(s) to generate projections for. "
                             "Options: llama3.1-8b-instruct, "
                             "mistral-7b-instruct-v0.3, qwen2.5-7b-instruct")
    parser.add_argument("--target-ml", nargs="*", default=None,
                        metavar="MODEL",
                        help="ML model(s) to generate projections for. "
                             "Options: xgboost, catboost")
    parser.add_argument("--llm-preamble", default=None,
                        help="System preamble for LLM projections. "
                             "Overrides profile setting.")
    parser.add_argument("--profile", "-p", default="default",
                        help="Run profile to use (e.g. extensions_eval). "
                             "Default: default")
    args = parser.parse_args()

    if args.data:
        data_dir = _resolve_data_dir(args.data)
    else:
        data_dir = _resolve_data_dir("D1_synth_valid_small")

    if args.out:
        out_path = Path(args.out)
        # Resolve relative --out paths against repo root, not CWD
        output_dir = out_path if out_path.is_absolute() else ROOT / out_path
    else:
        output_dir = ROOT / ".pipeline_out"

    # Build target_models override from CLI flags
    target_models_override = None
    if args.target_llm is not None or args.target_ml is not None or args.llm_preamble is not None:
        target_models_override = {}
        if args.target_llm is not None:
            target_models_override["llm"] = args.target_llm
        if args.target_ml is not None:
            target_models_override["ml"] = args.target_ml
        if args.llm_preamble is not None:
            target_models_override["llm_preamble"] = args.llm_preamble

    bar = "=" * 72
    print()
    print(f"{_BOLD}{_CYAN}{bar}{_RESET}")
    print(f"{_BOLD}{_CYAN}  Running: {data_dir.name}{_RESET}")
    print(f"{_BOLD}{_CYAN}{bar}{_RESET}")
    print(f"Dataset:    {data_dir}")
    print(f"Output to:  {output_dir}")
    if args.profile != "default":
        print(f"Profile:    {args.profile}")
    if target_models_override:
        if target_models_override.get("llm"):
            print(f"Target LLM: {', '.join(target_models_override['llm'])}")
        if target_models_override.get("ml"):
            print(f"Target ML:  {', '.join(target_models_override['ml'])}")
    print()

    summary = run_pipeline_fs(
        data_dir, output_dir, spec_dir=ROOT / "spec",
        profile_id=args.profile,
        target_models_override=target_models_override,
    )

    outcome = summary["outcome"]
    outcome_color = _OUTCOME_COLOR.get(outcome, "")
    print(f"Outcome:    {outcome_color}{_BOLD}{outcome}{_RESET}")
    print(f"stop_reason: {summary.get('stop_reason', '?')}")
    print(f"Run folder: {summary['run_folder']}")
    counts = summary["counts"]
    print(f"  accounts:     {counts['accounts_total']}")
    print(f"  transactions: {counts['transactions_total']}")
    print(f"  emitted (SV): {counts['transactions_emitted_sv']}")
    dropped = counts['transactions_dropped']
    dropped_color = _YELLOW if dropped > 0 else ""
    print(f"  dropped:      {dropped_color}{dropped}{_RESET if dropped_color else ''}")
    print(f"  ML rows:      {counts['ml_rows']}")
    print(f"  LLM contexts: {counts['llm_contexts']}")

    sev_issues = summary.get("by_severity_issues", {})
    if any(v > 0 for v in sev_issues.values()):
        print(f"  by_severity_issues:  {sev_issues}")

    if summary.get("dropped_details"):
        print(f"  dropped_details:")
        for d in summary["dropped_details"]:
            print(f"    {d.get('input_path', '?')} ({d.get('source_file', '?')}): {d.get('drop_reason', '?')}")

    if summary["run_flags"]:
        print(f"  run_flags:    {len(summary['run_flags'])}")
        for flag in summary["run_flags"]:
            sev = flag['severity']
            c = _SEVERITY_COLOR.get(sev, "")
            print(f"    {c}[{sev}]{_RESET if c else ''} {flag['id']}: {flag['message']}")

    if summary["issues"]:
        print(f"  issues:       {len(summary['issues'])}")
        for issue in summary["issues"]:
            if isinstance(issue, dict):
                sev = issue.get('severity', '?')
                c = _SEVERITY_COLOR.get(sev, "")
                print(f"    {c}[{sev}]{_RESET if c else ''} {issue.get('code', '?')}: {issue.get('message', '')}")
            else:
                print(f"    {issue}")
    else:
        print("  issues:       0")

    print(f"{_BOLD}{_CYAN}{bar}{_RESET}")


if __name__ == "__main__":
    main()
