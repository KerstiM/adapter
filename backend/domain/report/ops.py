"""
Domain report operations: pure helpers for building pipeline reports.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

from typing import Any

ADAPTER_VERSION = "0.1.0"

SEVERITY_RANK: dict[str, int] = {"INFO": 0, "WARN": 1, "ERROR": 2, "CRITICAL": 3}


def count_flags_by_severity(
    sv_transactions: list[dict],
    dropped: list[dict],
) -> dict[str, int]:
    """Count flag severities across all transactions (valid + dropped)."""
    counts: dict[str, int] = {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0}
    for tx in sv_transactions + dropped:
        for flag in tx.get("flags", []):
            sev = flag.get("severity", "")
            if sev in counts:
                counts[sev] += 1
    return counts


def build_dropped_details(
    dropped_txs: list[dict],
    dedupe_drops: list[dict],
    mapping_drops: list[dict],
) -> list[dict]:
    """Assemble the dropped_details list from all drop sources."""
    all_dropped: list[dict] = []

    for tx in dropped_txs:
        error_flags = [f for f in tx.get("flags", []) if f["severity"] == "ERROR"]
        all_dropped.append({
            "source_file": tx.get("source", {}).get("input_file"),
            "input_path": tx.get("source", {}).get("input_path"),
            "transaction_id": tx.get("transaction_id"),
            "drop_reason": "; ".join(f["message"] for f in error_flags) or "invariant check failed",
        })

    for tx in dedupe_drops:
        all_dropped.append({
            "source_file": tx.get("source", {}).get("input_file"),
            "input_path": tx.get("source", {}).get("input_path"),
            "transaction_id": tx.get("transaction_id"),
            "record_id": tx.get("record_id"),
            "drop_reason": "duplicate record_id",
        })

    all_dropped.extend(mapping_drops)
    return all_dropped


def count_error_drops(
    dropped_txs: list[dict],
    mapping_drops: list[dict],
    fail_severity: str = "ERROR",
) -> int:
    """Count error-level drops — shared by determine_outcome() and gate metrics.

    Counts invariant-dropped transactions with severity >= fail_severity,
    plus non-INFORMATION mapping drops.
    """
    fail_rank = SEVERITY_RANK.get(fail_severity, 2)

    error_drops = 0
    for tx in dropped_txs:
        if tx.get("status") == "INFORMATION":
            continue
        for flag in tx.get("flags", []):
            if SEVERITY_RANK.get(flag["severity"], 0) >= fail_rank:
                error_drops += 1
                break
    for md in mapping_drops:
        if md.get("status") != "INFORMATION":
            error_drops += 1
    return error_drops


def determine_outcome(
    by_severity: dict[str, int],
    issues: list[dict],
    run_flags: list[dict],
    dropped_txs: list[dict],
    mapping_drops: list[dict],
    total_raw: int,
    fail_severity: str = "ERROR",
    fail_ratio: float = 0.05,
) -> tuple[str, str]:
    """Determine pipeline outcome (status, stop_reason).

    Returns (outcome, stop_reason) based on gate policy.
    Uses count_error_drops() for the error-drop count — the same helper
    used by gate metrics to ensure identical counting logic.
    """
    error_drops = count_error_drops(dropped_txs, mapping_drops, fail_severity)

    drop_ratio = error_drops / total_raw if total_raw > 0 else 0.0
    if drop_ratio > fail_ratio:
        return "FAIL", f"error drop ratio {drop_ratio:.4f} exceeds threshold {fail_ratio}"
    elif by_severity["ERROR"] > 0 or any(i.get("severity") == "ERROR" for i in issues):
        return "PARTIAL_SUCCESS", "errors present but below fail threshold"
    elif run_flags or by_severity["WARN"] > 0:
        return "PARTIAL_SUCCESS", "warnings present"
    else:
        return "SUCCESS", "all validations passed"


def compute_metrics(
    input_records_total: int,
    passed_validation_total: int,
    dropped_total: int,
    dropped_details_count: int,
    ml_rows_count: int,
    invariant_checked_total: int,
    invariant_correct_total: int,
    critical_invariant_violations_total: int,
    error_drops: int,
) -> dict:
    """Compute derived quality and operational metrics.

    Counter mapping (current codebase → frozen definitions):
      transactions_total        → input_records_total  (= total_raw in pipeline)
      transactions_emitted_sv   → passed_validation_total  (= len(deduped_txs))
      transactions_dropped      → dropped_total

    Identity: input_records_total == passed_validation_total + dropped_total

    input_records_total is the single canonical raw-record counter used by
    both SLI-2 (pass-through ratio) and gate (error-drop ratio).  In
    pipeline.py this is total_raw — the count of all raw transactions across
    all report files before any processing.

    Returns a dict with five metric groups:

      sli2  — Validation pass-through ratio (official quality metric).
              = passed_validation_total / input_records_total

      qc2   — Drop-reporting coverage (operational control).
              = dropped_details_count / dropped_total  (must equal 1.0)
              All dropped records must appear in dropped_details[].
              Strict equality: over-reporting is treated as inconsistency.

      sli3  — Invariant compliance ratio (official quality metric).
              = invariant_correct_total / invariant_checked_total

              invariant_checked_total = records entering Stage 4
                  (CHECK_INVARIANTS) after mapping, before dedupe.
                  Captured as len(sv_bundle["transactions"]) before
                  calling check_invariants().  Excludes mapping drops.

              invariant_correct_total = invariant_checked_total
                  − ERROR invariant drops (dropped_txs)
                  − INV-09 dedupe drops (dedupe_drops)
                  − kept records with WARN invariant flags
                  Must be >= 0.

              critical_invariant_violations_total = records with
                  ERROR-level invariant violations only.
                  Excludes mapping drops, dedupe drops, WARN-only records.

      gate  — Operational error-drop fail policy (NOT an SLI).
              error_drop_ratio = error_drops / input_records_total
              Uses count_error_drops() — same logic as determine_outcome().

      info  — ML emission ratio (informative, NOT an SLI).
              = ml_rows_count / input_records_total
              End-to-end survival from raw input to ML projection.
              Always ≤ SLI-2 because ML projection excludes INFORMATION-status
              records that survive validation.
    """
    sli2_ratio = (
        passed_validation_total / input_records_total
        if input_records_total > 0
        else 1.0
    )

    if dropped_total > 0:
        qc2_ratio = dropped_details_count / dropped_total
        qc2_all_reported = dropped_details_count == dropped_total
    else:
        qc2_ratio = 1.0
        qc2_all_reported = True

    assert invariant_correct_total >= 0, (
        f"invariant_correct_total must be >= 0, got {invariant_correct_total} "
        f"(checked={invariant_checked_total})"
    )
    sli3_ratio = (
        invariant_correct_total / invariant_checked_total
        if invariant_checked_total > 0
        else 1.0
    )

    error_drop_ratio = error_drops / input_records_total if input_records_total > 0 else 0.0

    ml_emission_ratio = (
        ml_rows_count / input_records_total
        if input_records_total > 0
        else 0.0
    )

    return {
        "sli2": {
            "validation_pass_through_ratio": round(sli2_ratio, 4),
        },
        "qc2": {
            "drop_reporting_ratio": round(qc2_ratio, 4),
            "all_drops_reported": qc2_all_reported,
        },
        "sli3": {
            "invariant_compliance_ratio": round(sli3_ratio, 4),
            "invariant_checked_total": invariant_checked_total,
            "invariant_correct_total": invariant_correct_total,
            "critical_invariant_violations_total": critical_invariant_violations_total,
        },
        "gate": {
            "error_drop_ratio": round(error_drop_ratio, 4),
            "error_drops": error_drops,
        },
        "info": {
            "ml_emission_ratio": round(ml_emission_ratio, 4),
        },
    }


def build_report(
    run_id: str,
    created_at_utc: str,
    profile_id: str,
    dataset_id: str,
    input_dir: str,
    outcome: str,
    stop_reason: str,
    accounts_total: int,
    transactions_total: int,
    transactions_emitted_sv: int,
    transactions_dropped: int,
    ml_rows_count: int,
    llm_contexts_count: int,
    by_severity: dict[str, int],
    stage_log: list[dict],
    run_flags: list[dict],
    issues: list[dict],
    dropped_details: list[dict] | None = None,
    metrics: dict | None = None,
) -> dict:
    """Build report.json structure (S-05 compliant).

    Pure function — takes pre-resolved scalars, no Path/I/O.
    """
    report = {
        "report_schema_version": "1.3.0",
        "run": {
            "run_id": run_id,
            "created_at_utc": created_at_utc,
            "profile_id": profile_id,
            "dataset_id": dataset_id,
            "input_dir": input_dir,
            "adapter_version": ADAPTER_VERSION,
            "sv_schema_version": "1.0.0",
            "mapping_version": "1.0.0",
            "ruleset_version": "1.1.0",
        },
        "outcome": {
            "status": outcome,
            "stop_reason": stop_reason,
        },
        "summary": {
            "counts": {
                "accounts_total": accounts_total,
                "transactions_total": transactions_total,
                "transactions_emitted_sv": transactions_emitted_sv,
                "transactions_dropped": transactions_dropped,
                "ml_rows": ml_rows_count,
                "llm_contexts": llm_contexts_count,
            },
            "by_stage": stage_log,
            "by_severity": by_severity,
        },
        "run_flags": run_flags,
        "issues": issues,
        "dropped_details": dropped_details or [],
    }
    if metrics is not None:
        report["metrics"] = metrics
    return report
