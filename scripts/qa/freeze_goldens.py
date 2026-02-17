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
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from adapter.pipeline import run_pipeline

FROZEN_VERSION = "v1.0.0"
GOLDEN_CREATED_AT = "2000-01-01T00:00:00Z"

ARTIFACTS = [
    "sv.json",
    "report.json",
    Path("projections") / "ml_v1.csv",
    Path("projections") / "llm_context_v1.json",
]


def _sha256(path: Path) -> str:
    """Return hex SHA-256 digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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


def check_spec_lock(frozen_dir: Path) -> bool:
    """Verify spec.lock.json exists and is non-trivial."""
    lock_path = frozen_dir / "spec.lock.json"
    if not lock_path.exists():
        print(f"ERROR: {lock_path} does not exist.", file=sys.stderr)
        print("       Run the spec-lock step first.", file=sys.stderr)
        return False
    with open(lock_path, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print(f"ERROR: {lock_path} is empty ({{}}).", file=sys.stderr)
        print("       Run the spec-lock step first.", file=sys.stderr)
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

    run_id = f"GOLDEN_{ds_name}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_out = Path(tmp)
        try:
            summary = run_pipeline(
                data_dir=dataset_dir,
                output_dir=tmp_out,
                run_id=run_id,
                created_at_utc=GOLDEN_CREATED_AT,
            )
        except Exception as exc:
            print(f"  FAIL  {ds_name}: pipeline crashed — {exc}")
            return None

        run_folder = Path(summary["run_folder"])
        outcome = summary["outcome"]

        # Verify all expected artifacts exist
        missing = [str(a) for a in ARTIFACTS if not (run_folder / a).exists()]
        if missing:
            print(f"  FAIL  {ds_name}: missing artifacts: {', '.join(missing)}")
            return None

        # Clear and (re)create target directory
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        (target / "projections").mkdir()

        # Copy artifacts and compute checksums
        checksums: dict[str, str] = {}
        for artifact in ARTIFACTS:
            src = run_folder / artifact
            dst = target / artifact
            shutil.copy2(src, dst)
            checksums[str(artifact)] = f"sha256:{_sha256(dst)}"

        print(f"  OK    {ds_name} -> frozen/{FROZEN_VERSION}/golden/{ds_name}/  (outcome: {outcome})")

        return {
            "outcome": outcome,
            "run_id": run_id,
            "artifacts": checksums,
            "counts": summary.get("counts", {}),
        }


def update_manifest(
    frozen_dir: Path,
    entries: dict[str, dict],
) -> None:
    """Write/update frozen/v1.0.0/manifest.json with dataset entries."""
    manifest_path = frozen_dir / "manifest.json"

    # Load existing manifest (if any)
    manifest: dict = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, dict) and existing:
            manifest = existing

    # Ensure top-level structure
    manifest.setdefault("version", FROZEN_VERSION.lstrip("v"))
    manifest["frozen_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest.setdefault("datasets", {})

    # Merge new entries
    for ds_name, entry in entries.items():
        manifest["datasets"][ds_name] = entry

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")

    print(f"\nManifest updated: {manifest_path}")


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
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=REPO_ROOT / "datasets",
        help="Root directory containing dataset folders (default: datasets)",
    )
    parser.add_argument(
        "--frozen-dir",
        type=Path,
        default=REPO_ROOT / "frozen" / FROZEN_VERSION,
        help=f"Frozen version directory (default: frozen/{FROZEN_VERSION})",
    )
    args = parser.parse_args()

    frozen_dir = args.frozen_dir
    golden_dir = frozen_dir / "golden"

    # --- Gate: spec.lock.json must be present and non-empty ---
    if not check_spec_lock(frozen_dir):
        sys.exit(1)

    only = [s.strip() for s in args.dataset.split(",")] if args.dataset else None
    datasets = discover_datasets(args.datasets_dir, only)

    if not datasets:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)

    print(f"Freezing golden outputs for {len(datasets)} dataset(s):\n")

    ok = 0
    fail = 0
    skip = 0
    manifest_entries: dict[str, dict] = {}

    for ds_dir in datasets:
        entry = freeze_one(ds_dir, golden_dir, args.force)
        if entry is not None:
            ok += 1
            manifest_entries[ds_dir.name] = entry
        elif (golden_dir / ds_dir.name).exists() and not args.force:
            skip += 1
        else:
            fail += 1

    # Update manifest with successful entries
    if manifest_entries:
        update_manifest(frozen_dir, manifest_entries)

    print(f"\nDone: {ok} frozen, {skip} skipped, {fail} failed.")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
