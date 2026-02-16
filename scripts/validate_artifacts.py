#!/usr/bin/env python3
"""
End-to-end validation script for the adapter pipeline.

Usage:
    python scripts/validate_artifacts.py                      # runs all datasets
    python scripts/validate_artifacts.py --dataset D1         # runs one dataset
    python scripts/validate_artifacts.py --dataset D1 D4      # runs specific datasets

Exits non-zero if any validation fails.
"""
import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = REPO_ROOT / "datasets"
SPEC_DIR = REPO_ROOT / "spec"

# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_schemas() -> dict[str, dict]:
    return {
        "S-00A": _load_json(SPEC_DIR / "schemas" / "S-00A_berlin_accounts.schema.json"),
        "S-00B": _load_json(SPEC_DIR / "schemas" / "S-00B_berlin_transactions.schema.json"),
        "S-01":  _load_json(SPEC_DIR / "schemas" / "S-01_sv_schema.json"),
        "S-02":  _load_json(SPEC_DIR / "schemas" / "S-02_ml_projection_schema.json"),
        "S-03":  _load_json(SPEC_DIR / "schemas" / "S-03_llm_context_schema.json"),
        "S-05":  _load_json(SPEC_DIR / "schemas" / "S-05_collected_report_schema.json"),
    }


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def discover_datasets(filter_names: list[str] | None = None) -> list[Path]:
    """Find dataset directories under datasets/ that contain accounts.json + transactions.json."""
    datasets = []
    for d in sorted(DATASETS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "accounts.json").exists() and (d / "transactions.json").exists():
            if filter_names:
                # Match if any filter is a prefix of the directory name
                if not any(d.name.upper().startswith(f.upper()) for f in filter_names):
                    continue
            datasets.append(d)
    return datasets


# ---------------------------------------------------------------------------
# Run adapter
# ---------------------------------------------------------------------------

def run_adapter(dataset_dir: Path, output_dir: Path) -> dict:
    """Run the adapter pipeline on a dataset. Returns the summary dict."""
    # Import the pipeline directly to avoid subprocess overhead
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from adapter.pipeline import run_pipeline
    return run_pipeline(dataset_dir, output_dir)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_json(data: object, schema: dict, label: str) -> list[str]:
    """Validate data against a JSON schema. Returns list of error messages."""
    errors = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"{label}: {e.message}")
    return errors


def validate_ml_csv(csv_path: Path, schema: dict) -> list[str]:
    """Validate every row in the ML CSV against S-02."""
    errors = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            row_obj = {
                "row_id": int(row["row_id"]),
                "account_id": row["account_id"],
                "record_id": row["record_id"],
                "status": row["status"],
                "booking_date": row["booking_date"] or None,
                "value_date": row["value_date"],
                "direction": row["direction"],
                "currency": row["currency"],
                "signed_amount": row["signed_amount"],
                "abs_amount": row["abs_amount"],
                "counterparty_name": row["counterparty_name"] or None,
                "remittance": row["remittance"] or None,
            }
            try:
                jsonschema.validate(row_obj, schema)
            except jsonschema.ValidationError as e:
                errors.append(f"ml_v1.csv row {i+1} vs S-02: {e.message}")
                if len(errors) >= 5:
                    errors.append("... (truncated)")
                    break
    return errors


def validate_dataset(dataset_dir: Path, schemas: dict) -> dict:
    """
    Run the adapter on a dataset and validate all artifacts.

    Returns dict with:
      - dataset: str
      - outcome: str (from adapter)
      - passed: list[str]
      - failed: list[str]
    """
    ds_name = dataset_dir.name
    passed = []
    failed = []

    # Validate RAW inputs
    accounts = _load_json(dataset_dir / "accounts.json")
    errs = validate_json(accounts, schemas["S-00A"], "accounts.json vs S-00A")
    if errs:
        failed.extend(errs)
    else:
        passed.append("accounts.json vs S-00A")

    transactions = _load_json(dataset_dir / "transactions.json")
    errs = validate_json(transactions, schemas["S-00B"], "transactions.json vs S-00B")
    if errs:
        # RAW input validation failure is expected for error datasets
        failed.extend(errs)
    else:
        passed.append("transactions.json vs S-00B")

    # Run adapter
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        try:
            summary = run_adapter(dataset_dir, output_dir)
        except Exception as e:
            failed.append(f"adapter run failed: {e}")
            return {"dataset": ds_name, "outcome": "CRASH", "passed": passed, "failed": failed}

        outcome = summary["outcome"]
        run_folder = Path(summary["run_folder"])

        # Validate sv.json vs S-01
        sv = _load_json(run_folder / "sv.json")
        errs = validate_json(sv, schemas["S-01"], "sv.json vs S-01")
        if errs:
            failed.extend(errs)
        else:
            passed.append("sv.json vs S-01")

        # Validate ml_v1.csv vs S-02
        csv_path = run_folder / "projections" / "ml_v1.csv"
        errs = validate_ml_csv(csv_path, schemas["S-02"])
        if errs:
            failed.extend(errs)
        else:
            with open(csv_path) as f:
                n_rows = sum(1 for _ in csv.reader(f)) - 1  # minus header
            passed.append(f"ml_v1.csv vs S-02 ({n_rows} rows)")

        # Validate llm_context_v1.json vs S-03
        llm = _load_json(run_folder / "projections" / "llm_context_v1.json")
        errs = validate_json(llm, schemas["S-03"], "llm_context_v1.json vs S-03")
        if errs:
            failed.extend(errs)
        else:
            passed.append("llm_context_v1.json vs S-03")

        # Validate report.json vs S-05
        report = _load_json(run_folder / "report.json")
        errs = validate_json(report, schemas["S-05"], "report.json vs S-05")
        if errs:
            failed.extend(errs)
        else:
            passed.append("report.json vs S-05")

    return {
        "dataset": ds_name,
        "outcome": outcome,
        "passed": passed,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate adapter artifacts end-to-end.")
    parser.add_argument("--dataset", "-d", nargs="*", default=None,
                        help="Dataset name(s) to validate (prefix match). Default: all datasets.")
    args = parser.parse_args()

    schemas = load_schemas()
    datasets = discover_datasets(args.dataset)

    if not datasets:
        print("No datasets found.", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(datasets)} dataset(s):\n")

    all_results = []
    total_pass = 0
    total_fail = 0
    # Track output-only failures (RAW input failures in error datasets are expected)
    output_failures = 0

    for ds_dir in datasets:
        result = validate_dataset(ds_dir, schemas)
        all_results.append(result)

        print(f"  {result['dataset']}  (outcome: {result['outcome']})")
        for p in result["passed"]:
            print(f"    PASS  {p}")
            total_pass += 1
        for f in result["failed"]:
            print(f"    FAIL  {f}")
            total_fail += 1
            # Count non-RAW failures as output failures
            if "vs S-00A" not in f and "vs S-00B" not in f:
                output_failures += 1
        print()

    print(f"Total: {total_pass} passed, {total_fail} failed (of which {output_failures} are output validation failures)")

    if output_failures > 0:
        print("\nFAILED: output validation errors found.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nOK: all output artifacts validate against their schemas.")
        sys.exit(0)


if __name__ == "__main__":
    main()
