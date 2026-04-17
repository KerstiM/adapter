#!/usr/bin/env python3
"""
Freeze golden outputs into a versioned manifest for regression testing.

Reads golden/<dataset_id>/ artifacts, computes SHA-256 hashes, and writes
frozen/<version>/manifest.json with the following structure:

    {
      "frozen_version": "v1.0.0",
      "spec_lock_sha256": "<sha256(spec.lock.json)>",
      "datasets": [
        {
          "dataset_id": "D1_synth_valid_small",
          "expected_outcome": "SUCCESS",
          "golden": {
            "sv.json":              {"sha256": "..."},
            "ml_v1.csv":            {"sha256": "..."},
            "llm_context_v1.json":  {"sha256": "..."},
            "report.json":          {"sha256": "..."}
          }
        }
      ]
    }

Usage:
    python scripts/freeze_goldens.py                        # default v1.0.0
    python scripts/freeze_goldens.py --version v1.1.0       # custom version
    python scripts/freeze_goldens.py --only D1,D3           # specific datasets
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Golden artifact files and their paths relative to golden/<dataset_id>/
GOLDEN_FILES = {
    "sv.json":             Path("sv.json"),
    "ml_v1.csv":           Path("projections") / "ml_v1.csv",
    "llm_context_v1.json": Path("projections") / "llm_context_v1.json",
    "report.json":         Path("report.json"),
}

# Fallback mapping: dataset_id -> expected outcome.
# Used only when the README.md cannot be parsed.
EXPECTED_OUTCOME_FALLBACK = {
    "D1_synth_valid_small":     "SUCCESS",
    "D2_synth_mixed_large":     "PARTIAL_SUCCESS",
    "D3_synth_valid_seed42":     "SUCCESS",
    "D4_synth_errors_seed42":    "FAILED",
    "D5_synth_edges_seed99":     "SUCCESS",
    "D6_synth_dupes_seed99":     "PARTIAL_SUCCESS",
    "D7_standing_orders_seed77": "PARTIAL_SUCCESS",
    "D8_load_test_10k_seed88":   "SUCCESS",
    "D9_synth_perf_seed9":       "SUCCESS",
    "D10_real_deid_oct16":       "PARTIAL_SUCCESS",
    "D11_real_deid_2024":        "SUCCESS",
}


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_expected_outcome(dataset_dir: Path) -> str | None:
    """Try to extract 'Expected outcome' from dataset README.md."""
    readme = dataset_dir / "README.md"
    if not readme.exists():
        return None
    text = readme.read_text(encoding="utf-8")
    # Match table row:  | Expected outcome | VALUE |
    m = re.search(
        r"\|\s*Expected outcome\s*\|\s*(\w+)\s*\|",
        text,
        re.IGNORECASE,
    )
    return m.group(1).upper() if m else None


def discover_golden_datasets(
    golden_dir: Path,
    only: list[str] | None = None,
) -> list[str]:
    """Return sorted list of dataset_ids that have golden outputs."""
    datasets = []
    for d in sorted(golden_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if only and not any(d.name.upper().startswith(f.upper()) for f in only):
            continue
        datasets.append(d.name)
    return datasets


def build_manifest(
    version: str,
    golden_dir: Path,
    datasets_dir: Path,
    frozen_dir: Path,
    only: list[str] | None = None,
) -> dict:
    """Build the manifest dictionary."""
    spec_lock = frozen_dir / "spec.lock.json"
    if not spec_lock.exists():
        print(f"ERROR: {spec_lock} not found", file=sys.stderr)
        sys.exit(1)

    spec_lock_sha = sha256_file(spec_lock)
    dataset_ids = discover_golden_datasets(golden_dir, only)

    if not dataset_ids:
        print("No golden datasets found.", file=sys.stderr)
        sys.exit(1)

    datasets = []
    for ds_id in dataset_ids:
        ds_golden = golden_dir / ds_id

        # Determine expected outcome: README first, then fallback mapping
        outcome = parse_expected_outcome(datasets_dir / ds_id)
        if outcome is None:
            outcome = EXPECTED_OUTCOME_FALLBACK.get(ds_id)
        if outcome is None:
            print(f"  WARN  {ds_id}: no expected_outcome found, using UNKNOWN")
            outcome = "UNKNOWN"

        # Compute hashes for each golden artifact
        golden_hashes = {}
        missing = []
        for name, rel_path in GOLDEN_FILES.items():
            fpath = ds_golden / rel_path
            if not fpath.exists():
                missing.append(name)
                continue
            golden_hashes[name] = {"sha256": sha256_file(fpath)}

        if missing:
            print(f"  WARN  {ds_id}: missing golden files: {', '.join(missing)}")

        datasets.append({
            "dataset_id": ds_id,
            "expected_outcome": outcome,
            "golden": golden_hashes,
        })

    return {
        "frozen_version": version,
        "spec_lock_sha256": spec_lock_sha,
        "datasets": datasets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze golden outputs into a versioned manifest.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="v1.0.0",
        help="Frozen version tag (default: v1.0.0)",
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=REPO_ROOT / "golden",
        help="Directory containing golden outputs (default: golden)",
    )
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=REPO_ROOT / "datasets",
        help="Directory containing dataset folders with README.md (default: datasets)",
    )
    parser.add_argument(
        "--frozen-dir",
        type=Path,
        default=None,
        help="Frozen version directory (default: frozen/<version>)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of dataset prefixes (e.g. D1,D3)",
    )
    args = parser.parse_args()

    frozen_dir = args.frozen_dir or (REPO_ROOT / "frozen" / args.version)
    only = [s.strip() for s in args.only.split(",")] if args.only else None

    manifest = build_manifest(
        version=args.version,
        golden_dir=args.golden_dir,
        datasets_dir=args.datasets_dir,
        frozen_dir=frozen_dir,
        only=only,
    )

    manifest_path = frozen_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=False, ensure_ascii=False)
        f.write("\n")

    n = len(manifest["datasets"])
    print(f"Wrote {manifest_path} ({n} dataset(s), frozen_version={args.version})")


if __name__ == "__main__":
    main()
