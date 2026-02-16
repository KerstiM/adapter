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
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import jsonschema
import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADAPTER_VERSION = "0.1.0"
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
    """Resolve a spec path from the profile; handles S-00 vs S-00A naming."""
    path = REPO_ROOT / relpath
    if path.exists():
        return path
    # Fallback: match by the descriptive suffix after the first underscore
    # e.g. "S-00_berlin_accounts.schema.json" -> find "*_berlin_accounts.schema.json"
    parent = path.parent
    if parent.is_dir() and "_" in path.name:
        suffix_part = path.name.split("_", 1)[1]  # "berlin_accounts.schema.json"
        for candidate in sorted(parent.iterdir()):
            if candidate.is_file() and candidate.name.endswith(suffix_part):
                return candidate
    raise FileNotFoundError(f"Cannot resolve spec path: {relpath}")


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
        resolved["contracts"][key] = _load_yaml_file(REPO_ROOT / relpath)

    # Load rulesets
    resolved["rulesets"] = {}
    for key, relpath in profile.get("rulesets", {}).items():
        resolved["rulesets"][key] = _load_yaml_file(REPO_ROOT / relpath)

    return resolved


# ---------------------------------------------------------------------------
# Helpers — data utilities
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_prefix(created_at_utc: str) -> str:
    """Derive a filesystem-safe timestamp prefix from an ISO timestamp."""
    return created_at_utc.replace("-", "").replace(":", "").replace("T", "T").split(".")[0]


def _parse_decimal(s: str | None) -> Decimal | None:
    if s is None:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _decimal_str(d: Decimal) -> str:
    """Canonical decimal string without scientific notation."""
    return format(d.normalize(), "f")


def _is_iso_date(s: str | None) -> bool:
    if not s:
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _hash_record_id(parts: list[str]) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


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


# ---------------------------------------------------------------------------
# Stage 2: Map RAW -> SV (C-01)
# ---------------------------------------------------------------------------

def _infer_direction(raw_tx: dict, amount_raw: str) -> str:
    if raw_tx.get("debtorName"):
        return "IN"
    if raw_tx.get("creditorName"):
        return "OUT"
    if amount_raw.startswith("-"):
        return "OUT"
    return "IN"


def _pick_counterparty(raw_tx: dict, direction: str) -> dict:
    if direction == "OUT":
        return {
            "role": "CREDITOR",
            "name": raw_tx.get("creditorName"),
            "iban": (raw_tx.get("creditorAccount") or {}).get("iban"),
        }
    elif direction == "IN":
        return {
            "role": "DEBTOR",
            "name": raw_tx.get("debtorName"),
            "iban": (raw_tx.get("debtorAccount") or {}).get("iban"),
        }
    return {"role": "UNKNOWN", "name": None, "iban": None}


def _map_single_transaction(
    raw_tx: dict,
    account_id: str,
    status: str,
    source_index: int,
    source_file: str,
    status_key: str,
) -> dict | None:
    """Map one Berlin AIS transaction to SV transaction shape. Returns None on parse failure."""
    amount_raw = (raw_tx.get("transactionAmount") or {}).get("amount")
    if amount_raw is None:
        return None
    amt = _parse_decimal(amount_raw)
    if amt is None:
        return None

    currency = ((raw_tx.get("transactionAmount") or {}).get("currency") or "").upper()

    booking_date = raw_tx.get("bookingDate")
    value_date = raw_tx.get("valueDate")
    value_date_fell_back = False
    if not value_date:
        if booking_date and _is_iso_date(booking_date):
            value_date = booking_date
            value_date_fell_back = True
        else:
            return None  # unmappable: no valueDate and no valid bookingDate fallback

    direction = _infer_direction(raw_tx, amount_raw)

    amount_abs = _decimal_str(abs(amt))
    if direction == "OUT":
        amount_signed = "-" + amount_abs if not amount_abs.startswith("-") else amount_abs
    else:
        amount_signed = amount_abs

    # MAP-01: valueDate fallback flag
    flags: list[dict] = []
    if value_date_fell_back:
        flags.append({
            "id": "MAP-01_VALUE_DATE_FALLBACK",
            "severity": "WARN",
            "message": "valueDate missing; fell back to bookingDate.",
        })

    # INV-05: check if raw sign mismatches derived direction -> flag
    raw_is_negative = amount_raw.strip().startswith("-")
    if (direction == "OUT" and not raw_is_negative and amt != 0) or \
       (direction == "IN" and raw_is_negative):
        flags.append({
            "id": "INV-05_AMOUNT_SIGN_MATCHES_DIRECTION",
            "severity": "WARN",
            "message": "raw amount sign mismatched derived direction; normalized signed amount.",
        })

    counterparty = _pick_counterparty(raw_tx, direction)
    remittance = raw_tx.get("remittanceInformationUnstructured")
    transaction_id = raw_tx.get("transactionId")

    record_id = _hash_record_id([
        account_id,
        status,
        booking_date or "",
        value_date,
        amount_signed,
        currency,
        counterparty.get("name") or "",
        remittance or "",
        transaction_id or "",
    ])

    input_path = f"$.transactions.{status_key}[{source_index}]"

    return {
        "record_id": record_id,
        "transaction_id": transaction_id,
        "account_id": account_id,
        "status": status,
        "booking_date": booking_date,
        "value_date": value_date,
        "amount": {
            "currency": currency,
            "raw": amount_raw,
            "signed": amount_signed,
            "abs": amount_abs,
        },
        "direction": direction,
        "counterparty": counterparty,
        "remittance": remittance,
        "flags": flags,
        "source": {
            "input_file": source_file,
            "input_path": input_path,
        },
    }


def _flatten_report_file(
    tx_data: dict,
    account_id: str,
    source_file: str,
) -> tuple[list[dict], list[dict]]:
    """Flatten a single report file into SV transactions (C-01 flatten rules).

    Returns (mapped_transactions, mapping_drops).
    mapping_drops contains info dicts for raw transactions that could not be
    mapped (e.g. missing valueDate with no bookingDate fallback).
    """
    transactions_obj = tx_data.get("transactions") or {}
    sv_txs: list[dict] = []
    mapping_drops: list[dict] = []

    status_map = {
        "booked": "BOOKED",
        "pending": "PENDING",
        "information": "INFORMATION",
    }

    for key, status in status_map.items():
        raw_list = transactions_obj.get(key, [])
        for i, raw_tx in enumerate(raw_list):
            sv_tx = _map_single_transaction(
                raw_tx, account_id, status, i, source_file, key,
            )
            if sv_tx:
                sv_txs.append(sv_tx)
            else:
                # Determine drop reason
                amount_obj = raw_tx.get("transactionAmount") or {}
                has_amount = amount_obj.get("amount") is not None and _parse_decimal(amount_obj.get("amount")) is not None
                has_value_date = bool(raw_tx.get("valueDate"))
                has_booking_date = bool(raw_tx.get("bookingDate") and _is_iso_date(raw_tx.get("bookingDate")))

                if not has_amount:
                    reason = "transactionAmount missing or unparseable"
                elif not has_value_date and not has_booking_date:
                    reason = "valueDate missing and no valid bookingDate for fallback"
                else:
                    reason = "unmappable (unknown cause)"

                mapping_drops.append({
                    "source_file": source_file,
                    "input_path": f"$.transactions.{key}[{i}]",
                    "transaction_id": raw_tx.get("transactionId"),
                    "drop_reason": reason,
                    "status": status,
                })

    return sv_txs, mapping_drops


def _build_sv_bundle(
    accounts_data: dict,
    report_files: list[tuple[str, dict]],
    run_id: str,
    created_at_utc: str,
    profile: dict,
) -> tuple[dict, list[dict]]:
    """Build the full SVBundle from accounts + flattened report files.

    Returns (sv_bundle, mapping_drops) where mapping_drops lists raw
    transactions that could not be mapped to SV format.
    """
    raw_accounts = accounts_data.get("accounts", [])
    if not raw_accounts:
        return {"meta": {}, "accounts": [], "transactions": []}, []

    sv_accounts = []
    iban_to_account_id: dict[str, str] = {}
    for raw_acct in raw_accounts:
        account_id = raw_acct.get("resourceId", "unknown")
        iban = raw_acct.get("iban")
        if iban:
            iban_to_account_id[iban] = account_id

        sv_accounts.append({
            "account_id": account_id,
            "iban": iban,
            "currency": (raw_acct.get("currency") or "").upper(),
            "name": raw_acct.get("name"),
        })

    all_transactions: list[dict] = []
    all_mapping_drops: list[dict] = []
    for source_file, tx_data in report_files:
        report_iban = (tx_data.get("account") or {}).get("iban")
        account_id = iban_to_account_id.get(report_iban, sv_accounts[0]["account_id"])
        sv_txs, mapping_drops = _flatten_report_file(tx_data, account_id, source_file)
        all_transactions.extend(sv_txs)
        all_mapping_drops.extend(mapping_drops)

    # Build spec_versions from profile contracts/rulesets
    spec_versions = {}
    for key in ("S-00A", "S-00B", "S-01", "C-01", "R-01", "C-02", "C-03"):
        # Try schemas first, then contracts, then rulesets
        for section in ("schemas", "contracts", "rulesets"):
            src = profile.get(section, {}).get(key)
            if isinstance(src, dict) and "version" in src:
                spec_versions[key] = src["version"]
                break
        if key not in spec_versions:
            spec_versions[key] = profile.get("version", "1.0.0")

    meta = {
        "run_id": run_id,
        "created_at_utc": created_at_utc,
        "profile_id": profile["id"],
        "spec_versions": spec_versions,
    }

    return {
        "meta": meta,
        "accounts": sv_accounts,
        "transactions": all_transactions,
    }, all_mapping_drops


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
# Stage 4: Check invariants (R-01)
# ---------------------------------------------------------------------------

def _check_invariants(sv_bundle: dict) -> tuple[list[dict], list[dict]]:
    """
    Check R-01 invariants on each transaction.
    Returns (valid_transactions, dropped_transactions).
    """
    valid = []
    dropped = []

    for tx in sv_bundle.get("transactions", []):
        drop = False
        amount = tx.get("amount", {})

        # INV-01: currency format
        currency = amount.get("currency", "")
        if not re.match(r"^[A-Z]{3}$", currency):
            tx["flags"].append({
                "id": "INV-01_CURRENCY_FORMAT",
                "severity": "ERROR",
                "message": "currency invalid.",
            })
            drop = True

        # INV-02: value_date required
        if not tx.get("value_date"):
            tx["flags"].append({
                "id": "INV-02_VALUE_DATE_REQUIRED",
                "severity": "ERROR",
                "message": "valueDate missing.",
            })
            drop = True

        # INV-03: amount parseable
        for key in ("raw", "signed", "abs"):
            if _parse_decimal(amount.get(key)) is None:
                tx["flags"].append({
                    "id": "INV-03_AMOUNT_PARSEABLE",
                    "severity": "ERROR",
                    "message": f"amount.{key} not parseable.",
                })
                drop = True
                break

        if drop:
            dropped.append(tx)
            continue

        # INV-04: booking_date optional but valid if present
        bd = tx.get("booking_date")
        if bd is not None and not _is_iso_date(bd):
            tx["flags"].append({
                "id": "INV-04_BOOKING_DATE_OPTIONAL",
                "severity": "WARN",
                "message": "bookingDate present but invalid.",
            })

        # INV-05 already handled during mapping (flags_extra in C-01)

        # INV-10: counterparty all null
        cp = tx.get("counterparty", {})
        if cp.get("name") is None and cp.get("iban") is None:
            tx["flags"].append({
                "id": "INV-10_COUNTERPARTY_ALL_NULL",
                "severity": "WARN",
                "message": "counterparty present but all fields null.",
            })

        valid.append(tx)

    return valid, dropped


def _deduplicate_transactions(
    transactions: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Deduplicate SV transactions by (account_id, record_id) — INV-09.

    Within each group of duplicates the "winner" is chosen deterministically
    by sorting on (source.input_file, source.input_path, status, value_date,
    booking_date, transaction_id).  All others are flagged WARN and dropped.

    Returns (kept, dedupe_drops).
    """
    from collections import OrderedDict

    def _sort_key(tx: dict) -> tuple:
        src = tx.get("source", {})
        return (
            src.get("input_file", ""),
            src.get("input_path", ""),
            tx.get("status", ""),
            tx.get("value_date", ""),
            tx.get("booking_date") or "",
            tx.get("transaction_id") or "",
        )

    # Group by (account_id, record_id), preserving insertion order.
    groups: dict[tuple[str, str], list[dict]] = OrderedDict()
    for tx in transactions:
        key = (tx["account_id"], tx["record_id"])
        groups.setdefault(key, []).append(tx)

    kept: list[dict] = []
    dedupe_drops: list[dict] = []
    for (_aid, _rid), group in groups.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        # Sort deterministically; keep first.
        group.sort(key=_sort_key)
        kept.append(group[0])
        for dup in group[1:]:
            dup["flags"].append({
                "id": "INV-09_DUPLICATE_RECORD_ID",
                "severity": "WARN",
                "message": "Duplicate record_id within account; keeping first deterministically.",
            })
            dedupe_drops.append(dup)

    return kept, dedupe_drops


# ---------------------------------------------------------------------------
# Stage 5a: ML projection (C-02)
# ---------------------------------------------------------------------------

def _project_ml(sv_bundle: dict) -> list[dict]:
    """
    Project SV -> ML CSV rows (C-02).
    Filter: BOOKED + PENDING.
    Sort: account_id, value_date, record_id.
    """
    rows = []
    for tx in sv_bundle.get("transactions", []):
        if tx["status"] not in ("BOOKED", "PENDING"):
            continue

        rows.append({
            "account_id": tx["account_id"],
            "record_id": tx["record_id"],
            "status": tx["status"],
            "booking_date": tx.get("booking_date") or "",
            "value_date": tx["value_date"],
            "direction": tx["direction"],
            "currency": tx["amount"]["currency"],
            "signed_amount": tx["amount"]["signed"],
            "abs_amount": tx["amount"]["abs"],
            "counterparty_name": (tx.get("counterparty") or {}).get("name") or "",
            "remittance": tx.get("remittance") or "",
        })

    rows.sort(key=lambda r: (r["account_id"], r["value_date"], r["record_id"]))

    for i, row in enumerate(rows, 1):
        row["row_id"] = i

    return rows


# ---------------------------------------------------------------------------
# Stage 5b: LLM projection (C-03)
# ---------------------------------------------------------------------------

def _project_llm(sv_bundle: dict, profile: dict) -> list[dict]:
    """
    Project SV -> LLM context JSON (C-03), one per account.
    Filter: BOOKED + PENDING.
    Sort: value_date, record_id.
    Window: last N.
    """
    c03 = profile.get("contracts", {}).get("C-03", {})
    max_n = c03.get("window", {}).get("last_n", 200)
    max_cp_len = c03.get("truncate", {}).get("counterparty_name_max_len", 80)
    max_rem_len = c03.get("truncate", {}).get("remittance_max_len", 160)

    # Group transactions by account
    by_account: dict[str, list[dict]] = {}
    for tx in sv_bundle.get("transactions", []):
        if tx["status"] not in ("BOOKED", "PENDING"):
            continue
        by_account.setdefault(tx["account_id"], []).append(tx)

    contexts = []
    for sv_acct in sv_bundle.get("accounts", []):
        account_id = sv_acct["account_id"]
        txs = by_account.get(account_id, [])

        # Sort by value_date, record_id
        txs.sort(key=lambda t: (t["value_date"], t["record_id"]))
        # Window: last N
        txs = txs[-max_n:]

        mapped_txs = []
        for tx in txs:
            cp_name = (tx.get("counterparty") or {}).get("name") or ""
            if len(cp_name) > max_cp_len:
                cp_name = cp_name[:max_cp_len]
            rem = tx.get("remittance") or ""
            if len(rem) > max_rem_len:
                rem = rem[:max_rem_len]

            mapped_txs.append({
                "id": tx["record_id"],
                "d": tx["value_date"],
                "s": tx["status"],
                "dir": tx["direction"],
                "a": tx["amount"]["signed"],
                "c": tx["amount"]["currency"],
                "cp": cp_name or None,
                "r": rem or None,
            })

        context = {
            "meta": {
                "run_id": sv_bundle["meta"]["run_id"],
                "created_at_utc": sv_bundle["meta"]["created_at_utc"],
                "account_id": account_id,
                "iban": sv_acct["iban"],
                "currency": sv_acct["currency"],
            },
            "tx": mapped_txs,
        }
        contexts.append(context)

    return contexts


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _count_flags_by_severity(sv_transactions: list[dict], dropped: list[dict]) -> dict[str, int]:
    """Count flag severities across all transactions (valid + dropped)."""
    counts: dict[str, int] = {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0}
    for tx in sv_transactions + dropped:
        for flag in tx.get("flags", []):
            sev = flag.get("severity", "")
            if sev in counts:
                counts[sev] += 1
    return counts


def _build_report(
    run_id: str,
    created_at_utc: str,
    profile: dict,
    data_dir: Path,
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
) -> dict:
    """Build report.json structure (S-05 compliant)."""
    return {
        "report_schema_version": "1.0.0",
        "run": {
            "run_id": run_id,
            "created_at_utc": created_at_utc,
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
    report_files: list[tuple[str, dict]] = []
    for fname in ("transactions.json", "standing_orders.json"):
        fpath = data_dir / fname
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                tx_data = json.load(f)
            tx_errors = _validate_raw_transactions(tx_data, profile["schemas"]["S-00B"])
            issues.extend(tx_errors)
            stage_errors_1 += len(tx_errors)
            report_files.append((fname, tx_data))

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

    # Build dropped_details: invariant drops + mapping drops + dedupe drops
    all_dropped_details: list[dict] = []
    for tx in dropped_txs:
        error_flags = [f for f in tx.get("flags", []) if f["severity"] == "ERROR"]
        all_dropped_details.append({
            "source_file": tx.get("source", {}).get("input_file"),
            "input_path": tx.get("source", {}).get("input_path"),
            "transaction_id": tx.get("transaction_id"),
            "drop_reason": "; ".join(f["message"] for f in error_flags) or "invariant check failed",
        })
    for tx in dedupe_drops:
        all_dropped_details.append({
            "source_file": tx.get("source", {}).get("input_file"),
            "input_path": tx.get("source", {}).get("input_path"),
            "transaction_id": tx.get("transaction_id"),
            "record_id": tx.get("record_id"),
            "drop_reason": "duplicate record_id",
        })
    all_dropped_details.extend(mapping_drops)

    # Determine outcome using run_policy fail gate from default.yaml
    # fail_on: any_severity=ERROR, ratio_over_records=0.05
    run_policy = profile.get("run_policy", {}).get("partial_success_policy", {})
    fail_on = run_policy.get("fail_on", {})
    fail_severity = fail_on.get("any_severity", "ERROR")
    fail_ratio = fail_on.get("ratio_over_records", 0.05)

    # Count drops at the fail severity or higher.
    # INFORMATION txs that fail to map are expected omissions, not data errors,
    # so exclude them from the fail-gate ratio.
    severity_rank = {"INFO": 0, "WARN": 1, "ERROR": 2, "CRITICAL": 3}
    fail_rank = severity_rank.get(fail_severity, 2)
    error_drops = 0
    for tx in dropped_txs:
        if tx.get("status") == "INFORMATION":
            continue
        for flag in tx.get("flags", []):
            if severity_rank.get(flag["severity"], 0) >= fail_rank:
                error_drops += 1
                break
    for md in mapping_drops:
        if md.get("status") != "INFORMATION":
            error_drops += 1

    drop_ratio = error_drops / total_raw if total_raw > 0 else 0.0
    if drop_ratio > fail_ratio:
        outcome = "FAIL"
        stop_reason = f"error drop ratio {drop_ratio:.4f} exceeds threshold {fail_ratio}"
    elif by_severity["ERROR"] > 0 or any(i.get("code", "").startswith("S-01") for i in issues):
        outcome = "PARTIAL_SUCCESS"
        stop_reason = "errors present but below fail threshold"
    elif run_flags or by_severity["WARN"] > 0:
        outcome = "PARTIAL_SUCCESS"
        stop_reason = "warnings present"
    else:
        outcome = "SUCCESS"
        stop_reason = "all validations passed"

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

    # report.json
    report = _build_report(
        run_id=run_id,
        created_at_utc=created_at_utc,
        profile=profile,
        data_dir=data_dir,
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
