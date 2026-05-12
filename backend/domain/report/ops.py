"""
Domain report operations: pure helpers for building pipeline reports.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

from typing import Any

ADAPTER_VERSION = "0.1.0"

SEVERITY_RANK: dict[str, int] = {"INFO": 0, "WARN": 1, "ERROR": 2, "CRITICAL": 3}


# SLI-1 katvusdeklaratsioon: SV prioriteetsete väljade kohta, millele C-01
# defineerib kaardistuse või tuletuse. Käsitsi hooldatav — peab püsima C-01
# `map_single_transaction()` teostusega kooskõlas. Skoop: kõik tehingutaseme
# väljad S-01-st (sh `source.*` jälgitavuseks); välja jäävad `SVBundle.meta`,
# `accounts` (kaardistatud eraldi) ja `flags[]` (annotatsioonid, mitte väljad).
SLI1_FIELD_COVERAGE: dict[str, bool] = {
    # Identity & classification
    "record_id":            True,   # SHA-256 hash derived from composite key
    "transaction_id":       True,   # mapped from raw transactionId
    "account_id":           True,   # mapped from raw account resourceId
    "status":               True,   # mapped from booked/pending/information category

    # Dates
    "booking_date":         True,   # mapped from raw bookingDate
    "value_date":           True,   # mapped from raw valueDate (with fallback)

    # Amount
    "amount.currency":      True,   # mapped from raw transactionAmount.currency
    "amount.raw":           True,   # mapped from raw transactionAmount.amount
    "amount.signed":        True,   # derived: abs value + direction sign
    "amount.abs":           True,   # derived: absolute value of raw amount

    # Direction
    "direction":            True,   # inferred from debtor/creditor/sign heuristic

    # Counterparty
    "counterparty.role":    True,   # inferred from direction
    "counterparty.name":    True,   # mapped from raw creditorName/debtorName
    "counterparty.iban":    True,   # mapped from raw creditorAccount/debtorAccount

    # Remittance
    "remittance":           True,   # mapped from raw remittanceInformationUnstructured

    # Source lineage (included: traceability is a thesis design goal)
    "source.input_file":    True,   # constructed by C-01 for traceability
    "source.input_path":    True,   # constructed by C-01 (JSON path expression)
}


def compute_sli1_coverage(
    coverage_map: dict[str, bool] | None = None,
) -> dict[str, float | int]:
    """SLI-1 skeemikatvus: prioriteetsete SV väljade katvus.

    SLI-1 = covered_priority_fields / all_priority_fields

    Spetsifikatsioonitaseme näitaja, mis põhineb hooldataval
    katvusdeklaratsioonil SLI1_FIELD_COVERAGE. Ei sõltu jooksuandmetest
    ega konkreetsest andmestikust.

    Parameters
    ----------
    coverage_map : dict[str, bool] | None
        Asendab vaikimisi SLI1_FIELD_COVERAGE testide jaoks.

    Returns
    -------
    dict with keys:
        sli1_coverage_ratio : float   (0–1, rounded to 4 decimals)
        priority_sv_fields_total : int
        covered_priority_sv_fields : int
    """
    cmap = coverage_map if coverage_map is not None else SLI1_FIELD_COVERAGE
    total = len(cmap)
    covered = sum(1 for is_covered in cmap.values() if is_covered)
    ratio = covered / total if total > 0 else 0.0

    return {
        "sli1_coverage_ratio": round(ratio, 4),
        "priority_sv_fields_total": total,
        "covered_priority_sv_fields": covered,
    }


def _lookup_dotted(obj: Any, dotted_path: str) -> Any:
    current: Any = obj
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def derive_sli1_coverage_from_sv(
    sv_bundle: dict[str, Any],
    priority_fields: list[str] | None = None,
) -> dict[str, bool]:
    """Tuleta runtime SLI-1 katvuskaart tegeliku SV bundle'i pealt.

    Iga prioriteetne tee loetakse "kaetuks", kui vähemalt ühes tehingus on
    vastav väli olemas ja mitte-null. See vaatleb C-01 **tegelikku** väljundit
    ja ei saa valetada (erinevalt deklaratsioonist SLI1_FIELD_COVERAGE).
    """
    fields = priority_fields if priority_fields is not None else list(SLI1_FIELD_COVERAGE.keys())
    transactions = sv_bundle.get("transactions", []) or []
    coverage: dict[str, bool] = {f: False for f in fields}
    for tx in transactions:
        for field in fields:
            if coverage[field]:
                continue
            value = _lookup_dotted(tx, field)
            if value not in (None, ""):
                coverage[field] = True
    return coverage


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


def count_issues_by_severity(issues: list[dict]) -> dict[str, int]:
    """Count severity levels across the full issues[] report array.

    Unlike count_flags_by_severity (which only counts tx-level flags),
    this covers all pipeline-level issues including READ_INPUT schema
    errors, STANDARDIZE_TO_SV mapping drops, and VALIDATE_SCHEMA errors.
    """
    counts: dict[str, int] = {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0}
    for issue in issues:
        sev = issue.get("severity", "")
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

    Gate semantics: **inclusive** (`drop_ratio >= fail_ratio` → FAIL).
    Threshold is profile-configured (`run_policy.partial_success_policy.
    fail_on.ratio_over_records`); default 0.05 is for prototype demo.
    """
    error_drops = count_error_drops(dropped_txs, mapping_drops, fail_severity)

    drop_ratio = error_drops / total_raw if total_raw > 0 else 0.0
    if drop_ratio >= fail_ratio:
        return "FAIL", f"error drop ratio {drop_ratio:.4f} exceeds threshold {fail_ratio}"
    elif by_severity["ERROR"] > 0 or any(i.get("severity") == "ERROR" for i in issues):
        return "PARTIAL_SUCCESS", "errors present but below fail threshold"
    elif run_flags or by_severity["WARN"] > 0:
        return "PARTIAL_SUCCESS", "warnings present"
    else:
        return "SUCCESS", "all validations passed"


def _compute_sli2(passed_validation_total: int, input_records_total: int) -> dict:
    """SLI-2: validation pass-through ratio.

    Töötlusse võetud sisendtehingute osakaal, mis jääb pärast kaardistust,
    invariantide kontrolli ja deduplikatsiooni standardiseeritud
    vaheesitusse alles.  = passed_validation_total / input_records_total
    """
    ratio = (
        passed_validation_total / input_records_total
        if input_records_total > 0
        else 1.0
    )
    return {"validation_pass_through_ratio": round(ratio, 4)}


def _compute_qc2(dropped_details_count: int, dropped_total: int) -> dict:
    """QC-2: drop-reporting coverage (operational control).

    All dropped records must appear in dropped_details[].
    Strict equality: over-reporting is treated as inconsistency.
    """
    if dropped_total > 0:
        ratio = dropped_details_count / dropped_total
        all_reported = dropped_details_count == dropped_total
    else:
        ratio = 1.0
        all_reported = True
    return {
        "drop_reporting_ratio": round(ratio, 4),
        "all_drops_reported": all_reported,
    }


def _compute_sli3(
    invariant_checked_total: int,
    invariant_correct_total: int,
    critical_invariant_violations_total: int,
) -> dict:
    """SLI-3: invariant compliance ratio.

    invariant_checked_total (nimetaja) = records entering Stage 4
        (CHECK_INVARIANTS) after mapping, before dedupe.  Mapping drops
        (Stage 2) EI KUULU nimetajasse, sest need kirjed ei jõua kunagi
        invariantide kontrollini.

    invariant_correct_total (lugeja) = invariant_checked_total
        − ERROR-taseme invariantrikkumistega langetatud kirjed
        − INV-09 deduplikatsioonis eemaldatud kirjed
        − alles jäävad WARN-lipuga kirjed

    critical_invariant_violations_total = records with ERROR-level invariant
        violations only.  Excludes mapping drops, dedupe drops, WARN-only.
    """
    ratio = (
        invariant_correct_total / invariant_checked_total
        if invariant_checked_total > 0
        else 1.0
    )
    return {
        "invariant_compliance_ratio": round(ratio, 4),
        "invariant_checked_total": invariant_checked_total,
        "invariant_correct_total": invariant_correct_total,
        "critical_invariant_violations_total": critical_invariant_violations_total,
    }


def _compute_gate(error_drops: int, input_records_total: int) -> dict:
    """Gate: operational error-drop fail policy (NOT an SLI).

    Uses count_error_drops() upstream — same logic as determine_outcome().
    Threshold (`fail_ratio`) lives in the profile under
    `run_policy.partial_success_policy.fail_on.ratio_over_records`.
    """
    ratio = error_drops / input_records_total if input_records_total > 0 else 0.0
    return {
        "error_drop_ratio": round(ratio, 4),
        "error_drops": error_drops,
    }


def _compute_info(ml_rows_count: int, input_records_total: int) -> dict:
    """Info: ML emission ratio (informative, NOT an SLI).

    End-to-end survival from raw input to ML projection.  Always ≤ SLI-2
    because ML projection excludes INFORMATION-status records that
    survive validation.
    """
    ratio = ml_rows_count / input_records_total if input_records_total > 0 else 0.0
    return {"ml_emission_ratio": round(ratio, 4)}


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

    Thin orchestrator — see ``_compute_sli2``/``_compute_qc2``/``_compute_sli3``/
    ``_compute_gate``/``_compute_info`` (and module-level
    ``compute_sli1_coverage``) for the per-group definitions.

    Counter mapping (current codebase → frozen definitions):
      transactions_total        → input_records_total  (= total_raw in pipeline)
      transactions_emitted_sv   → passed_validation_total  (= len(deduped_txs))
      transactions_dropped      → dropped_total

    Identity: input_records_total == passed_validation_total + dropped_total
    """
    if invariant_correct_total < 0:
        raise ValueError(
            f"invariant_correct_total must be >= 0, got {invariant_correct_total} "
            f"(checked={invariant_checked_total})"
        )

    return {
        "sli1": compute_sli1_coverage(),
        "sli2": _compute_sli2(passed_validation_total, input_records_total),
        "qc2": _compute_qc2(dropped_details_count, dropped_total),
        "sli3": _compute_sli3(
            invariant_checked_total,
            invariant_correct_total,
            critical_invariant_violations_total,
        ),
        "gate": _compute_gate(error_drops, input_records_total),
        "info": _compute_info(ml_rows_count, input_records_total),
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
    by_severity_issues: dict[str, int],
    stage_log: list[dict],
    run_flags: list[dict],
    issues: list[dict],
    dropped_details: list[dict] | None = None,
    metrics: dict | None = None,
    *,
    sv_schema_version: str = "1.0.0",
    mapping_version: str = "1.0.0",
    ruleset_version: str = "1.1.0",
    spec_lock_sha256: str | None = None,
    input_fingerprint: str | None = None,
    output_artifact_hashes: dict[str, str] | None = None,
    report_extensions: dict[str, Any] | None = None,
    extra_projections_audit: list[dict] | None = None,
) -> dict:
    """Build report.json structure (S-05 compliant).

    Pure function — takes pre-resolved scalars, no Path/I/O.

    SLI-5 auditijälje väljad:
      Kohustuslikud (run sektsioon): sv_schema_version, mapping_version,
      ruleset_version, adapter_version.
      Soovitavad (kui antud): spec_lock_sha256, input_fingerprint,
      output_artifact_hashes.

    Opt-in raporti laiendused:
      Kui *report_extensions* on mitte-tühi dict, lisatakse see juuretasemel
      ``"extensions"`` võtmesse. Tühja dict'i või ``None`` puhul ``extensions``
      võtit ei teki — vaikekäitumine jääb baidi-täpselt samaks.

    Extra projektsioonide auditijälg:
      Kui *extra_projections_audit* on mitte-tühi list, lisatakse see
      juuretasemel ``"extra_projections"`` võtmesse.  Iga kirje sisaldab
      projektsiooni nime, lepingu ID/versiooni, skeemi ID-d, väljundfaili
      teed, kirjete arvu ja valideerimistulemust.
    """
    run_section: dict = {
        "run_id": run_id,
        "created_at_utc": created_at_utc,
        "profile_id": profile_id,
        "dataset_id": dataset_id,
        "input_dir": input_dir,
        "adapter_version": ADAPTER_VERSION,
        "sv_schema_version": sv_schema_version,
        "mapping_version": mapping_version,
        "ruleset_version": ruleset_version,
    }
    if spec_lock_sha256 is not None:
        run_section["spec_lock_sha256"] = spec_lock_sha256
    if input_fingerprint is not None:
        run_section["input_fingerprint"] = input_fingerprint

    report: dict = {
        "report_schema_version": "1.4.0",
        "run": run_section,
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
            "by_severity_issues": by_severity_issues,
        },
        "run_flags": run_flags,
        "issues": issues,
        "dropped_details": dropped_details or [],
    }
    if output_artifact_hashes is not None:
        report["output_artifact_hashes"] = output_artifact_hashes
    if metrics is not None:
        report["metrics"] = metrics
    if report_extensions:
        report["extensions"] = report_extensions
    if extra_projections_audit:
        report["extra_projections"] = extra_projections_audit
    return report


# ---------------------------------------------------------------------------
# SLI-5: Auditijälje täielikkus — nõutud auditiväljade kontroll
# ---------------------------------------------------------------------------

#: Kohustuslikud auditiväljad, mis peavad olema report.run sektsioonis.
SLI5_REQUIRED_AUDIT_FIELDS: list[str] = [
    "sv_schema_version",
    "mapping_version",
    "ruleset_version",
    "adapter_version",
]

#: Soovitavad lisaväljad auditijälje täielikkuse tõstmiseks.
SLI5_OPTIONAL_AUDIT_FIELDS: list[str] = [
    "spec_lock_sha256",
    "input_fingerprint",
]

#: Soovitavad väljundartefaktide räsid (report juuretasemel).
SLI5_OPTIONAL_ARTIFACT_HASH_KEYS: list[str] = [
    "sv",
    "ml",
    "llm",
    "report",
]


def _is_substantive(value: Any) -> bool:
    """Kontrollib, kas auditivälja väärtus on sisuliselt olemas.

    Sisuline olemasolu tähendab:
    - väli ei ole None
    - väli ei ole tühi string (ka pärast trimmimist)
    """
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


def compute_sli5_audit_completeness(report: dict) -> dict[str, float | int]:
    """SLI-5 auditijälje täielikkus.

    SLI-5 = sisuliselt olemasolevad nõutud auditiväljad / kõik nõutud auditiväljad

    Kohustuslik auditiväli loetakse olevaks ainult siis, kui:
    - väli on report.run sektsioonis olemas,
    - väärtus ei ole None,
    - väärtus ei ole tühi ega ainult tühikutest koosnev string.
    """
    run_section = report.get("run", {})
    present = sum(
        1 for field in SLI5_REQUIRED_AUDIT_FIELDS
        if field in run_section and _is_substantive(run_section[field])
    )
    total = len(SLI5_REQUIRED_AUDIT_FIELDS)
    ratio = present / total if total > 0 else 0.0

    return {
        "sli5_audit_completeness_ratio": round(ratio, 4),
        "required_fields_present": present,
        "required_fields_total": total,
    }
