#!/usr/bin/env python3
"""
Export golden (canonical) outputs for regression testing.

Runs the adapter pipeline on each dataset under datasets/ with deterministic
metadata (fixed run_id and created_at_utc) and copies the produced artifacts
into golden/<dataset_id>/:

    golden/<dataset_id>/
        sv.json
        report.json
        projections/ml_v1.csv
        projections/llm_context_v1.json

Usage:
    python scripts/export_golden.py                          # all datasets
    python scripts/export_golden.py --only D1,D3             # specific datasets
    python scripts/export_golden.py --overwrite              # allow overwriting
    python scripts/export_golden.py --datasets-dir datasets  # custom paths
    python scripts/export_golden.py --golden-dir golden
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from adapter.pipeline import run_pipeline

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


def export_golden(
    dataset_dir: Path,
    golden_dir: Path,
    overwrite: bool,
) -> bool:
    """Run the pipeline for one dataset and copy outputs to golden/. Returns True on success."""
    ds_name = dataset_dir.name
    target = golden_dir / ds_name

    if target.exists() and not overwrite:
        print(f"  SKIP  {ds_name}: golden/{ds_name}/ already exists (use --overwrite)")
        return False

    run_id = f"golden_{ds_name}"
    created_at_utc = GOLDEN_CREATED_AT

    with tempfile.TemporaryDirectory() as tmp:
        tmp_out = Path(tmp)
        try:
            summary = run_pipeline(
                data_dir=dataset_dir,
                output_dir=tmp_out,
                run_id=run_id,
                created_at_utc=created_at_utc,
            )
        except Exception as exc:
            print(f"  FAIL  {ds_name}: pipeline crashed — {exc}")
            return False

        run_folder = Path(summary["run_folder"])
        outcome = summary["outcome"]

        # Verify all expected artifacts exist
        missing = [str(a) for a in ARTIFACTS if not (run_folder / a).exists()]
        if missing:
            print(f"  FAIL  {ds_name}: missing artifacts: {', '.join(missing)}")
            return False

        # Clear and (re)create target directory
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        (target / "projections").mkdir()

        # Copy artifacts
        for artifact in ARTIFACTS:
            shutil.copy2(run_folder / artifact, target / artifact)

        print(f"  OK    {ds_name} -> golden/{ds_name}/  (outcome: {outcome})")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export golden outputs for regression testing.",
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
        help="Output directory for golden files (default: golden)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing golden outputs (default: refuse)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of dataset prefixes to export (e.g. D1,D3)",
    )
    args = parser.parse_args()

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    datasets = discover_datasets(args.datasets_dir, only)

    if not datasets:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)

    print(f"Exporting golden outputs for {len(datasets)} dataset(s):\n")

    ok = 0
    fail = 0
    skip = 0
    for ds_dir in datasets:
        result = export_golden(ds_dir, args.golden_dir, args.overwrite)
        if result:
            ok += 1
        elif (args.golden_dir / ds_dir.name).exists() and not args.overwrite:
            skip += 1
        else:
            fail += 1

    print(f"\nDone: {ok} exported, {skip} skipped, {fail} failed.")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
