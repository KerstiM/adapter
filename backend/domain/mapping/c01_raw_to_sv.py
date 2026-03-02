"""
C-01: RAW (Berlin AIS) -> SV mapping — pure functions.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Direction / counterparty inference
# ---------------------------------------------------------------------------

def infer_direction(raw_tx: dict, amount_raw: str) -> str:
    if raw_tx.get("debtorName"):
        return "IN"
    if raw_tx.get("creditorName"):
        return "OUT"
    if amount_raw.startswith("-"):
        return "OUT"
    return "IN"


def pick_counterparty(raw_tx: dict, direction: str) -> dict:
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


# ---------------------------------------------------------------------------
# Single transaction mapping
# ---------------------------------------------------------------------------

def map_single_transaction(
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
        next_exec = raw_tx.get("nextExecutionDate")
        if status == "INFORMATION" and next_exec and _is_iso_date(next_exec):
            value_date = next_exec
            value_date_fell_back = True
        elif booking_date and _is_iso_date(booking_date):
            value_date = booking_date
            value_date_fell_back = True
        else:
            return None

    direction = infer_direction(raw_tx, amount_raw)

    amount_abs = _decimal_str(abs(amt))
    if direction == "OUT" and amt != 0:
        amount_signed = "-" + amount_abs if not amount_abs.startswith("-") else amount_abs
    else:
        amount_signed = amount_abs

    # MAP-01: valueDate fallback flag
    flags: list[dict] = []
    if value_date_fell_back:
        fallback_src = "nextExecutionDate" if raw_tx.get("nextExecutionDate") and status == "INFORMATION" else "bookingDate"
        flags.append({
            "id": "MAP-01_VALUE_DATE_FALLBACK",
            "severity": "WARN",
            "message": f"valueDate missing; fell back to {fallback_src}.",
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

    counterparty = pick_counterparty(raw_tx, direction)
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


# ---------------------------------------------------------------------------
# Flatten report file
# ---------------------------------------------------------------------------

def flatten_report_file(
    tx_data: dict,
    account_id: str,
    source_file: str,
) -> tuple[list[dict], list[dict]]:
    """Flatten a single report file into SV transactions (C-01 flatten rules).

    Returns (mapped_transactions, mapping_drops).
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
            sv_tx = map_single_transaction(
                raw_tx, account_id, status, i, source_file, key,
            )
            if sv_tx:
                sv_txs.append(sv_tx)
            else:
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


# ---------------------------------------------------------------------------
# Build SV bundle
# ---------------------------------------------------------------------------

def build_sv_bundle(
    accounts_data: dict,
    report_files: list[tuple[str, dict]],
    run_id: str,
    created_at_utc: str,
    profile: dict,
) -> tuple[dict, list[dict]]:
    """Build the full SVBundle from accounts + flattened report files.

    Returns (sv_bundle, mapping_drops).
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
        sv_txs, mapping_drops = flatten_report_file(tx_data, account_id, source_file)
        all_transactions.extend(sv_txs)
        all_mapping_drops.extend(mapping_drops)

    # Build spec_versions from profile contracts/rulesets
    spec_versions = {}
    for key in ("S-00A", "S-00B", "S-01", "C-01", "R-01", "C-02", "C-03"):
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
