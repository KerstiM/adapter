#!/usr/bin/env python3
"""
Validate that every issue code in a report.json is registered in the
Error Catalog (spec/rulesets/error_catalog.yaml).

Usage:
    python scripts/validate_error_catalog.py <report.json> [<report2.json> ...]
    python scripts/validate_error_catalog.py --all-golden

Exits non-zero if any issue code is missing from the catalog.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "spec" / "rulesets" / "error_catalog.yaml"


def load_catalog_codes(catalog_path: Path) -> set[str]:
    """Return the set of registered issue codes from the error catalog."""
    with open(catalog_path, encoding="utf-8") as f:
        catalog = yaml.safe_load(f)
    return {entry["code"] for entry in catalog.get("entries", [])}


def extract_issue_codes(report_path: Path) -> list[str]:
    """Return the list of issue codes found in a report.json file."""
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    return [issue["code"] for issue in report.get("issues", []) if "code" in issue]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check that report.json issue codes are registered in the error catalog.",
    )
    parser.add_argument(
        "reports", nargs="*", type=Path,
        help="One or more report.json files to validate.",
    )
    parser.add_argument(
        "--all-golden", action="store_true",
        help="Validate all report.json files under golden/.",
    )
    args = parser.parse_args()

    report_paths: list[Path] = list(args.reports)
    if args.all_golden:
        golden_dir = REPO_ROOT / "golden"
        if golden_dir.is_dir():
            report_paths.extend(sorted(golden_dir.glob("*/report.json")))

    if not report_paths:
        print("No report files specified. Use positional args or --all-golden.", file=sys.stderr)
        sys.exit(2)

    if not CATALOG_PATH.exists():
        print(f"Error catalog not found: {CATALOG_PATH}", file=sys.stderr)
        sys.exit(2)

    registered = load_catalog_codes(CATALOG_PATH)
    print(f"Catalog: {len(registered)} registered code(s)")

    all_missing: dict[str, list[str]] = {}  # code -> list of report files

    for rpath in report_paths:
        if not rpath.exists():
            print(f"  SKIP  {rpath} (file not found)")
            continue
        codes = extract_issue_codes(rpath)
        missing = sorted(set(c for c in codes if c not in registered))
        label = rpath.relative_to(REPO_ROOT) if rpath.is_relative_to(REPO_ROOT) else rpath
        if codes:
            print(f"  {label}: {len(codes)} issue(s), {len(missing)} unregistered")
        else:
            print(f"  {label}: 0 issues (nothing to check)")
        for code in missing:
            all_missing.setdefault(code, []).append(str(label))

    if all_missing:
        print(f"\nFAILED: {len(all_missing)} unregistered issue code(s):")
        for code, files in sorted(all_missing.items()):
            print(f"  {code}  (in {', '.join(files)})")
        print("\nAdd missing codes to spec/rulesets/error_catalog.yaml to fix.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nOK: all issue codes are registered in the error catalog.")
        sys.exit(0)


if __name__ == "__main__":
    main()
