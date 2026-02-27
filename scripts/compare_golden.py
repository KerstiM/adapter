#!/usr/bin/env python3
"""
Compare current pipeline outputs against golden (canonical) outputs.

For each dataset, runs the pipeline with the same deterministic metadata used
by export_golden.py, then diffs every artifact against the corresponding
golden file.  Exits non-zero if any mismatch is found.

Usage:
    python scripts/compare_golden.py                    # all datasets
    python scripts/compare_golden.py --only D1,D3       # specific datasets
    python scripts/compare_golden.py --datasets-dir datasets --golden-dir golden
"""
import argparse
import csv
import difflib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from entrypoints.wiring_fs import run_pipeline_fs

GOLDEN_CREATED_AT = "2000-01-01T00:00:00Z"

ARTIFACTS = [
    "sv.json",
    "report.json",
    Path("projections") / "ml_v1.csv",
    Path("projections") / "llm_context_v1.json",
]


def discover_datasets(
    datasets_dir: Path,
    only: list[str] | None = None,
) -> list[Path]:
    """Find dataset directories that contain accounts.json + transactions.json."""
    datasets = []
    for d in sorted(datasets_dir.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "accounts.json").exists() or not (d / "transactions.json").exists():
            continue
        if only:
            if not any(d.name.upper().startswith(f.upper()) for f in only):
                continue
        datasets.append(d)
    return datasets


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _diff_text(golden_text: str, actual_text: str, label: str) -> list[str]:
    """Return unified diff lines between golden and actual text."""
    golden_lines = golden_text.splitlines(keepends=True)
    actual_lines = actual_text.splitlines(keepends=True)
    return list(difflib.unified_diff(
        golden_lines,
        actual_lines,
        fromfile=f"golden/{label}",
        tofile=f"actual/{label}",
        lineterm="",
    ))


def compare_dataset(
    dataset_dir: Path,
    golden_dir: Path,
) -> dict:
    """
    Run pipeline and compare against golden.

    Returns dict:
        dataset: str
        status: "MATCH" | "MISMATCH" | "ERROR" | "NO_GOLDEN"
        diffs: dict[str, list[str]]   (artifact -> diff lines)
        error: str | None
    """
    ds_name = dataset_dir.name
    golden_ds = golden_dir / ds_name

    if not golden_ds.exists():
        return {
            "dataset": ds_name,
            "status": "NO_GOLDEN",
            "diffs": {},
            "error": f"golden/{ds_name}/ does not exist",
        }

    run_id = f"golden_{ds_name}"
    created_at_utc = GOLDEN_CREATED_AT

    with tempfile.TemporaryDirectory() as tmp:
        tmp_out = Path(tmp)
        try:
            summary = run_pipeline_fs(
                data_dir=dataset_dir,
                output_dir=tmp_out,
                spec_dir=REPO_ROOT / "spec",
                run_id=run_id,
                created_at_utc=created_at_utc,
            )
        except Exception as exc:
            return {
                "dataset": ds_name,
                "status": "ERROR",
                "diffs": {},
                "error": f"pipeline crashed: {exc}",
            }

        run_folder = Path(summary["run_folder"])
        diffs: dict[str, list[str]] = {}

        for artifact in ARTIFACTS:
            golden_path = golden_ds / artifact
            actual_path = run_folder / artifact

            if not golden_path.exists():
                diffs[str(artifact)] = [f"--- golden file missing: {golden_path}"]
                continue
            if not actual_path.exists():
                diffs[str(artifact)] = [f"+++ actual file missing: {actual_path}"]
                continue

            golden_text = _read_text(golden_path)
            actual_text = _read_text(actual_path)

            diff_lines = _diff_text(golden_text, actual_text, f"{ds_name}/{artifact}")
            if diff_lines:
                diffs[str(artifact)] = diff_lines

    status = "MISMATCH" if diffs else "MATCH"
    return {
        "dataset": ds_name,
        "status": status,
        "diffs": diffs,
        "error": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare pipeline outputs against golden files.",
    )
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=REPO_ROOT / "datasets",
        help="Root directory containing dataset folders (default: datasets)",
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=REPO_ROOT / "golden",
        help="Directory containing golden files (default: golden)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of dataset prefixes to compare (e.g. D1,D3)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Print full diff output for mismatches",
    )
    args = parser.parse_args()

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    datasets = discover_datasets(args.datasets_dir, only)

    if not datasets:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)

    print(f"Comparing {len(datasets)} dataset(s) against golden outputs:\n")

    match_count = 0
    mismatch_count = 0
    error_count = 0

    for ds_dir in datasets:
        result = compare_dataset(ds_dir, args.golden_dir)
        status = result["status"]

        if status == "MATCH":
            print(f"  MATCH     {result['dataset']}")
            match_count += 1
        elif status == "NO_GOLDEN":
            print(f"  NO_GOLDEN {result['dataset']}: {result['error']}")
            error_count += 1
        elif status == "ERROR":
            print(f"  ERROR     {result['dataset']}: {result['error']}")
            error_count += 1
        else:
            artifacts = ", ".join(result["diffs"].keys())
            print(f"  MISMATCH  {result['dataset']}: differs in {artifacts}")
            if args.verbose:
                for artifact, diff_lines in result["diffs"].items():
                    print(f"\n    --- {artifact} ---")
                    for line in diff_lines[:50]:
                        print(f"    {line.rstrip()}")
                    if len(diff_lines) > 50:
                        print(f"    ... ({len(diff_lines) - 50} more lines)")
            mismatch_count += 1

    print(f"\nDone: {match_count} match, {mismatch_count} mismatch, {error_count} error.")

    if mismatch_count > 0 or error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
