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
_BAR = "=" * 72


def _resolve_data_dir(name: str) -> Path:
    """Resolve a dataset name or path to an actual directory.

    Tries in order:
      1. Exact path as given, or path relative to repo root
      2. Exact folder name under datasets/
      3. Prefix match: folder equals *name* (case-insensitive) or starts
         with *name* + ``"_"`` (case-insensitive).  The ``"_"`` fence
         prevents ``D1`` from matching ``D10_*``.
    """
    # 1. Direct path — try as-given and resolved against repo root so that
    #    e.g. ``datasets/D1_*`` works from both repo root and backend/.
    for p in (Path(name), ROOT / name):
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


def _build_target_models_override(args: argparse.Namespace) -> dict | None:
    """Collapse the three --target-* CLI flags into a single override dict.

    Returns ``None`` when none of the flags were supplied so the pipeline
    falls back to the profile's defaults.
    """
    if args.target_llm is None and args.target_ml is None and args.llm_preamble is None:
        return None
    override: dict = {}
    if args.target_llm is not None:
        override["llm"] = args.target_llm
    if args.target_ml is not None:
        override["ml"] = args.target_ml
    if args.llm_preamble is not None:
        override["llm_preamble"] = args.llm_preamble
    return override


def _resolve_output_dir(out_arg: str | None) -> Path:
    """Resolve --out to an output directory path.

    Returns the default ``ROOT/.pipeline_out`` when *out_arg* is empty.
    Absolute paths are honoured as-is; relative paths resolve against the
    repo root (not the caller's CWD).
    """
    if not out_arg:
        return ROOT / ".pipeline_out"
    out_path = Path(out_arg)
    return out_path if out_path.is_absolute() else ROOT / out_path


def _print_run_header(
    data_dir: Path,
    output_dir: Path,
    profile: str,
    target_models_override: dict | None,
) -> None:
    """Print the dataset/output/profile banner shown before the pipeline run."""
    print()
    print(f"{_BOLD}{_CYAN}{_BAR}{_RESET}")
    print(f"{_BOLD}{_CYAN}  Running: {data_dir.name}{_RESET}")
    print(f"{_BOLD}{_CYAN}{_BAR}{_RESET}")
    print(f"Dataset:    {data_dir}")
    print(f"Output to:  {output_dir}")
    if profile != "default":
        print(f"Profile:    {profile}")
    if target_models_override:
        if target_models_override.get("llm"):
            print(f"Target LLM: {', '.join(target_models_override['llm'])}")
        if target_models_override.get("ml"):
            print(f"Target ML:  {', '.join(target_models_override['ml'])}")
    print()


def _print_outcome_and_counts(summary: dict) -> None:
    """Print outcome line + counts table + by_severity_issues overview."""
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


def _print_dropped_details(dropped_details: list[dict] | None) -> None:
    """Print per-record drop reasons, one line each.  No-op when empty."""
    if not dropped_details:
        return
    print(f"  dropped_details:")
    for d in dropped_details:
        print(f"    {d.get('input_path', '?')} ({d.get('source_file', '?')}): {d.get('drop_reason', '?')}")


def _print_run_flags(run_flags: list[dict]) -> None:
    """Print run-level flags with severity coloring.  No-op when empty."""
    if not run_flags:
        return
    print(f"  run_flags:    {len(run_flags)}")
    for flag in run_flags:
        sev = flag['severity']
        c = _SEVERITY_COLOR.get(sev, "")
        print(f"    {c}[{sev}]{_RESET if c else ''} {flag['id']}: {flag['message']}")


def _print_issues(issues: list) -> None:
    """Print pipeline issues with severity coloring; print "0" line when none."""
    if not issues:
        print("  issues:       0")
        return
    print(f"  issues:       {len(issues)}")
    for issue in issues:
        if isinstance(issue, dict):
            sev = issue.get('severity', '?')
            c = _SEVERITY_COLOR.get(sev, "")
            print(f"    {c}[{sev}]{_RESET if c else ''} {issue.get('code', '?')}: {issue.get('message', '')}")
        else:
            print(f"    {issue}")


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

    data_dir = _resolve_data_dir(args.data or "D1_synth_valid_small")
    output_dir = _resolve_output_dir(args.out)
    target_models_override = _build_target_models_override(args)

    _print_run_header(data_dir, output_dir, args.profile, target_models_override)

    summary = run_pipeline_fs(
        data_dir, output_dir, spec_dir=ROOT / "spec",
        profile_id=args.profile,
        target_models_override=target_models_override,
    )

    _print_outcome_and_counts(summary)
    _print_dropped_details(summary.get("dropped_details"))
    _print_run_flags(summary["run_flags"])
    _print_issues(summary["issues"])
    print(f"{_BOLD}{_CYAN}{_BAR}{_RESET}")


if __name__ == "__main__":
    main()
