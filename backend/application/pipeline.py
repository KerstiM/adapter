"""
Adapter pipeline — application layer: RAW (Berlin AIS) -> SV -> ML/LLM projections.

Orchestrates the full 8-stage pipeline through ports only.  No filesystem I/O,
no pathlib, no os — all I/O is delegated to the injected port implementations.

Stages:
  1. READ_INPUT        — read & validate raw Berlin AIS input via DatasetPort + SpecPort
  2. STANDARDIZE_TO_SV — map to canonical SV (C-01) using pure functions
  3. VALIDATE_SCHEMA   — validate SV bundle against S-01 schema
  4. CHECK_INVARIANTS  — R-01 field-level rules + INV-09 dedupe
  5. PROJECT_ML        — ML CSV projection (C-02)
  6. PROJECT_LLM       — LLM context projection (C-03)
  7. FORMAT_FOR_MODEL  — model-specific formatting (C-04)
  8. WRITE_OUTPUTS     — persist artifacts via OutputPort + build report
"""

from __future__ import annotations

from typing import Any

import jsonschema

from domain.mapping.c01_raw_to_sv import (
    build_sv_bundle as _build_sv_bundle,
)
from domain.projections.c02_sv_to_ml import project_ml as _project_ml
from domain.projections.c03_sv_to_llm import project_llm as _project_llm
from domain.projections.c05_sv_to_stats import project_stats as _project_stats
from domain.projections.c06_sv_to_monthly_balance import (
    project_monthly_balance as _project_monthly_balance,
)
from domain.projections.model_formatters import format_for_model as _format_for_model
from domain.report.ops import (
    build_dropped_details as _build_dropped_details,
    build_report as _build_report,
    compute_metrics as _compute_metrics,
    count_error_drops as _count_error_drops,
    count_flags_by_severity as _count_flags_by_severity,
    determine_outcome as _determine_outcome,
)
from domain.rules.invariants_r01 import (
    check_invariants as _check_invariants,
    deduplicate_transactions as _deduplicate_transactions,
)
from ports.clock_port import ClockPort
from ports.dataset_port import DatasetPort
from ports.output_port import OutputPort
from ports.spec_port import SpecPort


# ---------------------------------------------------------------------------
# Helpers — pure data utilities (no I/O)
# ---------------------------------------------------------------------------

def _is_download_only(data: dict) -> bool:
    """Check if a transaction response is download-only (C-01 rule)."""
    return bool((data.get("_links") or {}).get("download", {}).get("href"))


# ---------------------------------------------------------------------------
# Extra-projection dispatch: name -> (pure function, contract key)
# ---------------------------------------------------------------------------
_EXTRA_PROJECTION_DISPATCH: dict[str, tuple[Any, str]] = {
    "stats": (_project_stats, "C-05"),
    "monthly_balance": (_project_monthly_balance, "C-06"),
}


# ---------------------------------------------------------------------------
# Stage 1 & 3: Schema validation (shared helper)
# ---------------------------------------------------------------------------

def _validate_against_schema(
    data: dict,
    schema: dict,
    *,
    code: str,
    stage: str,
    source_lineage: str,
) -> list[dict]:
    """Validate *data* against *schema* and return a list of Issue dicts.

    A successful validation returns an empty list.  A failure yields a single
    Issue dict with the given *code*/*stage*/*source_lineage* and the first
    schema error reported by ``jsonschema``.  This helper backs all four of
    the pipeline's schema-validation stages (S-00A/B/C on RAW input, S-01 on
    the SV bundle).
    """
    errors: list[dict] = []
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        schema_id = code.split("_", 1)[0]
        errors.append({
            "code": code,
            "severity": "ERROR",
            "stage": stage,
            "message": f"{schema_id} validation: {e.message}",
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": ".".join(str(p) for p in e.absolute_path) or None,
                "source_lineage": source_lineage,
            },
        })
    return errors


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    dataset: DatasetPort,
    out: OutputPort,
    spec: SpecPort,
    clock: ClockPort,
    profile_id: str = "default",
    *,
    dataset_id: str = "",
    input_dir: str = "",
    target_models_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full adapter pipeline via ports: RAW -> SV -> ML/LLM projections.

    This is the **single public entry point** of the application layer.
    It depends only on ``ports.*`` and ``domain.*`` — never on concrete
    adapters or filesystem paths.

    Parameters
    ----------
    dataset : DatasetPort
        Read-only access to raw Berlin AIS input files
        (accounts, transaction reports, standing orders).
    out : OutputPort
        Write access for persisting run artefacts
        (sv.json, ml_v1.csv, llm_context_v1.json, report.json).
    spec : SpecPort
        Read-only access to specification artefacts
        (schemas, contracts, rulesets, run profiles).
    clock : ClockPort
        Source of wall-clock time and unique run identifiers.
    profile_id : str, default ``"default"``
        Which run profile to load via *spec*.
    dataset_id : str, keyword-only
        Human-readable dataset name included in the run report.
    input_dir : str, keyword-only
        Input path string included in the run report for traceability.

    Returns
    -------
    dict[str, Any]
        Summary dict conforming to the structure::

            {
                "outcome":         str,   # SUCCESS | PARTIAL_SUCCESS | FAIL
                "stop_reason":     str,
                "run_id":          str,
                "counts": {
                    "accounts_total":           int,
                    "transactions_total":       int,
                    "transactions_emitted_sv":  int,
                    "transactions_dropped":     int,
                    "ml_rows":                  int,
                    "llm_contexts":             int,
                },
                "by_severity":     dict[str, int],
                "run_flags":       list[dict],
                "issues":          list[dict],
                "dropped_details": list[dict],
            }

        The full ``CollectedRunReport`` (see ``domain.report.models``) is
        written to *out* via ``out.write_report()``; this dict is a
        lightweight caller-facing summary.

    Notes
    -----
    ``run_folder`` is intentionally absent from the return value.
    Filesystem callers can read it from ``FsOutputAdapter.run_folder``
    after the call returns.
    """
    # ── RunContext ────────────────────────────────────────────────────────
    run_id = clock.new_run_id()
    created_at_utc = clock.now_utc()

    out.init_run_folder(run_id, created_at_utc)

    profile = spec.load_profile(profile_id)

    issues: list[dict] = []
    run_flags: list[dict] = []
    stage_log: dict[str, dict] = {}

    # ================================================================
    # Stage 1: READ_INPUT — read & validate RAW
    # ================================================================
    stage_errors_1 = 0
    stage_warnings_1 = 0

    accounts_data = dataset.read_accounts()
    acct_errors = _validate_against_schema(
        accounts_data,
        profile["schemas"]["S-00A"],
        code="S-00A_VALIDATION",
        stage="READ_INPUT",
        source_lineage="accounts.json",
    )
    issues.extend(acct_errors)
    stage_errors_1 += len(acct_errors)

    # Load report files via DatasetPort
    report_files: list[tuple[str, dict]] = []
    for name in dataset.list_transaction_reports():
        tx_data = dataset.read_transactions_report(name)
        if name == "transactions_download.json":
            if _is_download_only(tx_data):
                run_flags.append({
                    "id": "RUN_DOWNLOAD_ONLY",
                    "severity": "WARN",
                    "message": "transaction report delivered as download link; not expanded in prototype.",
                })
                stage_warnings_1 += 1
            else:
                tx_errors = _validate_against_schema(
                    tx_data,
                    profile["schemas"]["S-00B"],
                    code="S-00B_VALIDATION",
                    stage="READ_INPUT",
                    source_lineage="transactions.json",
                )
                issues.extend(tx_errors)
                stage_errors_1 += len(tx_errors)
                report_files.append((name, tx_data))
        else:
            tx_errors = _validate_against_schema(
                tx_data,
                profile["schemas"]["S-00B"],
                code="S-00B_VALIDATION",
                stage="READ_INPUT",
                source_lineage="transactions.json",
            )
            issues.extend(tx_errors)
            stage_errors_1 += len(tx_errors)
            report_files.append((name, tx_data))

    # Load optional standing orders via DatasetPort
    so_data = dataset.read_standing_orders_optional()
    if so_data is not None:
        so_errors = _validate_against_schema(
            so_data,
            profile["schemas"]["S-00C"],
            code="S-00C_VALIDATION",
            stage="READ_INPUT",
            source_lineage="standing_orders.json",
        )
        issues.extend(so_errors)
        stage_errors_1 += len(so_errors)
        report_files.append(("standing_orders.json", so_data))

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
    for md in mapping_drops:
        issues.append({
            "code": "C-01_MAPPING_DROP",
            "severity": "WARN",
            "stage": "STANDARDIZE_TO_SV",
            "message": md.get("drop_reason", "mapping drop"),
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": md.get("input_path"),
                "source_lineage": md.get("source_file", ""),
            },
        })
    stage_log["STANDARDIZE_TO_SV"] = {
        "status": "OK" if stage2_warnings == 0 else "WARN",
        "errors": 0,
        "warnings": stage2_warnings,
    }

    # ================================================================
    # Stage 3: VALIDATE_SCHEMA — validate SV against S-01
    # ================================================================
    sv_errors = _validate_against_schema(
        sv_bundle,
        profile["schemas"]["S-01"],
        code="S-01_VALIDATION",
        stage="VALIDATE_SCHEMA",
        source_lineage="sv.json",
    )
    issues.extend(sv_errors)

    stage_log["VALIDATE_SCHEMA"] = {
        "status": "OK" if not sv_errors else "ERROR",
        "errors": len(sv_errors),
        "warnings": 0,
    }

    # ================================================================
    # Stage 4: CHECK_INVARIANTS — R-01 (field-level rules)
    # ================================================================

    # SLI-3 denominator: records entering invariant checking after mapping,
    # before dedupe.  Excludes mapping drops (Stage 2).
    invariant_checked_total = len(sv_bundle.get("transactions", []))

    valid_txs, dropped_txs = _check_invariants(sv_bundle)

    # Stage 4b: Deduplicate by (account_id, record_id) — INV-09
    deduped_txs, dedupe_drops = _deduplicate_transactions(valid_txs)
    sv_bundle["transactions"] = deduped_txs

    # Count flags from invariants (on valid + dropped + dedupe-dropped txs)
    # and promote them into the issues list so the frontend can display details
    inv_warnings = 0
    inv_errors = 0
    for tx in deduped_txs + dropped_txs + dedupe_drops:
        for flag in tx.get("flags", []):
            if flag["severity"] == "WARN":
                inv_warnings += 1
            elif flag["severity"] == "ERROR":
                inv_errors += 1
            issues.append({
                "code": flag["id"],
                "severity": flag["severity"],
                "stage": "CHECK_INVARIANTS",
                "message": flag["message"],
                "refs": {
                    "account_id": tx.get("account_id"),
                    "record_id": tx.get("record_id"),
                    "field_path": None,
                    "source_lineage": tx.get("source", {}).get("input_file", ""),
                },
            })

    stage_log["CHECK_INVARIANTS"] = {
        "status": "OK" if inv_errors == 0 and inv_warnings == 0 else ("ERROR" if inv_errors > 0 else "WARN"),
        "errors": inv_errors,
        "warnings": inv_warnings,
    }

    # ================================================================
    # Stage 5: PROJECT_ML — ML projection (C-02)
    # ================================================================
    ml_rows = _project_ml(sv_bundle)

    stage_log["PROJECT_ML"] = {
        "status": "OK",
        "errors": 0,
        "warnings": 0,
    }

    # ================================================================
    # Stage 6: PROJECT_LLM — LLM context projection (C-03)
    # ================================================================
    llm_contexts = _project_llm(sv_bundle, profile)

    stage_log["PROJECT_LLM"] = {
        "status": "OK",
        "errors": 0,
        "warnings": 0,
    }

    # ----------------------------------------------------------------
    # Opt-in report extensions — additive, gated by profile
    # ----------------------------------------------------------------
    # Profile-level extension hook: each entry in ``profile["report_extensions"]``
    # contributes a named section to the final ``report.json`` under
    # ``"extensions"``. Absent or empty list → byte-identical default behaviour.
    report_extensions_out: dict[str, Any] = {}
    for _ext_name in profile.get("report_extensions", []):
        if _ext_name == "monthly_balance":
            report_extensions_out["monthly_balance"] = _project_monthly_balance(sv_bundle)

    # ----------------------------------------------------------------
    # Opt-in extra projections — profile-gated, contract-linked,
    # schema-validated, written as standalone output artefacts
    # ----------------------------------------------------------------
    extra_projections_audit: list[dict] = []
    for _proj_name in profile.get("extra_projections", []):
        _dispatch = _EXTRA_PROJECTION_DISPATCH.get(_proj_name)
        if _dispatch is None:
            continue
        _proj_fn, _contract_key = _dispatch

        # Read contract for output path and schema reference
        _contract = profile.get("contracts", {}).get(_contract_key, {})
        _output_cfg = _contract.get("output") or {}
        _schema_key = _output_cfg.get("schema")
        _output_file = _output_cfg.get("file", f"projections/{_proj_name}_v1.json")
        _output_filename = _output_file.rsplit("/", 1)[-1]

        # Run projection
        _proj_data = _proj_fn(sv_bundle)

        # Runtime schema validation
        _validation_result = "PASS"
        if _schema_key and _schema_key in profile.get("schemas", {}):
            try:
                jsonschema.validate(_proj_data, profile["schemas"][_schema_key])
            except jsonschema.ValidationError as e:
                _validation_result = f"FAIL: {e.message}"
                issues.append({
                    "code": f"{_schema_key}_VALIDATION",
                    "severity": "WARN",
                    "stage": "WRITE_OUTPUTS",
                    "message": f"{_schema_key} validation ({_proj_name}): {e.message}",
                    "refs": {
                        "account_id": None,
                        "record_id": None,
                        "field_path": ".".join(str(p) for p in e.absolute_path) or None,
                        "source_lineage": f"extra_projection:{_proj_name}",
                    },
                })

        # Write standalone output artefact
        out.write_extra_projection(_proj_data, _output_filename)

        # Audit trail entry
        extra_projections_audit.append({
            "name": _proj_name,
            "enabled": True,
            "contract_id": _contract.get("id", _contract_key),
            "contract_version": _contract.get("version", "unknown"),
            "schema_id": _schema_key,
            "output_file": f"projections/{_output_filename}",
            "item_count": len(_proj_data),
            "validation_result": _validation_result,
        })

    # ================================================================
    # Stage 7: FORMAT_FOR_MODEL — model-specific formatting (C-04)
    # ================================================================
    target_models = profile.get("target_models", {})
    if target_models_override:
        target_models = {**target_models, **target_models_override}
    model_ml_outputs: dict[str, dict] = {}
    model_llm_outputs: dict[str, list[dict]] = {}

    c04 = profile.get("contracts", {}).get("C-04", {})
    llm_preamble = target_models.get("llm_preamble", "")

    for ml_model_id in target_models.get("ml", []):
        ml_model_config = c04.get("ml_models", {}).get(ml_model_id)
        if ml_model_config:
            result = _format_for_model(
                ml_rows, sv_bundle, ml_model_id, ml_model_config, "ml",
            )
            suffix = ml_model_config.get("output_suffix", ml_model_id)
            model_ml_outputs[suffix] = result

    for llm_model_id in target_models.get("llm", []):
        llm_model_config = c04.get("llm_models", {}).get(llm_model_id)
        if llm_model_config:
            result = _format_for_model(
                llm_contexts, sv_bundle, llm_model_id, llm_model_config, "llm",
                preamble=llm_preamble,
            )
            suffix = llm_model_config.get("output_suffix", llm_model_id)
            model_llm_outputs[suffix] = result

    fmt_errors = 0
    stage_log["FORMAT_FOR_MODEL"] = {
        "status": "OK",
        "errors": fmt_errors,
        "warnings": 0,
    }

    # ================================================================
    # Stage 8: WRITE_OUTPUTS — persist via OutputPort
    # ================================================================
    out.write_sv(sv_bundle)
    out.write_ml(ml_rows)

    llm_output = llm_contexts[0] if len(llm_contexts) == 1 else llm_contexts
    out.write_llm(llm_output)

    for suffix, ml_model_data in model_ml_outputs.items():
        out.write_ml_model(ml_model_data, suffix)

    for suffix, llm_model_data in model_llm_outputs.items():
        out.write_llm_model(llm_model_data, suffix)

    # Count flag severities across all transactions for report
    all_dropped_for_severity = dropped_txs + dedupe_drops
    by_severity = _count_flags_by_severity(deduped_txs, all_dropped_for_severity)

    # Combine invariant drops + mapping drops + dedupe drops for total dropped count
    total_dropped = len(dropped_txs) + len(mapping_drops) + len(dedupe_drops)

    # Build dropped_details
    all_dropped_details = _build_dropped_details(dropped_txs, dedupe_drops, mapping_drops)

    # ----------------------------------------------------------------
    # SLI-3 invariant compliance counters
    # ----------------------------------------------------------------
    # critical_invariant_violations_total = records with ERROR-level invariant
    # violations only.  Excludes mapping drops, dedupe drops, WARN-only records.
    critical_invariant_violations_total = len(dropped_txs)

    # Count kept records that have WARN-level invariant flags (INV-04/05/10).
    # These are non-compliant for SLI-3 even though they were not dropped.
    # Only count WARN-level invariant flags (INV-04/05/10); ERROR-level
    # invariants already caused drops and are counted via len(dropped_txs).
    warn_flagged_kept = sum(
        1 for tx in deduped_txs
        if any(
            f["id"].startswith("INV-") and f.get("severity") == "WARN"
            for f in tx.get("flags", [])
        )
    )

    # invariant_correct_total = invariant_checked_total
    #     − ERROR invariant drops (dropped_txs)
    #     − INV-09 dedupe drops (dedupe_drops)
    #     − kept records with WARN invariant flags
    invariant_correct_total = (
        invariant_checked_total
        - len(dropped_txs)
        - len(dedupe_drops)
        - warn_flagged_kept
    )

    # ----------------------------------------------------------------
    # Gate: error-drop count (uses same logic as determine_outcome)
    # ----------------------------------------------------------------
    run_policy = profile.get("run_policy", {}).get("partial_success_policy", {})
    fail_on = run_policy.get("fail_on", {})
    fail_severity = fail_on.get("any_severity", "ERROR")
    fail_ratio = fail_on.get("ratio_over_records", 0.05)

    error_drops = _count_error_drops(dropped_txs, mapping_drops, fail_severity)

    # Compute derived metrics (SLI-2, QC-2, SLI-3, gate, informative)
    metrics = _compute_metrics(
        input_records_total=total_raw,
        passed_validation_total=len(deduped_txs),
        dropped_total=total_dropped,
        dropped_details_count=len(all_dropped_details),
        ml_rows_count=len(ml_rows),
        invariant_checked_total=invariant_checked_total,
        invariant_correct_total=invariant_correct_total,
        critical_invariant_violations_total=critical_invariant_violations_total,
        error_drops=error_drops,
    )

    # Determine outcome using run_policy gate from default.yaml
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
        "CHECK_INVARIANTS", "PROJECT_ML", "PROJECT_LLM",
        "FORMAT_FOR_MODEL", "WRITE_OUTPUTS",
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
        metrics=metrics,
        report_extensions=report_extensions_out or None,
        extra_projections_audit=extra_projections_audit or None,
    )
    out.write_report(report)

    # --- Return summary (no run_folder — FS callers get it from FsOutputAdapter.run_folder) ---
    return {
        "outcome": outcome,
        "stop_reason": stop_reason,
        "run_id": run_id,
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
        "metrics": metrics,
    }
