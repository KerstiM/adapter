#!/usr/bin/env python3
"""
Verify frozen golden outputs are still reproducible.

Reads manifest.json + spec.lock.json, re-runs the pipeline for every dataset
with the same deterministic metadata used by freeze_goldens.py, and compares
the produced artifacts against the manifest SHA-256 checksums.

Exits 0 if everything matches, 1 if any mismatch or error is found.

Usage:
    python scripts/qa/verify_goldens.py                     # verify all
    python scripts/qa/verify_goldens.py --dataset D1,D3     # specific datasets
    python scripts/qa/verify_goldens.py -v                  # verbose (show diffs)
    python scripts/qa/verify_goldens.py --update            # re-freeze on failure
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Bootstrap: ensure _utils is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _utils import (
    ARTIFACT_MAP,
    FROZEN_DIR,
    FROZEN_VERSION,
    REPO_ROOT,
    diff_csv_first_row,
    diff_json_files,
    discover_datasets,
    run_pipeline_deterministic,
    sha256_bytes,
    sha256_file,
)


# ---------------------------------------------------------------------------
# Phase 1: spec.lock.json integrity
# ---------------------------------------------------------------------------

def verify_spec_lock(frozen_dir: Path) -> list[str]:
    """Check every artifact listed in spec.lock.json still has the same hash.

    Returns a list of failure messages (empty = all good).
    """
    lock_path = frozen_dir / "spec.lock.json"
    if not lock_path.exists():
        return [f"spec.lock.json not found at {lock_path}"]

    with open(lock_path, encoding="utf-8") as f:
        lock = json.load(f)

    if not lock:
        return [f"spec.lock.json is empty at {lock_path}"]

    failures: list[str] = []

    # Check profile
    profile = lock.get("profile", {})
    profile_path = REPO_ROOT / profile.get("path", "")
    if profile_path.exists():
        actual = sha256_file(profile_path)
        expected = profile.get("sha256", "")
        if actual != expected:
            failures.append(
                f"  profile {profile.get('id')}: expected {expected[:12]}... got {actual[:12]}..."
            )
    else:
        failures.append(f"  profile file missing: {profile_path}")

    # Check each artifact
    for art in lock.get("artifacts", []):
        art_path = REPO_ROOT / art["path"]
        if not art_path.exists():
            failures.append(f"  {art['id']} ({art['kind']}): file missing — {art['path']}")
            continue
        actual = sha256_file(art_path)
        expected = art["sha256"]
        if actual != expected:
            failures.append(
                f"  {art['id']} ({art['kind']}): expected {expected[:12]}... got {actual[:12]}..."
            )

    return failures


# ---------------------------------------------------------------------------
# Phase 2: manifest.json format guard and cross-check with spec.lock.json
# ---------------------------------------------------------------------------

def verify_manifest_meta(frozen_dir: Path) -> list[str]:
    """Verify manifest.json exists, has the correct format, and spec_lock_sha256 matches."""
    manifest_path = frozen_dir / "manifest.json"
    lock_path = frozen_dir / "spec.lock.json"

    if not manifest_path.exists():
        return [f"manifest.json not found at {manifest_path}"]

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    failures: list[str] = []

    # --- Format guard: detect old/wrong manifest format ---
    datasets_field = manifest.get("datasets")
    if isinstance(datasets_field, dict):
        failures.append(
            "  manifest.json has 'datasets' as a dict (old format).\n"
            "  Re-run:  python scripts/qa/freeze_goldens.py --force\n"
            "  to regenerate the manifest in the expected list format."
        )
        return failures

    if "frozen_version" not in manifest:
        failures.append(
            "  manifest.json is missing 'frozen_version'.\n"
            "  Re-run:  python scripts/qa/freeze_goldens.py --force\n"
            "  to regenerate the manifest."
        )
        return failures

    if "spec_lock_sha256" not in manifest:
        failures.append(
            "  manifest.json is missing 'spec_lock_sha256'.\n"
            "  Re-run:  python scripts/qa/freeze_goldens.py --force\n"
            "  to regenerate the manifest."
        )
        return failures

    # --- Validate frozen_version ---
    if manifest["frozen_version"] != FROZEN_VERSION:
        failures.append(
            f"  frozen_version: expected {FROZEN_VERSION!r}, "
            f"got {manifest['frozen_version']!r}"
        )

    # --- Validate spec_lock_sha256 ---
    if lock_path.exists():
        actual_lock_hash = sha256_bytes(lock_path.read_bytes())
        expected_lock_hash = manifest.get("spec_lock_sha256", "")
        if actual_lock_hash != expected_lock_hash:
            failures.append(
                f"  spec_lock_sha256 mismatch: manifest says {expected_lock_hash[:12]}... "
                f"but file hashes to {actual_lock_hash[:12]}..."
            )

    return failures


# ---------------------------------------------------------------------------
# Phase 3: re-run pipeline and compare hashes
# ---------------------------------------------------------------------------

def verify_dataset(
    dataset_dir: Path,
    manifest_entry: dict,
    verbose: bool = False,
) -> dict:
    """Run pipeline for one dataset and compare against manifest checksums.

    Returns:
        dataset:  str
        status:   "PASS" | "FAIL" | "ERROR"
        details:  list[str]   (per-artifact failure info)
    """
    ds_name = dataset_dir.name
    expected_outcome = manifest_entry.get("expected_outcome")
    expected_golden = manifest_entry.get("golden", {})

    with tempfile.TemporaryDirectory() as tmp:
        tmp_out = Path(tmp)
        try:
            summary = run_pipeline_deterministic(dataset_dir, tmp_out)
        except Exception as exc:
            return {
                "dataset": ds_name,
                "status": "ERROR",
                "details": [f"pipeline crashed: {exc}"],
            }

        run_folder = Path(summary["run_folder"])
        actual_outcome = summary["outcome"]
        details: list[str] = []

        # Outcome check
        if expected_outcome and actual_outcome != expected_outcome:
            details.append(
                f"outcome: expected {expected_outcome}, got {actual_outcome}"
            )

        # Artifact hash checks
        for run_path, manifest_key in ARTIFACT_MAP:
            actual_file = run_folder / run_path
            if not actual_file.exists():
                details.append(f"{manifest_key}: file not produced by pipeline")
                continue

            expected_info = expected_golden.get(manifest_key, {})
            expected_hash = expected_info.get("sha256", "")
            if not expected_hash:
                details.append(f"{manifest_key}: no expected hash in manifest")
                continue

            actual_hash = sha256_file(actual_file)
            if actual_hash != expected_hash:
                details.append(
                    f"{manifest_key}: HASH MISMATCH\n"
                    f"    expected {expected_hash}\n"
                    f"    got      {actual_hash}"
                )
                # Show diff when verbose
                if verbose:
                    frozen_file = (
                        FROZEN_DIR / "golden" / ds_name / run_path
                    )
                    if frozen_file.exists():
                        if manifest_key.endswith(".csv"):
                            row_diff = diff_csv_first_row(frozen_file, actual_file)
                            if row_diff:
                                details.append(f"    CSV diff: {row_diff}")
                        else:
                            diff_lines = diff_json_files(frozen_file, actual_file, max_lines=5)
                            for dl in diff_lines:
                                details.append(f"    {dl}")

    status = "FAIL" if details else "PASS"
    return {"dataset": ds_name, "status": status, "details": details}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify frozen golden outputs are still reproducible.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Comma-separated list of dataset prefixes to verify (e.g. D1,D3)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Show diffs for mismatched artifacts",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Re-freeze goldens (runs freeze_goldens.py --force) if verification fails",
    )
    args = parser.parse_args()

    frozen_dir = FROZEN_DIR
    manifest_path = frozen_dir / "manifest.json"
    had_failure = False

    # -- Phase 1: spec.lock.json integrity ----------------------------------
    print("Phase 1: spec.lock.json integrity")
    spec_failures = verify_spec_lock(frozen_dir)
    if spec_failures:
        print("  FAIL — spec files have changed since lock was created:")
        for line in spec_failures:
            print(line)
        had_failure = True
    else:
        print("  PASS")

    # -- Phase 2: manifest.json cross-check ---------------------------------
    print("\nPhase 2: manifest.json cross-check")
    meta_failures = verify_manifest_meta(frozen_dir)
    if meta_failures:
        print("  FAIL — manifest metadata inconsistency:")
        for line in meta_failures:
            print(line)
        had_failure = True
    else:
        print("  PASS")

    # -- Phase 3: re-run pipeline and compare --------------------------------
    if not manifest_path.exists():
        print("\nPhase 3: SKIP — manifest.json missing, nothing to verify")
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    # Guard: abort phase 3 if manifest format is wrong
    datasets_field = manifest.get("datasets")
    if not isinstance(datasets_field, list):
        print("\nPhase 3: SKIP — manifest 'datasets' is not a list (wrong format)")
        print("  Re-run:  python scripts/qa/freeze_goldens.py --force")
        sys.exit(1)

    # Build lookup: dataset_id -> manifest entry
    ds_entries: dict[str, dict] = {}
    for entry in datasets_field:
        ds_entries[entry["dataset_id"]] = entry

    ds_filter = [s.strip() for s in args.dataset.split(",")] if args.dataset else None
    datasets = discover_datasets(ds_filter)

    if not datasets:
        print("\nNo datasets found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nPhase 3: re-run pipeline for {len(datasets)} dataset(s)\n")

    pass_count = 0
    fail_count = 0
    error_count = 0
    failed_datasets: list[str] = []

    for ds_dir in datasets:
        ds_name = ds_dir.name
        entry = ds_entries.get(ds_name)
        if entry is None:
            print(f"  SKIP    {ds_name}: not in manifest.json")
            continue

        result = verify_dataset(ds_dir, entry, verbose=args.verbose)
        status = result["status"]

        if status == "PASS":
            print(f"  PASS    {ds_name}")
            pass_count += 1
        elif status == "ERROR":
            print(f"  ERROR   {ds_name}")
            for d in result["details"]:
                print(f"          {d}")
            error_count += 1
            failed_datasets.append(ds_name)
            had_failure = True
        else:
            print(f"  FAIL    {ds_name}")
            for d in result["details"]:
                for line in d.split("\n"):
                    print(f"          {line}")
            fail_count += 1
            failed_datasets.append(ds_name)
            had_failure = True

    # -- Summary -------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"Summary: {pass_count} PASS, {fail_count} FAIL, {error_count} ERROR")
    if failed_datasets:
        print(f"Failed:  {', '.join(failed_datasets)}")
    print(f"{'='*60}")

    # -- --update: re-freeze if there were failures --------------------------
    if had_failure and args.update:
        print("\n--update requested: re-freezing goldens ...")
        freeze_script = REPO_ROOT / "scripts" / "qa" / "freeze_goldens.py"
        cmd = [sys.executable, str(freeze_script), "--force"]
        if args.dataset:
            cmd.extend(["--dataset", args.dataset])
        rc = subprocess.call(cmd)
        if rc != 0:
            print("freeze_goldens.py exited with errors.", file=sys.stderr)
            sys.exit(1)
        print("Goldens re-frozen. Run verify again to confirm.")

    if had_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
