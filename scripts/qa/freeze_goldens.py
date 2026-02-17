#!/usr/bin/env python3
"""
Freeze golden outputs into frozen/v1.0.0/golden/<dataset_id>/.

Runs the adapter pipeline on each dataset with deterministic metadata
(fixed run_id and created_at_utc) and copies the produced artifacts into
the frozen version directory.  Also writes/updates manifest.json with
SHA-256 checksums for every artifact.

Prerequisites:
    frozen/v1.0.0/spec.lock.json must exist and be non-empty (not just {}).

Usage:
    python scripts/qa/freeze_goldens.py                    # all datasets
    python scripts/qa/freeze_goldens.py --dataset D1,D3    # specific datasets
    python scripts/qa/freeze_goldens.py --force            # overwrite existing
"""
import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Bootstrap: ensure _utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (
    ARTIFACT_MAP,
    FROZEN_DIR,
    FROZEN_VERSION,
    REPO_ROOT,
    discover_datasets,
    run_pipeline_deterministic,
    sha256_bytes,
    sha256_file,
)


def check_spec_lock(frozen_dir: Path) -> bool:
    """Verify spec.lock.json exists and is non-trivial."""
    lock_path = frozen_dir / "spec.lock.json"
    if not lock_path.exists():
        print(f"ERROR: {lock_path} does not exist.", file=sys.stderr)
        print("       Run  python scripts/qa/build_spec_lock.py  first.", file=sys.stderr)
        return False
    with open(lock_path, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print(f"ERROR: {lock_path} is empty ({{}}).", file=sys.stderr)
        print("       Run  python scripts/qa/build_spec_lock.py  first.", file=sys.stderr)
        return False
    return True


def freeze_one(
    dataset_dir: Path,
    golden_dir: Path,
    force: bool,
) -> dict | None:
    """Run the pipeline for one dataset and copy outputs to golden/.

    Returns a manifest entry dict on success, or None on failure/skip.
    """
    ds_name = dataset_dir.name
    target = golden_dir / ds_name

    if target.exists() and not force:
        print(f"  SKIP  {ds_name}: already frozen (use --force to overwrite)")
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_out = Path(tmp)
        try:
            summary = run_pipeline_deterministic(dataset_dir, tmp_out)
        except Exception as exc:
            print(f"  FAIL  {ds_name}: pipeline crashed — {exc}")
            return None

        run_folder = Path(summary["run_folder"])
        outcome = summary["outcome"]

        # Verify all expected artifacts exist
        missing = [run_path for run_path, _ in ARTIFACT_MAP if not (run_folder / run_path).exists()]
        if missing:
            print(f"  FAIL  {ds_name}: missing artifacts: {', '.join(missing)}")
            return None

        # Clear and (re)create target directory
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        (target / "projections").mkdir()

        # Copy artifacts and compute checksums
        golden: dict[str, dict[str, str]] = {}
        for run_path, manifest_key in ARTIFACT_MAP:
            src = run_folder / run_path
            dst = target / run_path
            shutil.copy2(src, dst)
            golden[manifest_key] = {"sha256": sha256_file(dst)}

        print(f"  OK    {ds_name} -> frozen/{FROZEN_VERSION}/golden/{ds_name}/  (outcome: {outcome})")

        entry: dict = {
            "dataset_id": ds_name,
            "expected_outcome": outcome,
            "golden": golden,
        }

        counts = summary.get("counts")
        if counts:
            entry["counts"] = counts

        return entry


def write_manifest(
    frozen_dir: Path,
    entries: list[dict],
) -> None:
    """Write frozen/v1.0.0/manifest.json in list format expected by run_full_qa.py."""
    manifest_path = frozen_dir / "manifest.json"
    lock_path = frozen_dir / "spec.lock.json"

    spec_lock_hash = sha256_bytes(lock_path.read_bytes()) if lock_path.exists() else ""

    manifest = {
        "frozen_version": FROZEN_VERSION,
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spec_lock_sha256": spec_lock_hash,
        "datasets": entries,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")

    print(f"\nManifest written: {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze golden outputs into frozen/v1.0.0/golden/.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Comma-separated list of dataset prefixes to freeze (e.g. D1,D3)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite existing frozen golden outputs",
    )
    args = parser.parse_args()

    frozen_dir = FROZEN_DIR
    golden_dir = frozen_dir / "golden"

    # --- Gate: spec.lock.json must be present and non-empty ---
    if not check_spec_lock(frozen_dir):
        sys.exit(1)

    ds_filter = [s.strip() for s in args.dataset.split(",")] if args.dataset else None
    datasets = discover_datasets(ds_filter)

    if not datasets:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)

    # Load existing manifest to preserve entries for datasets we are NOT re-freezing
    manifest_path = frozen_dir / "manifest.json"
    existing_entries: dict[str, dict] = {}
    if manifest_path.exists():
        try:
            existing = json.load(open(manifest_path, encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("datasets"), list):
                for entry in existing["datasets"]:
                    existing_entries[entry["dataset_id"]] = entry
        except Exception:
            pass

    print(f"Freezing golden outputs for {len(datasets)} dataset(s):\n")

    ok = 0
    fail = 0
    skip = 0
    new_entries: dict[str, dict] = {}

    for ds_dir in datasets:
        entry = freeze_one(ds_dir, golden_dir, args.force)
        if entry is not None:
            ok += 1
            new_entries[entry["dataset_id"]] = entry
        elif (golden_dir / ds_dir.name).exists() and not args.force:
            skip += 1
        else:
            fail += 1

    # Merge: new entries override existing ones; preserve unaffected datasets
    merged = dict(existing_entries)
    merged.update(new_entries)

    # Write manifest with all entries (sorted by dataset_id)
    if new_entries:
        sorted_entries = [merged[k] for k in sorted(merged)]
        write_manifest(frozen_dir, sorted_entries)

    print(f"\nDone: {ok} frozen, {skip} skipped, {fail} failed.")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
