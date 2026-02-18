"""
Adapter pipeline: RAW (Berlin AIS) -> SV -> ML/LLM projections.

Implements the full pipeline:
  1. Read & validate RAW input (S-00A, S-00B) — multiple report files + download-only
  2. Map to SV (C-01) — flatten booked/pending/information, derive direction/counterparty/amounts
  3. Validate SV schema (S-01)
  4. Check invariants (R-01) — field-level rules + INV-09 dedupe by (account_id, record_id)
  5. Project to ML CSV (C-02) and LLM context JSON (C-03)
  6. Write outputs + fail-gate check (default.yaml run_policy)
"""

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from domain.mapping.c01_raw_to_sv import (
    build_sv_bundle as _build_sv_bundle,
    flatten_report_file as _flatten_report_file,
    map_single_transaction as _map_single_transaction,
)
from domain.projections.c02_sv_to_ml import project_ml as _project_ml
from domain.projections.c03_sv_to_llm import project_llm as _project_llm
from domain.report.ops import (
    ADAPTER_VERSION,
    build_dropped_details as _build_dropped_details,
    build_report as _build_report,
    count_flags_by_severity as _count_flags_by_severity,
    determine_outcome as _determine_outcome,
)
from domain.rules.invariants_r01 import (
    check_invariants as _check_invariants,
    deduplicate_transactions as _deduplicate_transactions,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = REPO_ROOT / "spec"


# ---------------------------------------------------------------------------
# Helpers — file loading
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_yaml_file(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_spec_path(relpath: str) -> Path:
    """
    Resolve a spec path EXACTLY as written in the profile.
    No fallbacks, no guessing. If missing -> fail fast.
    """
    path = (REPO_ROOT / relpath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Spec file missing (profile points to it): {relpath} -> {path}")
    return path


def load_profile() -> dict:
    """Load default profile and resolve all referenced spec files."""
    profile_path = SPEC_DIR / "profiles" / "default.yaml"
    profile = _load_yaml_file(profile_path)

    resolved: dict[str, Any] = {
        "id": profile["id"],
        "version": profile["version"],
    }

    # Load schemas
    resolved["schemas"] = {}
    for key, relpath in profile.get("schemas", {}).items():
        path = _resolve_spec_path(relpath)
        resolved["schemas"][key] = _load_json(path)

    # Load contracts
    resolved["contracts"] = {}
    for key, relpath in profile.get("contracts", {}).items():
        path = _resolve_spec_path(relpath)
        resolved["contracts"][key] = _load_yaml_file(path)

    # Load rulesets
    resolved["rulesets"] = {}
    for key, relpath in profile.get("rulesets", {}).items():
        path = _resolve_spec_path(relpath)
        resolved["rulesets"][key] = _load_yaml_file(path)

    return resolved


# ---------------------------------------------------------------------------
# Helpers — data utilities
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_prefix(created_at_utc: str) -> str:
    """Derive a filesystem-safe timestamp prefix from an ISO timestamp."""
    return created_at_utc.replace("-", "").replace(":", "").replace("T", "T").split(".")[0]


def _is_download_only(data: dict) -> bool:
    """Check if a transaction response is download-only (C-01 rule)."""
    return bool((data.get("_links") or {}).get("download", {}).get("href"))


def _stable_json(obj: Any) -> str:
    """Deterministic JSON serialization."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Stage 1: Read & validate RAW input
# ---------------------------------------------------------------------------

def _validate_raw_accounts(accounts_data: dict, schema: dict) -> list[dict]:
    errors: list[dict] = []
    try:
        jsonschema.validate(accounts_data, schema)
    except jsonschema.ValidationError as e:
        errors.append({
            "code": "S-00A_VALIDATION",
            "severity": "ERROR",
            "stage": "READ_INPUT",
            "message": f"S-00A validation: {e.message}",
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": ".".join(str(p) for p in e.absolute_path) or None,
                "source_lineage": "accounts.json",
            },
        })
    return errors


def _validate_raw_transactions(tx_data: dict, schema: dict) -> list[dict]:
    errors: list[dict] = []
    try:
        jsonschema.validate(tx_data, schema)
    except jsonschema.ValidationError as e:
        errors.append({
            "code": "S-00B_VALIDATION",
            "severity": "ERROR",
            "stage": "READ_INPUT",
            "message": f"S-00B validation: {e.message}",
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": ".".join(str(p) for p in e.absolute_path) or None,
                "source_lineage": "transactions.json",
            },
        })
    return errors


def _validate_raw_standing_orders(so_data: dict, schema: dict) -> list[dict]:
    errors: list[dict] = []
    try:
        jsonschema.validate(so_data, schema)
    except jsonschema.ValidationError as e:
        errors.append({
            "code": "S-00C_VALIDATION",
            "severity": "ERROR",
            "stage": "READ_INPUT",
            "message": f"S-00C validation: {e.message}",
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": ".".join(str(p) for p in e.absolute_path) or None,
                "source_lineage": "standing_orders.json",
            },
        })
    return errors


# ---------------------------------------------------------------------------
# Stage 3: Validate SV schema
# ---------------------------------------------------------------------------

def _validate_sv_schema(sv_bundle: dict, schema: dict) -> list[dict]:
    errors: list[dict] = []
    try:
        jsonschema.validate(sv_bundle, schema)
    except jsonschema.ValidationError as e:
        errors.append({
            "code": "S-01_VALIDATION",
            "severity": "ERROR",
            "stage": "VALIDATE_SCHEMA",
            "message": f"S-01 validation: {e.message}",
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": ".".join(str(p) for p in e.absolute_path) or None,
                "source_lineage": "sv.json",
            },
        })
    return errors


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    data_dir: str | Path,
    output_dir: str | Path,
    run_id: str | None = None,
    created_at_utc: str | None = None,
) -> dict:
    """
    Run the full adapter pipeline: RAW -> SV -> ML/LLM projections.

    All outputs are written to a single run folder:
        out/<timestamp>_<run_id>/
            sv.json
            report.json
            projections/ml_v1.csv
            projections/llm_context_v1.json

    Returns:
        Summary dict with outcome, run_id, run_folder, counts, flags, issues.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

    # --- RunContext: single source of run_id and created_at_utc ---
    if run_id is None:
        run_id = uuid.uuid4().hex[:12]
    if created_at_utc is None:
        created_at_utc = _now_utc()

    # Create run folder: <timestamp>_<run_id>
    ts = _ts_prefix(created_at_utc)
    run_folder = output_dir / f"{ts}_{run_id}"
    run_folder.mkdir(parents=True, exist_ok=True)
    proj_folder = run_folder / "projections"
    proj_folder.mkdir(exist_ok=True)

    # Load profile (reads all spec files)
    profile = load_profile()

    issues: list[dict] = []
    run_flags: list[dict] = []
    stage_log: dict[str, dict] = {}

    # ================================================================
    # Stage 1: READ_INPUT — read & validate RAW
    # ================================================================
    stage_errors_1 = 0
    stage_warnings_1 = 0

    with open(data_dir / "accounts.json", encoding="utf-8") as f:
        accounts_data = json.load(f)

    acct_errors = _validate_raw_accounts(accounts_data, profile["schemas"]["S-00A"])
    issues.extend(acct_errors)
    stage_errors_1 += len(acct_errors)

    # Load report files (C-01 inputs.reports)
    # Multi-account support: load ALL transactions*.json files except
    # transactions_download.json (handled separately below).
    report_files: list[tuple[str, dict]] = []
    tx_candidates = sorted(
        p.name for p in data_dir.glob("transactions*.json")
        if p.name != "transactions_download.json"
    )
    for fname in tx_candidates:
        fpath = data_dir / fname
        with open(fpath, encoding="utf-8") as f:
            tx_data = json.load(f)
        tx_errors = _validate_raw_transactions(tx_data, profile["schemas"]["S-00B"])
        issues.extend(tx_errors)
        stage_errors_1 += len(tx_errors)
        report_files.append((fname, tx_data))

    # Load optional standing orders (validated against S-00C)
    so_path = data_dir / "standing_orders.json"
    if so_path.exists():
        with open(so_path, encoding="utf-8") as f:
            so_data = json.load(f)
        so_errors = _validate_raw_standing_orders(so_data, profile["schemas"]["S-00C"])
        issues.extend(so_errors)
        stage_errors_1 += len(so_errors)
        report_files.append(("standing_orders.json", so_data))

    # Load optional download-only files (C-01 download_only_handling)
    for fname in ("transactions_download.json",):
        fpath = data_dir / fname
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                dl_data = json.load(f)
            if _is_download_only(dl_data):
                run_flags.append({
                    "id": "RUN_DOWNLOAD_ONLY",
                    "severity": "WARN",
                    "message": "transaction report delivered as download link; not expanded in prototype.",
                })
                stage_warnings_1 += 1
            else:
                tx_errors = _validate_raw_transactions(dl_data, profile["schemas"]["S-00B"])
                issues.extend(tx_errors)
                stage_errors_1 += len(tx_errors)
                report_files.append((fname, dl_data))

    # Count total raw transactions across all report files
    total_raw = 0
    for _, tx_data in report_files:
        tx_obj = tx_data.get("transactions") or {}
        for key in ("booked", "pending", "information"):
            total_raw += len(tx_obj.get(key, []))

    stage_log["READ_INPUT"] = {
        "status": "OK" if stage_errors_1 == 0 else "WARN",
        "errors": stage_errors_1,
        "warnings": stage_warnings_1,
    }

    # ================================================================
    # Stage 2: STANDARDIZE_TO_SV — map RAW -> SV (C-01)
    # ================================================================
    sv_bundle, mapping_drops = _build_sv_bundle(
        accounts_data, report_files, run_id, created_at_utc, profile,
    )

    stage2_warnings = len(mapping_drops)
    stage_log["STANDARDIZE_TO_SV"] = {
        "status": "OK" if stage2_warnings == 0 else "WARN",
        "errors": 0,
        "warnings": stage2_warnings,
    }

    # ================================================================
    # Stage 3: VALIDATE_SCHEMA — validate SV against S-01
    # ================================================================
    sv_errors = _validate_sv_schema(sv_bundle, profile["schemas"]["S-01"])
    issues.extend(sv_errors)

    stage_log["VALIDATE_SCHEMA"] = {
        "status": "OK" if not sv_errors else "ERROR",
        "errors": len(sv_errors),
        "warnings": 0,
    }

    # ================================================================
    # Stage 4: CHECK_INVARIANTS — R-01 (field-level rules)
    # ================================================================
    valid_txs, dropped_txs = _check_invariants(sv_bundle)

    # Stage 4b: Deduplicate by (account_id, record_id) — INV-09
    deduped_txs, dedupe_drops = _deduplicate_transactions(valid_txs)
    sv_bundle["transactions"] = deduped_txs

    # Count flags from invariants (on valid + dropped + dedupe-dropped txs)
    inv_warnings = 0
    inv_errors = 0
    for tx in deduped_txs + dropped_txs + dedupe_drops:
        for flag in tx.get("flags", []):
            if flag["severity"] == "WARN":
                inv_warnings += 1
            elif flag["severity"] == "ERROR":
                inv_errors += 1

    stage_log["CHECK_INVARIANTS"] = {
        "status": "OK" if inv_errors == 0 and inv_warnings == 0 else ("ERROR" if inv_errors > 0 else "WARN"),
        "errors": inv_errors,
        "warnings": inv_warnings,
    }

    # ================================================================
    # Stage 5a: PROJECT_ML — ML projection (C-02)
    # ================================================================
    ml_rows = _project_ml(sv_bundle)

    stage_log["PROJECT_ML"] = {
        "status": "OK",
        "errors": 0,
        "warnings": 0,
    }

    # ================================================================
    # Stage 5b: PROJECT_LLM — LLM projection (C-03)
    # ================================================================
    llm_contexts = _project_llm(sv_bundle, profile)

    stage_log["PROJECT_LLM"] = {
        "status": "OK",
        "errors": 0,
        "warnings": 0,
    }

    # ================================================================
    # Stage 6: WRITE_OUTPUTS
    # ================================================================

    # sv.json (deterministic key order)
    with open(run_folder / "sv.json", "w", encoding="utf-8") as f:
        f.write(_stable_json(sv_bundle))
        f.write("\n")

    # projections/ml_v1.csv
    csv_path = proj_folder / "ml_v1.csv"
    fieldnames = [
        "row_id", "account_id", "record_id", "status",
        "booking_date", "value_date", "direction", "currency",
        "signed_amount", "abs_amount", "counterparty_name", "remittance",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ml_rows)

    # projections/llm_context_v1.json — all accounts
    llm_path = proj_folder / "llm_context_v1.json"
    if len(llm_contexts) == 1:
        llm_output = llm_contexts[0]
    else:
        llm_output = llm_contexts  # array for multi-account
    with open(llm_path, "w", encoding="utf-8") as f:
        f.write(_stable_json(llm_output))
        f.write("\n")

    # Count flag severities across all transactions for report
    all_dropped_for_severity = dropped_txs + dedupe_drops
    by_severity = _count_flags_by_severity(deduped_txs, all_dropped_for_severity)

    # Combine invariant drops + mapping drops + dedupe drops for total dropped count
    total_dropped = len(dropped_txs) + len(mapping_drops) + len(dedupe_drops)

    # Build dropped_details
    all_dropped_details = _build_dropped_details(dropped_txs, dedupe_drops, mapping_drops)

    # Determine outcome using run_policy fail gate from default.yaml
    run_policy = profile.get("run_policy", {}).get("partial_success_policy", {})
    fail_on = run_policy.get("fail_on", {})
    fail_severity = fail_on.get("any_severity", "ERROR")
    fail_ratio = fail_on.get("ratio_over_records", 0.05)

    outcome, stop_reason = _determine_outcome(
        by_severity=by_severity,
        issues=issues,
        run_flags=run_flags,
        dropped_txs=dropped_txs,
        mapping_drops=mapping_drops,
        total_raw=total_raw,
        fail_severity=fail_severity,
        fail_ratio=fail_ratio,
    )

    stage_log["WRITE_OUTPUTS"] = {
        "status": "OK",
        "errors": 0,
        "warnings": 0,
    }

    # Convert stage_log dict to S-05 compliant array
    stage_order = [
        "READ_INPUT", "STANDARDIZE_TO_SV", "VALIDATE_SCHEMA",
        "CHECK_INVARIANTS", "PROJECT_ML", "PROJECT_LLM", "WRITE_OUTPUTS",
    ]
    stage_log_array: list[dict] = []
    for stage_name in stage_order:
        entry = stage_log.get(stage_name, {})
        stage_log_array.append({
            "stage": stage_name,
            "errors": entry.get("errors", 0),
            "warnings": entry.get("warnings", 0),
            "infos": 0,
        })

    # Resolve dataset_id and input_dir for report (handle Path -> str here)
    dataset_id = data_dir.name
    try:
        input_dir = str(data_dir.resolve().relative_to(REPO_ROOT).as_posix())
    except Exception:
        input_dir = str(data_dir.resolve().as_posix())

    # report.json
    report = _build_report(
        run_id=run_id,
        created_at_utc=created_at_utc,
        profile_id=profile["id"],
        dataset_id=dataset_id,
        input_dir=input_dir,
        outcome=outcome,
        stop_reason=stop_reason,
        accounts_total=len(sv_bundle.get("accounts", [])),
        transactions_total=total_raw,
        transactions_emitted_sv=len(deduped_txs),
        transactions_dropped=total_dropped,
        ml_rows_count=len(ml_rows),
        llm_contexts_count=len(llm_contexts),
        by_severity=by_severity,
        stage_log=stage_log_array,
        run_flags=run_flags,
        issues=issues,
        dropped_details=all_dropped_details,
    )
    with open(run_folder / "report.json", "w", encoding="utf-8") as f:
        f.write(_stable_json(report))
        f.write("\n")

    # --- Return summary ---
    return {
        "outcome": outcome,
        "stop_reason": stop_reason,
        "run_id": run_id,
        "run_folder": str(run_folder),
        "counts": {
            "accounts_total": len(sv_bundle.get("accounts", [])),
            "transactions_total": total_raw,
            "transactions_emitted_sv": len(deduped_txs),
            "transactions_dropped": total_dropped,
            "ml_rows": len(ml_rows),
            "llm_contexts": len(llm_contexts),
        },
        "by_severity": by_severity,
        "run_flags": run_flags,
        "issues": issues,
        "dropped_details": all_dropped_details,
    }
