"""
Adapter pipeline: RAW (Berlin AIS) -> SV -> ML/LLM projections.

Implements the happy path:
  1. Read & validate RAW input (S-00A, S-00B) — multiple report files + download-only
  2. Map to SV (C-01) — flatten booked/pending/information, derive direction/counterparty/amounts
  3. Validate SV schema (S-01)
  4. Check invariants (R-01)
  5. Project to ML CSV (C-02) and LLM context JSON (C-03)
  6. Write outputs
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
# Helpers
# ---------------------------------------------------------------------------

def _load_schema(name: str) -> dict:
    path = SPEC_DIR / "schemas" / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_yaml(relpath: str) -> dict:
    path = SPEC_DIR / relpath
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


# ---------------------------------------------------------------------------
# Stage 1: Read & validate RAW input
# ---------------------------------------------------------------------------

def _validate_raw_accounts(accounts_data: dict) -> list[str]:
    """Returns list of error messages (empty = valid)."""
    errors = []
    try:
        schema = _load_schema("S-00A_berlin_accounts.schema.json")
        jsonschema.validate(accounts_data, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"S-00A validation: {e.message}")
    return errors


def _validate_raw_transactions(tx_data: dict) -> list[str]:
    """Returns list of error messages (empty = valid)."""
    errors = []
    try:
        schema = _load_schema("S-00B_berlin_transactions.schema.json")
        jsonschema.validate(tx_data, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"S-00B validation: {e.message}")
    return errors


# ---------------------------------------------------------------------------
# Stage 2: Map RAW -> SV (C-01)
# ---------------------------------------------------------------------------

def _infer_direction(raw_tx: dict, amount_raw: str) -> str:
    """
    C-01 derive.direction:
      if exists(debtor_name)  -> "IN"
      else if exists(creditor_name) -> "OUT"
      else if starts_with(amount_raw, "-") -> "OUT" else "IN"
    """
    if raw_tx.get("debtorName"):
        return "IN"
    if raw_tx.get("creditorName"):
        return "OUT"
    if amount_raw.startswith("-"):
        return "OUT"
    return "IN"


def _pick_counterparty(raw_tx: dict, direction: str) -> dict:
    """
    C-01 derive.counterparty:
      OUT -> {role: CREDITOR, name: creditorName, iban: creditorAccount.iban}
      IN  -> {role: DEBTOR,   name: debtorName,   iban: debtorAccount.iban}
      else -> {role: UNKNOWN, name: null, iban: null}
    """
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
    # Amount
    amount_raw = (raw_tx.get("transactionAmount") or {}).get("amount")
    if amount_raw is None:
        return None
    amt = _parse_decimal(amount_raw)
    if amt is None:
        return None

    currency = ((raw_tx.get("transactionAmount") or {}).get("currency") or "").upper()

    # Dates
    booking_date = raw_tx.get("bookingDate")  # may be None (e.g. PENDING)
    value_date = raw_tx.get("valueDate")
    if not value_date:
        return None  # INV-02 will catch this anyway

    # Direction
    direction = _infer_direction(raw_tx, amount_raw)

    # Amount object
    amount_abs = _decimal_str(abs(amt))
    if direction == "OUT":
        amount_signed = "-" + amount_abs if not amount_abs.startswith("-") else amount_abs
    else:
        amount_signed = amount_abs

    # Check if raw sign mismatches derived direction -> flag
    flags: list[dict] = []
    raw_is_negative = amount_raw.strip().startswith("-")
    if (direction == "OUT" and not raw_is_negative and amt != 0) or \
       (direction == "IN" and raw_is_negative):
        flags.append({
            "id": "INV-05_AMOUNT_SIGN_MATCHES_DIRECTION",
            "severity": "WARN",
            "message": "raw amount sign mismatched derived direction; normalized signed amount.",
        })

    # Counterparty
    counterparty = _pick_counterparty(raw_tx, direction)

    # Remittance
    remittance = raw_tx.get("remittanceInformationUnstructured")

    # Transaction ID
    transaction_id = raw_tx.get("transactionId")

    # Record ID (C-01: hash of key fields)
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

    # Source lineage
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
) -> list[dict]:
    """Flatten a single report file into SV transactions (C-01 flatten rules)."""
    transactions_obj = tx_data.get("transactions") or {}
    sv_txs = []

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

    return sv_txs


def _build_sv_bundle(
    accounts_data: dict,
    report_files: list[tuple[str, dict]],
    run_id: str,
    created_at_utc: str,
    run_flags: list[dict],
) -> dict:
    """Build the full SVBundle from accounts + flattened report files."""
    # Resolve accounts
    raw_accounts = accounts_data.get("accounts", [])
    if not raw_accounts:
        return {"meta": {}, "accounts": [], "transactions": []}

    # Build account IBAN -> account_id mapping
    sv_accounts = []
    iban_to_account_id: dict[str, str] = {}
    for raw_acct in raw_accounts:
        resource_id = raw_acct.get("resourceId", "unknown")
        account_id = resource_id  # use resourceId directly as account_id
        iban = raw_acct.get("iban")
        if iban:
            iban_to_account_id[iban] = account_id

        sv_accounts.append({
            "account_id": account_id,
            "iban": iban,
            "currency": (raw_acct.get("currency") or "").upper(),
            "name": raw_acct.get("name"),
        })

    # Flatten all report files into transactions
    all_transactions: list[dict] = []
    for source_file, tx_data in report_files:
        # Resolve which account this report belongs to
        report_iban = (tx_data.get("account") or {}).get("iban")
        account_id = iban_to_account_id.get(report_iban, sv_accounts[0]["account_id"])

        sv_txs = _flatten_report_file(tx_data, account_id, source_file)
        all_transactions.extend(sv_txs)

    # Meta with spec_versions
    meta = {
        "run_id": run_id,
        "created_at_utc": created_at_utc,
        "profile_id": "default",
        "spec_versions": {
            "S-00A": "1.0.0",
            "S-00B": "1.0.0",
            "S-01": "1.0.0",
            "C-01": "1.0.0",
            "R-01": "1.0.0",
            "C-02": "1.0.0",
            "C-03": "1.0.0",
        },
    }

    return {
        "meta": meta,
        "accounts": sv_accounts,
        "transactions": all_transactions,
    }


# ---------------------------------------------------------------------------
# Stage 3: Validate SV schema
# ---------------------------------------------------------------------------

def _validate_sv_schema(sv_bundle: dict) -> list[str]:
    """Validate SVBundle against S-01. Returns list of error messages."""
    schema = _load_schema("S-01_sv_schema.json")
    errors = []
    try:
        jsonschema.validate(sv_bundle, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"S-01 validation: {e.message}")
    return errors


# ---------------------------------------------------------------------------
# Stage 4: Check invariants (R-01)
# ---------------------------------------------------------------------------

def _check_invariants(sv_bundle: dict) -> tuple[list[dict], list[dict]]:
    """
    Check R-01 invariants on each transaction.
    Returns (valid_transactions, dropped_transactions).
    Each transaction may have flags added.
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


# ---------------------------------------------------------------------------
# Stage 5a: ML projection (C-02)
# ---------------------------------------------------------------------------

def _project_ml(sv_bundle: dict) -> list[dict]:
    """
    Project SV -> ML CSV rows (C-02).
    Filter: BOOKED + PENDING.
    Sort: account_id, value_date, record_id.
    Columns: row_id (1-based int), account_id, record_id, status,
             booking_date, value_date, direction, currency,
             signed_amount, abs_amount, counterparty_name, remittance.
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

    # Sort: account_id, value_date, record_id
    rows.sort(key=lambda r: (r["account_id"], r["value_date"], r["record_id"]))

    # Add row_id (1-based)
    for i, row in enumerate(rows, 1):
        row["row_id"] = i

    return rows


# ---------------------------------------------------------------------------
# Stage 5b: LLM projection (C-03)
# ---------------------------------------------------------------------------

def _project_llm(sv_bundle: dict) -> list[dict]:
    """
    Project SV -> LLM context JSON (C-03), one per account.
    Filter: BOOKED + PENDING.
    Sort: value_date, record_id.
    Window: last 200.
    Truncate: counterparty_name 80, remittance 160.
    """
    contract = _load_yaml("contracts/C-03_sv_to_llm.yaml")
    max_n = contract.get("window", {}).get("last_n", 200)
    max_cp_len = contract.get("truncate", {}).get("counterparty_name_max_len", 80)
    max_rem_len = contract.get("truncate", {}).get("remittance_max_len", 160)

    # Group transactions by account
    by_account: dict[str, list[dict]] = {}
    for tx in sv_bundle.get("transactions", []):
        if tx["status"] not in ("BOOKED", "PENDING"):
            continue
        acct = tx["account_id"]
        by_account.setdefault(acct, []).append(tx)

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
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    data_dir: str | Path,
    output_dir: str | Path,
    run_id: str | None = None,
) -> dict:
    """
    Run the full adapter pipeline: RAW -> SV -> ML/LLM projections.

    Args:
        data_dir: Directory containing accounts.json, transactions.json,
                  standing_orders.json, transactions_download.json
        output_dir: Directory for output files
        run_id: Optional fixed run_id for reproducibility

    Returns:
        Summary dict with outcome, counts, and issues.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if run_id is None:
        run_id = uuid.uuid4().hex[:12]
    created_at_utc = _now_utc()

    issues: list[str] = []
    run_flags: list[dict] = []

    # --- Stage 1: Read & validate RAW ---
    with open(data_dir / "accounts.json", encoding="utf-8") as f:
        accounts_data = json.load(f)

    acct_errors = _validate_raw_accounts(accounts_data)
    issues.extend(acct_errors)

    # Load report files (C-01 inputs.reports)
    report_files: list[tuple[str, dict]] = []
    for fname in ("transactions.json", "standing_orders.json"):
        fpath = data_dir / fname
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                tx_data = json.load(f)
            tx_errors = _validate_raw_transactions(tx_data)
            issues.extend(tx_errors)
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
            else:
                # Not download-only, treat as normal report
                tx_errors = _validate_raw_transactions(dl_data)
                issues.extend(tx_errors)
                report_files.append((fname, dl_data))

    # Count total raw transactions across all report files
    total_raw = 0
    for _, tx_data in report_files:
        tx_obj = tx_data.get("transactions") or {}
        for key in ("booked", "pending", "information"):
            total_raw += len(tx_obj.get(key, []))

    # --- Stage 2: Map to SV (C-01) ---
    sv_bundle = _build_sv_bundle(
        accounts_data, report_files, run_id, created_at_utc, run_flags,
    )

    # --- Stage 3: Validate SV schema ---
    sv_errors = _validate_sv_schema(sv_bundle)
    issues.extend(sv_errors)

    # --- Stage 4: Check invariants (R-01) ---
    valid_txs, dropped_txs = _check_invariants(sv_bundle)
    sv_bundle["transactions"] = valid_txs

    # --- Stage 5a: ML projection (C-02) ---
    ml_rows = _project_ml(sv_bundle)

    # --- Stage 5b: LLM projection (C-03) ---
    llm_contexts = _project_llm(sv_bundle)

    # --- Write outputs ---
    # SVBundle
    with open(output_dir / "sv_bundle.json", "w", encoding="utf-8") as f:
        json.dump(sv_bundle, f, indent=2, ensure_ascii=False)

    # ML CSV
    csv_path = output_dir / "ml_projection.csv"
    fieldnames = [
        "row_id", "account_id", "record_id", "status",
        "booking_date", "value_date", "direction", "currency",
        "signed_amount", "abs_amount", "counterparty_name", "remittance",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ml_rows)

    # LLM context
    with open(output_dir / "llm_context.json", "w", encoding="utf-8") as f:
        json.dump(llm_contexts[0] if llm_contexts else {}, f, indent=2, ensure_ascii=False)

    # --- Summary ---
    emitted = len(valid_txs)
    n_dropped = len(dropped_txs)
    has_errors = any("ERROR" in str(i) for i in issues)

    summary = {
        "outcome": "SUCCESS" if not issues and not run_flags else "PARTIAL_SUCCESS",
        "run_id": run_id,
        "counts": {
            "accounts_total": len(sv_bundle.get("accounts", [])),
            "transactions_total": total_raw,
            "transactions_emitted_sv": emitted,
            "transactions_dropped": n_dropped,
            "ml_rows": len(ml_rows),
            "llm_contexts": len(llm_contexts),
        },
        "run_flags": run_flags,
        "issues": issues,
    }

    return summary
