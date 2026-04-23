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

from dataclasses import dataclass, field
from typing import Any

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
    count_issues_by_severity as _count_issues_by_severity,
    determine_outcome as _determine_outcome,
)
from domain.rules.invariants_r01 import (
    check_invariants as _check_invariants,
    deduplicate_transactions as _deduplicate_transactions,
)
from domain.rules.quality_checks import check_quality as _check_quality
from ports.clock_port import ClockPort
from ports.dataset_port import DatasetPort
from ports.output_port import OutputPort
from ports.spec_port import SpecPort
from ports.validation_port import ValidationPort


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
    validator: ValidationPort,
    data: dict,
    schema: dict,
    *,
    code: str,
    stage: str,
    source_lineage: str,
) -> list[dict]:
    """Validate *data* against *schema* via the injected validator and return Issue dicts.

    A successful validation returns an empty list.  A failure yields a single
    Issue dict with the given *code*/*stage*/*source_lineage* and the first
    schema error reported by the validator.  This helper backs all four of
    the pipeline's schema-validation stages (S-00A/B/C on RAW input, S-01 on
    the SV bundle).
    """
    raw_errors = validator.validate(data, schema)
    errors: list[dict] = []
    for raw in raw_errors:
        schema_id = code.split("_", 1)[0]
        errors.append({
            "code": code,
            "severity": "ERROR",
            "stage": stage,
            "message": f"{schema_id} validation: {raw['message']}",
            "refs": {
                "account_id": None,
                "record_id": None,
                "field_path": raw.get("field_path"),
                "source_lineage": source_lineage,
            },
        })
    return errors


# ---------------------------------------------------------------------------
# RunContext — accumulator for mutable pipeline state
# ---------------------------------------------------------------------------

@dataclass
class _RunContext:
    """Mutable accumulator threaded through stage helpers.

    Only the three list/dict accumulators below are mutated during a run;
    everything else (``run_id``, ``created_at_utc``, ``profile``) is read-only.
    """
    run_id: str
    created_at_utc: str
    profile: dict
    issues: list[dict] = field(default_factory=list)
    run_flags: list[dict] = field(default_factory=list)
    stage_log: dict[str, dict] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Stage helpers — each mutates ctx and returns stage-specific outputs
# ---------------------------------------------------------------------------

def _stage_read_input(
    dataset: DatasetPort,
    validator: ValidationPort,
    ctx: _RunContext,
) -> tuple[dict, list[tuple[str, dict]], int]:
    """Stage 1 — read RAW input via ports and validate against S-00A/B/C."""
    profile = ctx.profile
    stage_errors = 0
    stage_warnings = 0

    accounts_data = dataset.read_accounts()
    acct_errors = _validate_against_schema(
        validator,
        accounts_data,
        profile["schemas"]["S-00A"],
        code="S-00A_VALIDATION",
        stage="READ_INPUT",
        source_lineage="accounts.json",
    )
    ctx.issues.extend(acct_errors)
    stage_errors += len(acct_errors)

    report_files: list[tuple[str, dict]] = []
    for name in dataset.list_transaction_reports():
        tx_data = dataset.read_transactions_report(name)
        if name == "transactions_download.json":
            if _is_download_only(tx_data):
                ctx.run_flags.append({
                    "id": "RUN_DOWNLOAD_ONLY",
                    "severity": "WARN",
                    "message": "transaction report delivered as download link; not expanded in prototype.",
                })
                stage_warnings += 1
            else:
                tx_errors = _validate_against_schema(
                    validator,
                    tx_data,
                    profile["schemas"]["S-00B"],
                    code="S-00B_VALIDATION",
                    stage="READ_INPUT",
                    source_lineage="transactions.json",
                )
                ctx.issues.extend(tx_errors)
                stage_errors += len(tx_errors)
                report_files.append((name, tx_data))
        else:
            tx_errors = _validate_against_schema(
                validator,
                tx_data,
                profile["schemas"]["S-00B"],
                code="S-00B_VALIDATION",
                stage="READ_INPUT",
                source_lineage="transactions.json",
            )
            ctx.issues.extend(tx_errors)
            stage_errors += len(tx_errors)
            report_files.append((name, tx_data))

    so_data = dataset.read_standing_orders_optional()
    if so_data is not None:
        so_errors = _validate_against_schema(
            validator,
            so_data,
            profile["schemas"]["S-00C"],
            code="S-00C_VALIDATION",
            stage="READ_INPUT",
            source_lineage="standing_orders.json",
        )
        ctx.issues.extend(so_errors)
        stage_errors += len(so_errors)
        report_files.append(("standing_orders.json", so_data))

    total_raw = 0
    for _, tx_data in report_files:
        tx_obj = tx_data.get("transactions") or {}
        for key in ("booked", "pending", "information"):
            total_raw += len(tx_obj.get(key, []))

    ctx.stage_log["READ_INPUT"] = {
        "status": "OK" if stage_errors == 0 else "WARN",
        "errors": stage_errors,
        "warnings": stage_warnings,
    }
    return accounts_data, report_files, total_raw


def _stage_standardize_to_sv(
    accounts_data: dict,
    report_files: list[tuple[str, dict]],
    ctx: _RunContext,
) -> tuple[dict, list[dict]]:
    """Stage 2 — map RAW to canonical SV bundle (C-01)."""
    sv_bundle, mapping_drops, mapping_run_flags = _build_sv_bundle(
        accounts_data, report_files, ctx.run_id, ctx.created_at_utc, ctx.profile,
    )

    for mrf in mapping_run_flags:
        ctx.run_flags.append({
            "id": mrf["code"],
            "severity": mrf["severity"],
            "message": mrf["message"],
        })

    stage_warnings = len(mapping_drops)
    for md in mapping_drops:
        ctx.issues.append({
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
    ctx.stage_log["STANDARDIZE_TO_SV"] = {
        "status": "OK" if stage_warnings == 0 else "WARN",
        "errors": 0,
        "warnings": stage_warnings,
    }
    return sv_bundle, mapping_drops


def _stage_validate_sv_schema(
    sv_bundle: dict,
    validator: ValidationPort,
    ctx: _RunContext,
) -> None:
    """Stage 3 — validate the SV bundle against S-01."""
    sv_errors = _validate_against_schema(
        validator,
        sv_bundle,
        ctx.profile["schemas"]["S-01"],
        code="S-01_VALIDATION",
        stage="VALIDATE_SCHEMA",
        source_lineage="sv.json",
    )
    ctx.issues.extend(sv_errors)
    ctx.stage_log["VALIDATE_SCHEMA"] = {
        "status": "OK" if not sv_errors else "ERROR",
        "errors": len(sv_errors),
        "warnings": 0,
    }


def _stage_check_invariants(
    sv_bundle: dict,
    ctx: _RunContext,
) -> tuple[int, list[dict], list[dict], list[dict]]:
    """Stage 4 — R-01 field invariants + INV-09 dedupe + QC diagnostics."""
    invariant_checked_total = len(sv_bundle.get("transactions", []))

    r01_ruleset = ctx.profile["rulesets"]["R-01"]
    qc_ruleset = ctx.profile["rulesets"]["QC"]

    valid_txs, dropped_txs = _check_invariants(sv_bundle, r01_ruleset)
    deduped_txs, dedupe_drops = _deduplicate_transactions(valid_txs, r01_ruleset)
    sv_bundle["transactions"] = deduped_txs
    _check_quality(deduped_txs, qc_ruleset)

    inv_warnings = 0
    inv_errors = 0
    for tx in deduped_txs + dropped_txs + dedupe_drops:
        for flag in tx.get("flags", []):
            if flag["severity"] == "WARN":
                inv_warnings += 1
            elif flag["severity"] == "ERROR":
                inv_errors += 1
            ctx.issues.append({
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

    ctx.stage_log["CHECK_INVARIANTS"] = {
        "status": (
            "OK" if inv_errors == 0 and inv_warnings == 0
            else ("ERROR" if inv_errors > 0 else "WARN")
        ),
        "errors": inv_errors,
        "warnings": inv_warnings,
    }
    return invariant_checked_total, deduped_txs, dropped_txs, dedupe_drops


def _stage_project(
    sv_bundle: dict,
    ctx: _RunContext,
) -> tuple[list[dict], list[dict]]:
    """Stages 5 & 6 — ML (C-02) and LLM (C-03) projections."""
    ml_rows = _project_ml(sv_bundle)
    ctx.stage_log["PROJECT_ML"] = {"status": "OK", "errors": 0, "warnings": 0}

    llm_contexts = _project_llm(sv_bundle, ctx.profile)
    ctx.stage_log["PROJECT_LLM"] = {"status": "OK", "errors": 0, "warnings": 0}

    return ml_rows, llm_contexts


def _stage_report_extensions_and_extras(
    sv_bundle: dict,
    validator: ValidationPort,
    out: OutputPort,
    ctx: _RunContext,
) -> tuple[dict[str, Any], list[dict]]:
    """Opt-in report extensions and extra projections (profile-gated)."""
    profile = ctx.profile
    report_extensions_out: dict[str, Any] = {}
    projection_cache: dict[str, Any] = {}

    for ext_name in profile.get("report_extensions", []):
        if ext_name == "monthly_balance":
            projection_cache["monthly_balance"] = _project_monthly_balance(sv_bundle)
            report_extensions_out["monthly_balance"] = projection_cache["monthly_balance"]

    extra_projections_audit: list[dict] = []
    for proj_name in profile.get("extra_projections", []):
        dispatch = _EXTRA_PROJECTION_DISPATCH.get(proj_name)
        if dispatch is None:
            continue
        proj_fn, contract_key = dispatch

        contract = profile.get("contracts", {}).get(contract_key, {})
        output_cfg = contract.get("output") or {}
        schema_key = output_cfg.get("schema")
        output_file = output_cfg.get("file", f"projections/{proj_name}_v1.json")
        output_filename = output_file.rsplit("/", 1)[-1]

        if proj_name in projection_cache:
            proj_data = projection_cache[proj_name]
        else:
            proj_data = proj_fn(sv_bundle)

        validation_result = "PASS"
        if schema_key and schema_key in profile.get("schemas", {}):
            val_errors = validator.validate(proj_data, profile["schemas"][schema_key])
            if val_errors:
                first = val_errors[0]
                validation_result = f"FAIL: {first['message']}"
                ctx.issues.append({
                    "code": f"{schema_key}_VALIDATION",
                    "severity": "WARN",
                    "stage": "WRITE_OUTPUTS",
                    "message": f"{schema_key} validation ({proj_name}): {first['message']}",
                    "refs": {
                        "account_id": None,
                        "record_id": None,
                        "field_path": first.get("field_path"),
                        "source_lineage": f"extra_projection:{proj_name}",
                    },
                })

        out.write_extra_projection(proj_data, output_filename)

        extra_projections_audit.append({
            "name": proj_name,
            "enabled": True,
            "contract_id": contract.get("id", contract_key),
            "contract_version": contract.get("version", "unknown"),
            "schema_id": schema_key,
            "output_file": f"projections/{output_filename}",
            "item_count": len(proj_data),
            "validation_result": validation_result,
        })

    return report_extensions_out, extra_projections_audit


def _stage_format_for_model(
    ml_rows: list[dict],
    llm_contexts: list[dict],
    sv_bundle: dict,
    target_models_override: dict[str, Any] | None,
    ctx: _RunContext,
) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """Stage 7 — per-target-model formatting (C-04)."""
    target_models = ctx.profile.get("target_models", {})
    if target_models_override:
        target_models = {**target_models, **target_models_override}
    model_ml_outputs: dict[str, dict] = {}
    model_llm_outputs: dict[str, list[dict]] = {}

    c04 = ctx.profile.get("contracts", {}).get("C-04", {})
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

    ctx.stage_log["FORMAT_FOR_MODEL"] = {"status": "OK", "errors": 0, "warnings": 0}
    return model_ml_outputs, model_llm_outputs


def _stage_write_outputs(
    sv_bundle: dict,
    ml_rows: list[dict],
    llm_contexts: list[dict],
    model_ml_outputs: dict[str, dict],
    model_llm_outputs: dict[str, list[dict]],
    validator: ValidationPort,
    out: OutputPort,
    ctx: _RunContext,
) -> None:
    """Stage 8 — re-validate SV after Stage-4 mutations, then persist artefacts."""
    # Re-validate post Stage-4 (quality checks may have added flags).
    # This intentionally overwrites the stage_log["VALIDATE_SCHEMA"] entry
    # written in Stage 3 so the final report reflects the latest result.
    sv_errors_post = _validate_against_schema(
        validator,
        sv_bundle,
        ctx.profile["schemas"]["S-01"],
        code="S-01_VALIDATION",
        stage="VALIDATE_SCHEMA",
        source_lineage="sv.json",
    )
    ctx.issues.extend(sv_errors_post)
    ctx.stage_log["VALIDATE_SCHEMA"] = {
        "status": "OK" if not sv_errors_post else "ERROR",
        "errors": len(sv_errors_post),
        "warnings": 0,
    }

    out.write_sv(sv_bundle)
    out.write_ml(ml_rows)

    llm_output = llm_contexts[0] if len(llm_contexts) == 1 else llm_contexts
    out.write_llm(llm_output)

    for suffix, ml_model_data in model_ml_outputs.items():
        out.write_ml_model(ml_model_data, suffix)
    for suffix, llm_model_data in model_llm_outputs.items():
        out.write_llm_model(llm_model_data, suffix)

    ctx.stage_log["WRITE_OUTPUTS"] = {"status": "OK", "errors": 0, "warnings": 0}


_STAGE_ORDER = (
    "READ_INPUT", "STANDARDIZE_TO_SV", "VALIDATE_SCHEMA",
    "CHECK_INVARIANTS", "PROJECT_ML", "PROJECT_LLM",
    "FORMAT_FOR_MODEL", "WRITE_OUTPUTS",
)


def _stage_log_array(stage_log: dict[str, dict]) -> list[dict]:
    """Convert the mutable stage_log dict into the S-05-compliant array."""
    return [
        {
            "stage": stage_name,
            "errors": stage_log.get(stage_name, {}).get("errors", 0),
            "warnings": stage_log.get(stage_name, {}).get("warnings", 0),
            "infos": 0,
        }
        for stage_name in _STAGE_ORDER
    ]


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    dataset: DatasetPort,
    out: OutputPort,
    spec: SpecPort,
    clock: ClockPort,
    validator: ValidationPort,
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
    ctx = _RunContext(run_id=run_id, created_at_utc=created_at_utc, profile=profile)

    # Stage 1: READ_INPUT
    accounts_data, report_files, total_raw = _stage_read_input(dataset, validator, ctx)

    # Stage 2: STANDARDIZE_TO_SV
    sv_bundle, mapping_drops = _stage_standardize_to_sv(accounts_data, report_files, ctx)

    # Stage 3: VALIDATE_SCHEMA (first pass)
    _stage_validate_sv_schema(sv_bundle, validator, ctx)

    # Stage 4: CHECK_INVARIANTS + INV-09 dedupe + QC diagnostics
    invariant_checked_total, deduped_txs, dropped_txs, dedupe_drops = \
        _stage_check_invariants(sv_bundle, ctx)

    # Stages 5 & 6: PROJECT_ML, PROJECT_LLM
    ml_rows, llm_contexts = _stage_project(sv_bundle, ctx)

    # Opt-in report extensions + extra projections (profile-gated)
    report_extensions_out, extra_projections_audit = \
        _stage_report_extensions_and_extras(sv_bundle, validator, out, ctx)

    # Stage 7: FORMAT_FOR_MODEL
    model_ml_outputs, model_llm_outputs = _stage_format_for_model(
        ml_rows, llm_contexts, sv_bundle, target_models_override, ctx,
    )

    # Stage 8: WRITE_OUTPUTS (re-validate + persist)
    _stage_write_outputs(
        sv_bundle, ml_rows, llm_contexts,
        model_ml_outputs, model_llm_outputs,
        validator, out, ctx,
    )

    # ── Report + summary ──────────────────────────────────────────────────
    all_dropped_for_severity = dropped_txs + dedupe_drops
    by_severity = _count_flags_by_severity(deduped_txs, all_dropped_for_severity)
    by_severity_issues = _count_issues_by_severity(ctx.issues)

    total_dropped = len(dropped_txs) + len(mapping_drops) + len(dedupe_drops)
    all_dropped_details = _build_dropped_details(dropped_txs, dedupe_drops, mapping_drops)

    # SLI-3 invariant compliance counters:
    #   invariant_correct_total = invariant_checked_total
    #       − ERROR invariant drops (dropped_txs)
    #       − INV-09 dedupe drops (dedupe_drops)
    #       − kept records with WARN-level invariant flags (INV-04, INV-05).
    critical_invariant_violations_total = len(dropped_txs)
    warn_flagged_kept = sum(
        1 for tx in deduped_txs
        if any(
            f["id"].startswith("INV-") and f.get("severity") == "WARN"
            for f in tx.get("flags", [])
        )
    )
    invariant_correct_total = (
        invariant_checked_total
        - len(dropped_txs)
        - len(dedupe_drops)
        - warn_flagged_kept
    )

    # Gate: same fail_severity / fail_ratio used by determine_outcome
    run_policy = profile.get("run_policy", {}).get("partial_success_policy", {})
    fail_on = run_policy.get("fail_on", {})
    fail_severity = fail_on.get("any_severity", "ERROR")
    fail_ratio = fail_on.get("ratio_over_records", 0.05)

    error_drops = _count_error_drops(dropped_txs, mapping_drops, fail_severity)

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

    outcome, stop_reason = _determine_outcome(
        by_severity=by_severity,
        issues=ctx.issues,
        run_flags=ctx.run_flags,
        dropped_txs=dropped_txs,
        mapping_drops=mapping_drops,
        total_raw=total_raw,
        fail_severity=fail_severity,
        fail_ratio=fail_ratio,
    )

    sv_versions = sv_bundle.get("meta", {}).get("spec_versions", {})

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
        by_severity_issues=by_severity_issues,
        stage_log=_stage_log_array(ctx.stage_log),
        run_flags=ctx.run_flags,
        issues=ctx.issues,
        dropped_details=all_dropped_details,
        metrics=metrics,
        sv_schema_version=sv_versions.get("S-01", "1.0.0"),
        mapping_version=sv_versions.get("C-01", "1.0.0"),
        ruleset_version=sv_versions.get("R-01", "1.1.0"),
        report_extensions=report_extensions_out or None,
        extra_projections_audit=extra_projections_audit or None,
    )
    out.write_report(report)

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
        "by_severity_issues": by_severity_issues,
        "run_flags": ctx.run_flags,
        "issues": ctx.issues,
        "dropped_details": all_dropped_details,
        "metrics": metrics,
    }
