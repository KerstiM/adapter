#!/usr/bin/env python3
"""
End-to-end QA entrypoint: verifies consistency of specs, datasets, outputs,
and goldens in a single run.

Usage:
    python scripts/qa/run_full_qa.py                          # all datasets
    python scripts/qa/run_full_qa.py --dataset D1             # one dataset
    python scripts/qa/run_full_qa.py --dataset D1,D2          # specific
    python scripts/qa/run_full_qa.py --skip-golden            # skip golden comparison
    python scripts/qa/run_full_qa.py --fast                   # only D1 + D3

Exit code 0 if all checks pass, else 1.
"""

import argparse
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

import jsonschema
import yaml

# ---------------------------------------------------------------------------
# Bootstrap: ensure repo-relative imports work regardless of cwd
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from _utils import (
    ARTIFACT_MAP,
    DATASETS_DIR,
    FROZEN_DIR,
    FROZEN_VERSION,
    GOLDEN_CREATED_AT,
    REPO_ROOT,
    SPEC_DIR,
    STAGE_ORDER,
    diff_csv_first_row,
    diff_json_files,
    discover_datasets,
    find_transaction_files,
    load_json,
    load_yaml,
    run_pipeline_deterministic,
    sha256_bytes,
    sha256_file,
)

# ═══════════════════════════════════════════════════════════════════════════
# Section 1: SPEC INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════


def _version_from_file(path: Path) -> str | None:
    """Extract top-level 'version' from a JSON or YAML file."""
    try:
        if path.suffix == ".json":
            data = load_json(path)
        else:
            data = load_yaml(path)
        if isinstance(data, dict):
            return data.get("version")
    except Exception:
        pass
    return None


def check_spec_integrity() -> tuple[bool, list[str]]:
    """Verify spec profile references and artifact versions.

    Returns (passed, messages).
    """
    failures: list[str] = []
    profile_path = SPEC_DIR / "profiles" / "default.yaml"

    if not profile_path.exists():
        return False, ["default.yaml not found"]

    profile = load_yaml(profile_path)

    # Profile must have id and version
    if not profile.get("id"):
        failures.append("profile missing 'id'")
    if not profile.get("version"):
        failures.append("profile missing 'version'")

    counts = {"schemas": 0, "contracts": 0, "rulesets": 0}

    for section in ("schemas", "contracts", "rulesets"):
        entries = profile.get(section, {})
        if not isinstance(entries, dict):
            continue
        for artifact_id, rel_path in sorted(entries.items()):
            counts[section] += 1
            full_path = REPO_ROOT / rel_path

            if not full_path.exists():
                failures.append(f"{artifact_id}: file missing -> {rel_path}")
                continue

            version = _version_from_file(full_path)
            if version is None:
                failures.append(f"{artifact_id}: missing top-level 'version' in {rel_path}")

    summary = (
        f"{counts['schemas']} schemas, "
        f"{counts['contracts']} contracts, "
        f"{counts['rulesets']} rulesets"
    )

    passed = len(failures) == 0
    msgs = [summary]
    if failures:
        msgs.extend(failures)
    return passed, msgs


# ═══════════════════════════════════════════════════════════════════════════
# Section 2: DATASET INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════


def _load_schemas() -> dict[str, dict]:
    """Load all spec schemas by ID."""
    mapping = {
        "S-00A": "S-00A_berlin_accounts.schema.json",
        "S-00B": "S-00B_berlin_transactions.schema.json",
        "S-00C": "S-00C_berlin_standing_orders.schema.json",
        "S-01": "S-01_sv_schema.json",
        "S-02": "S-02_ml_projection_schema.json",
        "S-03": "S-03_llm_context_schema.json",
        "S-05": "S-05_collected_report_schema.json",
    }
    schemas: dict[str, dict] = {}
    for key, filename in mapping.items():
        p = SPEC_DIR / "schemas" / filename
        if p.exists():
            schemas[key] = load_json(p)
    return schemas


def _validate_json(data: object, schema: dict, label: str) -> list[str]:
    errors: list[str] = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"{label}: {e.message}")
    return errors


CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
AMOUNT_RE = re.compile(r"^-?\d+(\.\d{1,3})?$")


def _semantic_checks_transactions(
    tx_data: dict, accounts_ibans: set[str], tx_file_name: str,
) -> list[str]:
    """Semantic checks beyond schema: IBAN cross-ref, pending bookingDate, currency/amount formats."""
    errors: list[str] = []

    # account.iban must exist in accounts.json
    report_iban = (tx_data.get("account") or {}).get("iban")
    if not report_iban:
        errors.append(f"{tx_file_name}: missing account.iban")
    elif report_iban not in accounts_ibans:
        errors.append(f"{tx_file_name}: account.iban '{report_iban}' not found in accounts.json")

    tx_obj = tx_data.get("transactions") or {}

    # Check pending transactions must not include bookingDate
    for i, ptx in enumerate(tx_obj.get("pending", [])):
        if "bookingDate" in ptx:
            errors.append(
                f"{tx_file_name}: pending[{i}] has bookingDate (must be absent for pending)"
            )

    # Currency and amount format checks across all statuses
    for status_key in ("booked", "pending", "information"):
        for i, raw_tx in enumerate(tx_obj.get(status_key, [])):
            amt_obj = raw_tx.get("transactionAmount") or {}
            currency = amt_obj.get("currency", "")
            amount = amt_obj.get("amount", "")

            if currency and not CURRENCY_RE.match(currency):
                errors.append(
                    f"{tx_file_name}: {status_key}[{i}] currency '{currency}' "
                    f"does not match ^[A-Z]{{3}}$"
                )
            if amount and not AMOUNT_RE.match(amount):
                errors.append(
                    f"{tx_file_name}: {status_key}[{i}] amount '{amount}' "
                    f"does not match ^-?\\d+(\\.\\d{{1,3}})?$"
                )

    return errors


def validate_dataset_inputs(dataset_dir: Path, schemas: dict) -> dict:
    """Validate a single dataset's input files.

    Returns dict with: dataset, passed, failed, skipped.
    """
    ds_name = dataset_dir.name
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []

    # --- accounts.json (S-00A) ---
    acct_path = dataset_dir / "accounts.json"
    accounts_data = load_json(acct_path)
    errs = _validate_json(accounts_data, schemas["S-00A"], "accounts.json vs S-00A")
    if errs:
        failed.extend(errs)
    else:
        passed.append("S-00A  accounts.json")

    # Collect IBANs for cross-checking
    accounts_ibans: set[str] = set()
    for acct in accounts_data.get("accounts", []):
        iban = acct.get("iban")
        if iban:
            accounts_ibans.add(iban)

    # --- transactions*.json (S-00B) ---
    tx_files = find_transaction_files(dataset_dir)
    if not tx_files:
        failed.append("S-00B: no transactions*.json found")
    for tx_path in tx_files:
        tx_data = load_json(tx_path)
        errs = _validate_json(tx_data, schemas["S-00B"], f"{tx_path.name} vs S-00B")
        if errs:
            failed.extend(errs)
        else:
            passed.append(f"S-00B  {tx_path.name}")

        # Semantic checks
        sem_errs = _semantic_checks_transactions(tx_data, accounts_ibans, tx_path.name)
        if sem_errs:
            failed.extend(sem_errs)

    # --- standing_orders.json (S-00C, optional) ---
    so_path = dataset_dir / "standing_orders.json"
    if so_path.exists():
        if "S-00C" in schemas:
            so_data = load_json(so_path)
            errs = _validate_json(so_data, schemas["S-00C"], "standing_orders.json vs S-00C")
            if errs:
                failed.extend(errs)
            else:
                passed.append("S-00C  standing_orders.json")
        else:
            skipped.append("S-00C schema not available")
    else:
        skipped.append("standing_orders.json not present")

    return {
        "dataset": ds_name,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 3: PIPELINE OUTPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════


def _validate_ml_csv(csv_path: Path, schema: dict) -> list[str]:
    """Validate ML CSV rows against S-02 schema."""
    errors: list[str] = []
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
                errors.append(f"ml_v1.csv row {i + 1} vs S-02: {e.message}")
                if len(errors) >= 5:
                    errors.append("... (truncated)")
                    break
    return errors


def _count_csv_rows(csv_path: Path) -> int:
    """Count data rows in CSV (excluding header)."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def _cross_artifact_checks(run_folder: Path, schemas: dict) -> list[str]:
    """Cross-artifact consistency checks between report, SV, ML CSV, and LLM context."""
    errors: list[str] = []

    sv = load_json(run_folder / "sv.json")
    report = load_json(run_folder / "report.json")
    ml_path = run_folder / "projections" / "ml_v1.csv"
    llm_path = run_folder / "projections" / "llm_context_v1.json"
    llm = load_json(llm_path)

    counts = report.get("summary", {}).get("counts", {})

    # transactions_emitted_sv == len(sv.transactions)
    sv_tx_count = len(sv.get("transactions", []))
    reported_emitted = counts.get("transactions_emitted_sv", -1)
    if reported_emitted != sv_tx_count:
        errors.append(
            f"report.counts.transactions_emitted_sv ({reported_emitted}) "
            f"!= len(sv.transactions) ({sv_tx_count})"
        )

    # ml_rows == number of rows in ml_v1.csv (excluding header)
    actual_ml_rows = _count_csv_rows(ml_path)
    reported_ml_rows = counts.get("ml_rows", -1)
    if reported_ml_rows != actual_ml_rows:
        errors.append(
            f"report.counts.ml_rows ({reported_ml_rows}) "
            f"!= actual CSV rows ({actual_ml_rows})"
        )

    # llm_contexts count
    if isinstance(llm, list):
        actual_llm_contexts = len(llm)
    else:
        actual_llm_contexts = 1
    reported_llm = counts.get("llm_contexts", -1)
    if reported_llm != actual_llm_contexts:
        errors.append(
            f"report.counts.llm_contexts ({reported_llm}) "
            f"!= actual LLM contexts ({actual_llm_contexts})"
        )

    # ML rows should be only BOOKED+PENDING and correspond to SV by record_id
    sv_bp_record_ids = set()
    for tx in sv.get("transactions", []):
        if tx.get("status") in ("BOOKED", "PENDING"):
            sv_bp_record_ids.add(tx["record_id"])

    ml_record_ids = set()
    ml_statuses = set()
    with open(ml_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ml_record_ids.add(row["record_id"])
            ml_statuses.add(row["status"])

    bad_statuses = ml_statuses - {"BOOKED", "PENDING"}
    if bad_statuses:
        errors.append(f"ML CSV contains non-BOOKED/PENDING statuses: {bad_statuses}")

    orphan_ml = ml_record_ids - sv_bp_record_ids
    if orphan_ml:
        errors.append(
            f"ML CSV has {len(orphan_ml)} record_ids not in SV BOOKED/PENDING"
        )

    # Stage log is in correct order and stages exist
    stage_log = report.get("summary", {}).get("by_stage", [])
    if isinstance(stage_log, list):
        actual_stages = [s.get("stage") for s in stage_log]
        if actual_stages != STAGE_ORDER:
            errors.append(
                f"Stage log order mismatch: got {actual_stages}, "
                f"expected {STAGE_ORDER}"
            )

    return errors


def validate_pipeline_outputs(dataset_dir: Path, schemas: dict) -> dict:
    """Run pipeline and validate outputs for a single dataset.

    Returns dict with: dataset, outcome, passed, failed.
    """
    ds_name = dataset_dir.name
    passed: list[str] = []
    failed: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        try:
            summary = run_pipeline_deterministic(dataset_dir, output_dir)
        except Exception as e:
            return {
                "dataset": ds_name,
                "outcome": "CRASH",
                "passed": passed,
                "failed": [f"pipeline crashed: {e}"],
            }

        outcome = summary["outcome"]
        run_folder = Path(summary["run_folder"])

        # --- S-01: sv.json ---
        sv_path = run_folder / "sv.json"
        sv = load_json(sv_path)
        errs = _validate_json(sv, schemas["S-01"], "sv.json vs S-01")
        if errs:
            failed.extend(errs)
        else:
            passed.append(f"S-01  sv.json ({len(sv.get('transactions', []))} tx)")

        # --- S-02: ml_v1.csv (row-by-row) ---
        csv_path = run_folder / "projections" / "ml_v1.csv"
        errs = _validate_ml_csv(csv_path, schemas["S-02"])
        if errs:
            failed.extend(errs)
        else:
            n = _count_csv_rows(csv_path)
            passed.append(f"S-02  ml_v1.csv ({n} rows)")

        # --- S-03: llm_context_v1.json ---
        llm_path = run_folder / "projections" / "llm_context_v1.json"
        llm = load_json(llm_path)
        errs = _validate_json(llm, schemas["S-03"], "llm_context_v1.json vs S-03")
        if errs:
            failed.extend(errs)
        else:
            passed.append("S-03  llm_context_v1.json")

        # --- S-05: report.json ---
        report_path = run_folder / "report.json"
        if report_path.exists() and "S-05" in schemas:
            report_data = load_json(report_path)
            errs = _validate_json(report_data, schemas["S-05"], "report.json vs S-05")
            if errs:
                failed.extend(errs)
            else:
                passed.append("S-05  report.json")

        # --- Cross-artifact consistency ---
        errs = _cross_artifact_checks(run_folder, schemas)
        if errs:
            failed.extend(errs)
        else:
            passed.append("cross-artifact consistency")

    return {
        "dataset": ds_name,
        "outcome": outcome,
        "passed": passed,
        "failed": failed,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section 4: GOLDEN SNAPSHOT VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


def _golden_path_for_artifact(ds_name: str, manifest_key: str) -> Path:
    """Map manifest artifact key to its frozen golden file path."""
    if manifest_key == "sv.json":
        return FROZEN_DIR / "golden" / ds_name / "sv.json"
    elif manifest_key == "report.json":
        return FROZEN_DIR / "golden" / ds_name / "report.json"
    elif manifest_key == "ml_v1.csv":
        return FROZEN_DIR / "golden" / ds_name / "projections" / "ml_v1.csv"
    elif manifest_key == "llm_context_v1.json":
        return FROZEN_DIR / "golden" / ds_name / "projections" / "llm_context_v1.json"
    return FROZEN_DIR / "golden" / ds_name / manifest_key


def verify_goldens(datasets: list[Path]) -> tuple[bool, list[str]]:
    """Compare pipeline outputs against frozen golden snapshots.

    Returns (passed, messages).
    """
    manifest_path = FROZEN_DIR / "manifest.json"
    if not manifest_path.exists():
        return False, ["manifest.json not found — run freeze_goldens.py first"]

    manifest = load_json(manifest_path)
    ds_entries: dict[str, dict] = {}
    for entry in manifest.get("datasets", []):
        ds_entries[entry["dataset_id"]] = entry

    all_msgs: list[str] = []
    any_fail = False

    for ds_dir in datasets:
        ds_name = ds_dir.name
        entry = ds_entries.get(ds_name)
        if entry is None:
            all_msgs.append(f"  SKIP  {ds_name}: not in manifest")
            continue

        expected_golden = entry.get("golden", {})
        ds_fails: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            try:
                summary = run_pipeline_deterministic(ds_dir, output_dir)
            except Exception as e:
                all_msgs.append(f"  ERROR {ds_name}: pipeline crashed: {e}")
                any_fail = True
                continue

            run_folder = Path(summary["run_folder"])

            for run_path, manifest_key in ARTIFACT_MAP:
                actual_file = run_folder / run_path
                if not actual_file.exists():
                    ds_fails.append(f"{manifest_key}: not produced")
                    continue

                expected_info = expected_golden.get(manifest_key, {})
                expected_hash = expected_info.get("sha256", "")
                if not expected_hash:
                    ds_fails.append(f"{manifest_key}: no expected hash in manifest")
                    continue

                actual_hash = sha256_file(actual_file)
                if actual_hash != expected_hash:
                    ds_fails.append(
                        f"{manifest_key}: HASH MISMATCH "
                        f"(expected {expected_hash[:12]}... got {actual_hash[:12]}...)"
                    )
                    # Show diff snippet
                    golden_file = _golden_path_for_artifact(ds_name, manifest_key)
                    if golden_file.exists():
                        if manifest_key.endswith(".csv"):
                            row_diff = diff_csv_first_row(golden_file, actual_file)
                            if row_diff:
                                ds_fails.append(f"  CSV diff: {row_diff}")
                        else:
                            diff_lines = diff_json_files(golden_file, actual_file, max_lines=5)
                            for dl in diff_lines:
                                ds_fails.append(f"  {dl}")

        if ds_fails:
            all_msgs.append(f"  FAIL  {ds_name}")
            for f in ds_fails:
                all_msgs.append(f"    {f}")
            any_fail = True
        else:
            all_msgs.append(f"  PASS  {ds_name}")

    return not any_fail, all_msgs


# ═══════════════════════════════════════════════════════════════════════════
# Section 5: DETERMINISM SMOKE CHECK
# ═══════════════════════════════════════════════════════════════════════════


def check_determinism(dataset_dir: Path) -> tuple[bool, list[str]]:
    """Run pipeline twice with same metadata, compare output hashes.

    Returns (passed, messages).
    """
    ds_name = dataset_dir.name
    run_id = f"GOLDEN_{ds_name}"
    msgs: list[str] = []

    hashes_a: dict[str, str] = {}
    hashes_b: dict[str, str] = {}

    for label, target in [("run-A", hashes_a), ("run-B", hashes_b)]:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            try:
                summary = run_pipeline_deterministic(dataset_dir, output_dir, run_id=run_id)
            except Exception as e:
                return False, [f"{label} crashed: {e}"]

            run_folder = Path(summary["run_folder"])
            for run_path, manifest_key in ARTIFACT_MAP:
                f = run_folder / run_path
                if f.exists():
                    target[manifest_key] = sha256_file(f)

    mismatches: list[str] = []
    for key in hashes_a:
        if hashes_a[key] != hashes_b.get(key, ""):
            mismatches.append(
                f"{key}: run-A={hashes_a[key][:12]}... run-B={hashes_b.get(key, 'MISSING')[:12]}..."
            )

    if mismatches:
        msgs.append(f"  {ds_name}: NON-DETERMINISTIC")
        for m in mismatches:
            msgs.append(f"    {m}")
        return False, msgs
    else:
        msgs.append(f"  {ds_name}: deterministic (all {len(hashes_a)} artifacts match)")
        return True, msgs


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Full QA entrypoint: spec, datasets, outputs, goldens, determinism.",
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        default=None,
        help="Comma-separated dataset names/prefixes (e.g. D1 or D1,D2)",
    )
    parser.add_argument(
        "--skip-golden",
        action="store_true",
        default=False,
        help="Skip golden snapshot verification",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        default=False,
        help="Only run D1 + D3 (fast smoke test)",
    )
    args = parser.parse_args()

    # Resolve dataset filter
    if args.fast:
        ds_filter = ["D1", "D3"]
    elif args.dataset:
        ds_filter = [s.strip() for s in args.dataset.split(",")]
    else:
        ds_filter = None

    datasets = discover_datasets(ds_filter)
    if not datasets:
        print("ERROR: no datasets found.", file=sys.stderr)
        sys.exit(1)

    print(f"QA run: {len(datasets)} dataset(s)\n")

    overall_pass = True
    section_results: dict[str, str] = {}

    # ── 1. SPEC INTEGRITY ────────────────────────────────────────────────
    print("=" * 60)
    print("SPEC INTEGRITY")
    print("=" * 60)

    spec_ok, spec_msgs = check_spec_integrity()
    for m in spec_msgs:
        print(f"  {m}")
    section_results["SPEC"] = "PASS" if spec_ok else "FAIL"
    if not spec_ok:
        overall_pass = False
    print()

    # ── 2. DATASET INPUT VALIDATION ──────────────────────────────────────
    print("=" * 60)
    print("DATASET INPUT VALIDATION")
    print("=" * 60)

    schemas = _load_schemas()
    ds_all_ok = True

    # Load expected_raw_validation from manifest
    expected_raw: dict[str, str] = {}
    manifest_path = FROZEN_DIR / "manifest.json"
    if manifest_path.exists():
        manifest_data = load_json(manifest_path)
        for entry in manifest_data.get("datasets", []):
            erv = entry.get("expected_raw_validation")
            if erv:
                expected_raw[entry["dataset_id"]] = erv.upper()

    expected_fail_count = 0

    for ds_dir in datasets:
        result = validate_dataset_inputs(ds_dir, schemas)
        has_fail = len(result["failed"]) > 0
        ds_name = result["dataset"]
        ds_expected = expected_raw.get(ds_name)

        if ds_expected == "FAIL":
            if has_fail:
                status = "PASS (expected fail)"
                expected_fail_count += 1
            else:
                status = "FAIL (expected fail did not happen)"
                ds_all_ok = False
        else:
            status = "FAIL" if has_fail else "PASS"
            if has_fail:
                ds_all_ok = False

        print(f"  {ds_name}: {status}")
        for p in result["passed"]:
            print(f"    PASS  {p}")
        for s in result["skipped"]:
            print(f"    SKIP  {s}")
        for f in result["failed"]:
            print(f"    FAIL  {f}")

    section_results["DATASETS"] = "PASS" if ds_all_ok else "FAIL"
    if not ds_all_ok:
        overall_pass = False
    print()

    # ── 3. PIPELINE OUTPUT VALIDATION ────────────────────────────────────
    print("=" * 60)
    print("PIPELINE OUTPUT VALIDATION")
    print("=" * 60)

    out_all_ok = True

    for ds_dir in datasets:
        result = validate_pipeline_outputs(ds_dir, schemas)
        has_fail = len(result["failed"]) > 0
        status = "FAIL" if has_fail else "PASS"
        print(f"  {result['dataset']} (outcome: {result['outcome']}): {status}")
        for p in result["passed"]:
            print(f"    PASS  {p}")
        for f in result["failed"]:
            print(f"    FAIL  {f}")
        if has_fail:
            out_all_ok = False

    section_results["OUTPUTS"] = "PASS" if out_all_ok else "FAIL"
    if not out_all_ok:
        overall_pass = False
    print()

    # ── 4. GOLDEN SNAPSHOT VERIFICATION ──────────────────────────────────
    if args.skip_golden:
        print("=" * 60)
        print("GOLDEN SNAPSHOT VERIFICATION — SKIPPED (--skip-golden)")
        print("=" * 60)
        section_results["GOLDENS"] = "SKIP"
    else:
        print("=" * 60)
        print("GOLDEN SNAPSHOT VERIFICATION")
        print("=" * 60)

        golden_ok, golden_msgs = verify_goldens(datasets)
        for m in golden_msgs:
            print(m)
        section_results["GOLDENS"] = "PASS" if golden_ok else "FAIL"
        if not golden_ok:
            overall_pass = False
    print()

    # ── 5. DETERMINISM SMOKE CHECK ───────────────────────────────────────
    print("=" * 60)
    print("DETERMINISM SMOKE CHECK")
    print("=" * 60)

    # Use D1 by default; if D1 not in selected datasets, use first available
    det_ds = None
    for ds in datasets:
        if ds.name.upper().startswith("D1"):
            det_ds = ds
            break
    if det_ds is None:
        det_ds = datasets[0]

    det_ok, det_msgs = check_determinism(det_ds)
    for m in det_msgs:
        print(m)
    section_results["DETERMINISM"] = "PASS" if det_ok else "FAIL"
    if not det_ok:
        overall_pass = False
    print()

    # ── SUMMARY ──────────────────────────────────────────────────────────
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for section, result in section_results.items():
        tag = "PASS" if result == "PASS" else ("SKIP" if result == "SKIP" else "FAIL")
        print(f"  {section}: {tag}")
    if expected_fail_count:
        print(f"  expected-fail datasets: {expected_fail_count}")

    print()
    if overall_pass:
        print("ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
