#!/usr/bin/env python3
"""
End-to-end validation script for the adapter pipeline.

Runs the adapter on one or more dataset folders under datasets/ and validates
every artifact against its JSON schema:

  S-00A  accounts.json          (required input)
  S-00B  transactions*.json     (required input — one or more report files)
  S-00C  standing_orders.json   (optional input — skipped with note when absent)
  S-01   sv.json                (output)
  S-02   ml_v1.csv              (output, row-by-row)
  S-03   llm_context_v1.json    (output)
  S-05   report.json            (output — skipped with note when absent)

Usage:
    python scripts/validate_artifacts.py                      # all datasets
    python scripts/validate_artifacts.py --dataset D1         # one dataset
    python scripts/validate_artifacts.py --dataset D1 D4      # specific datasets

Exits non-zero if any validation error is found.
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
    schemas: dict[str, dict] = {}
    mapping = {
        "S-00A": "S-00A_berlin_accounts.schema.json",
        "S-00B": "S-00B_berlin_transactions.schema.json",
        "S-00C": "S-00C_berlin_standing_orders.schema.json",
        "S-01":  "S-01_sv_schema.json",
        "S-02":  "S-02_ml_projection_schema.json",
        "S-03":  "S-03_llm_context_schema.json",
        "S-05":  "S-05_collected_report_schema.json",
    }
    for key, filename in mapping.items():
        schema_path = SPEC_DIR / "schemas" / filename
        if schema_path.exists():
            schemas[key] = _load_json(schema_path)
        # If schema file doesn't exist we simply won't have it in the dict
    return schemas


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def _find_transaction_report_files(dataset_dir: Path) -> list[Path]:
    """Find all transactions*.json files in a dataset, excluding transactions_download.json.

    Sorted for determinism.
    """
    return sorted(
        p for p in dataset_dir.glob("transactions*.json")
        if p.name != "transactions_download.json"
    )


def discover_datasets(filter_names: list[str] | None = None) -> list[Path]:
    """Find dataset directories under datasets/ that contain accounts.json + at least one report file."""
    datasets = []
    for d in sorted(DATASETS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "accounts.json").exists() and _find_transaction_report_files(d):
            if filter_names:
                if not any(d.name.upper().startswith(f.upper()) for f in filter_names):
                    continue
            datasets.append(d)
    return datasets


# ---------------------------------------------------------------------------
# Run adapter
# ---------------------------------------------------------------------------

def run_adapter(dataset_dir: Path, output_dir: Path) -> dict:
    """Run the adapter pipeline on a dataset. Returns the summary dict."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from adapter.pipeline import run_pipeline
    return run_pipeline(dataset_dir, output_dir)


# ---------------------------------------------------------------------------
# Validation helpers
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


# ---------------------------------------------------------------------------
# Per-dataset validation
# ---------------------------------------------------------------------------

def validate_dataset(dataset_dir: Path, schemas: dict) -> dict:
    """
    Run the adapter on a dataset and validate all artifacts.

    Returns dict with:
      - dataset: str
      - outcome: str (from adapter)
      - passed: list[str]
      - failed: list[str]
      - skipped: list[str]
    """
    ds_name = dataset_dir.name
    passed = []
    failed = []
    skipped = []

    # ---- S-00A  accounts.json (required) ----
    accounts = _load_json(dataset_dir / "accounts.json")
    errs = validate_json(accounts, schemas["S-00A"], "accounts.json vs S-00A")
    if errs:
        failed.extend(errs)
    else:
        passed.append("S-00A  accounts.json")

    # ---- S-00B  transaction report files (required, one or more) ----
    tx_report_files = _find_transaction_report_files(dataset_dir)
    if not tx_report_files:
        failed.append("S-00B  no transactions*.json report file found")
    for tx_path in tx_report_files:
        tx_data = _load_json(tx_path)
        errs = validate_json(tx_data, schemas["S-00B"], f"{tx_path.name} vs S-00B")
        if errs:
            failed.extend(errs)
        else:
            passed.append(f"S-00B  {tx_path.name}")

    # ---- S-00C  standing_orders.json (optional) ----
    so_path = dataset_dir / "standing_orders.json"
    if so_path.exists():
        if "S-00C" in schemas:
            so_data = _load_json(so_path)
            errs = validate_json(so_data, schemas["S-00C"], "standing_orders.json vs S-00C")
            if errs:
                failed.extend(errs)
            else:
                passed.append("S-00C  standing_orders.json")
        else:
            skipped.append("S-00C  standing_orders.json — schema file not found, skipping")
    else:
        skipped.append("S-00C  standing_orders.json — file not present in dataset, skipping")

    # ---- Run the adapter ----
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        try:
            summary = run_adapter(dataset_dir, output_dir)
        except Exception as e:
            failed.append(f"adapter run failed: {e}")
            return {"dataset": ds_name, "outcome": "CRASH", "passed": passed, "failed": failed, "skipped": skipped}

        outcome = summary["outcome"]
        run_folder = Path(summary["run_folder"])

        # ---- S-01  sv.json ----
        sv_path = run_folder / "sv.json"
        sv = _load_json(sv_path)
        errs = validate_json(sv, schemas["S-01"], "sv.json vs S-01")
        if errs:
            failed.extend(errs)
        else:
            n_tx = len(sv.get("transactions", []))
            passed.append(f"S-01   sv.json ({n_tx} transactions)")

        # ---- S-02  ml_v1.csv (row-by-row) ----
        csv_path = run_folder / "projections" / "ml_v1.csv"
        errs = validate_ml_csv(csv_path, schemas["S-02"])
        if errs:
            failed.extend(errs)
        else:
            with open(csv_path) as f:
                n_rows = sum(1 for _ in csv.reader(f)) - 1
            passed.append(f"S-02   ml_v1.csv ({n_rows} rows)")

        # ---- S-03  llm_context_v1.json ----
        llm_path = run_folder / "projections" / "llm_context_v1.json"
        llm = _load_json(llm_path)
        errs = validate_json(llm, schemas["S-03"], "llm_context_v1.json vs S-03")
        if errs:
            failed.extend(errs)
        else:
            passed.append("S-03   llm_context_v1.json")

        # ---- S-05  report.json (skip if not present or schema not wired) ----
        report_path = run_folder / "report.json"
        if "S-05" not in schemas:
            skipped.append("S-05   report.json — schema not wired in spec/, skipping")
        elif not report_path.exists():
            skipped.append("S-05   report.json — not produced by adapter, skipping")
        else:
            report = _load_json(report_path)
            errs = validate_json(report, schemas["S-05"], "report.json vs S-05")
            if errs:
                failed.extend(errs)
            else:
                passed.append("S-05   report.json")

    return {
        "dataset": ds_name,
        "outcome": outcome,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

RAW_SCHEMAS = {"S-00A", "S-00B", "S-00C"}


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

    total_pass = 0
    total_fail = 0
    total_skip = 0
    output_failures = 0

    for ds_dir in datasets:
        result = validate_dataset(ds_dir, schemas)

        print(f"  {result['dataset']}  (adapter outcome: {result['outcome']})")
        for p in result["passed"]:
            print(f"    PASS  {p}")
            total_pass += 1
        for s in result["skipped"]:
            print(f"    SKIP  {s}")
            total_skip += 1
        for f in result["failed"]:
            print(f"    FAIL  {f}")
            total_fail += 1
            # RAW input failures are expected for error-injection datasets
            if not any(tag in f for tag in ("vs S-00A", "vs S-00B", "vs S-00C")):
                output_failures += 1
        print()

    print(f"Total: {total_pass} passed, {total_skip} skipped, {total_fail} failed "
          f"(of which {output_failures} are output validation failures)")

    if output_failures > 0:
        print("\nFAILED: output validation errors found.", file=sys.stderr)
        sys.exit(1)
    else:
        print("\nOK: all output artifacts validate against their schemas.")
        sys.exit(0)


if __name__ == "__main__":
    main()
