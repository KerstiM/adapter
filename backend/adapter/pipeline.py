"""
Adapter pipeline: RAW (Berlin AIS) -> SV -> ML/LLM projections -> report.

Implements the happy path described in the thesis:
  1. Validate RAW input against S-00A/S-00B schemas
  2. Map to SV using C-01 contract rules
  3. Check invariants using R-01 ruleset
  4. Project to ML CSV (C-02) and LLM context JSON (C-03)
  5. Generate collected report (S-05)
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
SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"

STAGES = [
    "READ_INPUT",
    "STANDARDIZE_TO_SV",
    "VALIDATE_SCHEMA",
    "CHECK_INVARIANTS",
    "PROJECT_ML",
    "PROJECT_LLM",
    "WRITE_OUTPUTS",
]


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


def _date_to_utc(date_str: str | None) -> str | None:
    """Parse ISO date or datetime to UTC datetime string ending with Z."""
    if not date_str:
        return None
    # Already a datetime with T
    if "T" in date_str:
        s = date_str.rstrip("Z")
        return s + "Z"
    # Date-only -> midnight UTC
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str + "T00:00:00Z"
    except ValueError:
        return None


def _is_datetime_utc(s: str | None) -> bool:
    if not s or not s.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def _parse_decimal(s: str | None) -> Decimal | None:
    if s is None:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _decimal_str(d: Decimal) -> str:
    """Canonical decimal string without scientific notation."""
    # Use fixed-point formatting to avoid '2.75E+3' style output
    return format(d.normalize(), "f")


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _hash_record_id(parts: list[str]) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Stage 1: Read & validate RAW input
# ---------------------------------------------------------------------------

class Issue:
    __slots__ = ("code", "severity", "stage", "message", "refs")

    def __init__(self, code: str, severity: str, stage: str, message: str, refs: dict):
        self.code = code
        self.severity = severity
        self.stage = stage
        self.message = message
        self.refs = refs

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "refs": {
                "account_id": self.refs.get("account_id"),
                "record_id": self.refs.get("record_id"),
                "field_path": self.refs.get("field_path"),
                "source_lineage": self.refs.get("source_lineage"),
                "source_record_id": self.refs.get("source_record_id"),
            },
        }


def _validate_raw_input(
    accounts_data: dict,
    transactions_data: dict,
    issues: list[Issue],
) -> bool:
    """Validate RAW against S-00A/S-00B. Returns True if valid."""
    ok = True
    try:
        schema_a = _load_schema("S-00A_berlin_accounts.schema.json")
        jsonschema.validate(accounts_data, schema_a)
    except jsonschema.ValidationError as e:
        issues.append(Issue(
            "RAW_SCHEMA_ACCOUNTS", "ERROR", "READ_INPUT",
            f"Accounts schema validation failed: {e.message}",
            {"account_id": None, "record_id": None, "field_path": str(e.json_path),
             "source_lineage": "accounts.json", "source_record_id": None},
        ))
        ok = False

    try:
        schema_b = _load_schema("S-00B_berlin_transactions.schema.json")
        jsonschema.validate(transactions_data, schema_b)
    except jsonschema.ValidationError as e:
        issues.append(Issue(
            "RAW_SCHEMA_TRANSACTIONS", "ERROR", "READ_INPUT",
            f"Transactions schema validation failed: {e.message}",
            {"account_id": None, "record_id": None, "field_path": str(e.json_path),
             "source_lineage": "transactions.json", "source_record_id": None},
        ))
        ok = False

    return ok


# ---------------------------------------------------------------------------
# Stage 2: Map RAW -> SV  (C-01)
# ---------------------------------------------------------------------------

def _infer_direction(
    raw_tx: dict,
    context_iban: str | None,
    amount: Decimal,
) -> str:
    """
    Infer direction following C-01 rules:
    - If creditorAccount present and matches context account -> CREDIT (incoming)
    - If debtorAccount present and matches context account -> DEBIT (outgoing)
    - If only creditorName (no debtor) -> DEBIT (paying to creditor)
    - If only debtorName (no creditor) -> CREDIT (receiving from debtor)
    - Fallback: amount sign (negative = DEBIT)
    """
    creditor_iban = (raw_tx.get("creditorAccount") or {}).get("iban")
    debtor_iban = (raw_tx.get("debtorAccount") or {}).get("iban")

    # If context account appears as debtor -> we are the debtor -> DEBIT
    if debtor_iban and context_iban and debtor_iban == context_iban:
        return "DEBIT"
    # If context account appears as creditor -> we are the creditor -> CREDIT
    if creditor_iban and context_iban and creditor_iban == context_iban:
        return "CREDIT"

    # Berlin convention: creditorName present means we pay to them -> DEBIT
    has_creditor = raw_tx.get("creditorName") is not None
    has_debtor = raw_tx.get("debtorName") is not None

    if has_creditor and not has_debtor:
        return "DEBIT"
    if has_debtor and not has_creditor:
        return "CREDIT"

    # Fallback to amount sign
    if amount < 0:
        return "DEBIT"
    return "CREDIT"


def _pick_counterparty(raw_tx: dict, direction: str) -> dict:
    """Pick counterparty based on direction (C-01 rules)."""
    if direction == "DEBIT":
        # We pay -> counterparty is creditor
        name = raw_tx.get("creditorName")
        iban = (raw_tx.get("creditorAccount") or {}).get("iban")
        bic = (raw_tx.get("creditorAgent") or {}).get("bic")
    else:
        # We receive -> counterparty is debtor
        name = raw_tx.get("debtorName")
        iban = (raw_tx.get("debtorAccount") or {}).get("iban")
        bic = (raw_tx.get("debtorAgent") or {}).get("bic")

    return {"name": name, "iban": iban, "bic": bic}


def _normalize_amount_sign(amount: Decimal, direction: str) -> Decimal:
    """Ensure amount sign matches direction: DEBIT -> negative, CREDIT -> positive."""
    if direction == "DEBIT":
        return -abs(amount)
    return abs(amount)


def _map_single_transaction(
    raw_tx: dict,
    account_id: str,
    context_iban: str | None,
    status: str,
    source_index: int,
    source_file: str,
    issues: list[Issue],
) -> dict | None:
    """Map a single Berlin AIS transaction to SVTransaction. Returns None on DROP."""
    source_lineage = f"$.transactions.{status.lower()}[{source_index}]"

    # Parse amount
    raw_amount_str = (raw_tx.get("transactionAmount") or {}).get("amount")
    amount = _parse_decimal(raw_amount_str)
    if amount is None:
        issues.append(Issue(
            "C01_PARSE_AMOUNT", "ERROR", "STANDARDIZE_TO_SV",
            f"Cannot parse amount: {raw_amount_str!r}",
            {"account_id": account_id, "record_id": None,
             "field_path": "transactionAmount.amount",
             "source_lineage": source_lineage, "source_record_id": raw_tx.get("transactionId")},
        ))
        return None

    # Currency
    currency = ((raw_tx.get("transactionAmount") or {}).get("currency") or "").upper()

    # Direction
    direction = _infer_direction(raw_tx, context_iban, amount)

    # Normalize amount sign
    amount = _normalize_amount_sign(amount, direction)
    amount_str = _decimal_str(amount)

    # Booking time
    booking_date_raw = raw_tx.get("bookingDateTime") or raw_tx.get("bookingDate")
    booking_time_utc = _date_to_utc(booking_date_raw)
    if status == "PENDING" and not booking_time_utc:
        # For pending, try reservationDate or valueDate
        fallback = raw_tx.get("reservationDate") or raw_tx.get("valueDate")
        booking_time_utc = _date_to_utc(fallback)

    if not booking_time_utc:
        issues.append(Issue(
            "C01_MISSING_BOOKING_TIME", "ERROR", "STANDARDIZE_TO_SV",
            "No parseable booking time found.",
            {"account_id": account_id, "record_id": None,
             "field_path": "bookingDate",
             "source_lineage": source_lineage, "source_record_id": raw_tx.get("transactionId")},
        ))
        return None

    # Value time
    value_time_utc = _date_to_utc(raw_tx.get("valueDate"))

    # Description
    remittance_unstructured = raw_tx.get("remittanceInformationUnstructured")
    remittance_structured = raw_tx.get("remittanceInformationStructured")
    bank_tx_code = raw_tx.get("bankTransactionCode")

    desc_parts = [p for p in [remittance_unstructured, remittance_structured, bank_tx_code] if p]
    description_raw = ", ".join(desc_parts) if desc_parts else ""
    description_norm = _normalize_text(description_raw)

    # Counterparty
    counterparty = _pick_counterparty(raw_tx, direction)

    # Source record ID
    source_record_id = (
        raw_tx.get("entryReference")
        or raw_tx.get("transactionId")
        or _hash_record_id([account_id, booking_time_utc, amount_str])
    )

    # Record ID (deterministic hash)
    record_id = _hash_record_id([
        account_id,
        source_record_id,
        booking_time_utc,
        amount_str,
        currency,
        description_norm,
        counterparty.get("iban") or "",
        counterparty.get("name") or "",
    ])

    return {
        "record_id": record_id,
        "account_id": account_id,
        "status": status,
        "booking_time_utc": booking_time_utc,
        "value_time_utc": value_time_utc,
        "amount": amount_str,
        "currency": currency,
        "direction": direction,
        "description_raw": description_raw,
        "description_norm": description_norm,
        "remittance": {
            "unstructured": remittance_unstructured,
            "structured": remittance_structured,
        },
        "transaction_code": bank_tx_code,
        "counterparty": counterparty,
        "origin": {
            "source_format": "berlin_ais_json",
            "source_record_id": str(source_record_id),
            "source_lineage": f"{source_file}:{source_lineage}",
        },
        "flags": [],
    }


def _map_to_sv(
    accounts_data: dict,
    transactions_data: dict,
    run_id: str,
    created_at_utc: str,
    provider_id: str,
    issues: list[Issue],
) -> dict:
    """Map Berlin AIS RAW to SVBundle (C-01)."""
    contract = _load_yaml("contracts/C-01_ob_to_sv.yaml")
    mapping_version = contract["contract_version"]
    ruleset = _load_yaml("rulesets/R-01_sv_invariants.yaml")
    ruleset_version = ruleset["ruleset_version"]

    context_iban = (transactions_data.get("account") or {}).get("iban")

    # Build accounts
    sv_accounts = []
    for raw_acct in accounts_data.get("accounts", []):
        resource_id = raw_acct.get("resourceId", "unknown")
        account_id = f"{provider_id}:{resource_id}"

        # Map transactions for this account
        sv_transactions = []
        booked = (transactions_data.get("transactions") or {}).get("booked", [])
        for i, raw_tx in enumerate(booked):
            sv_tx = _map_single_transaction(
                raw_tx, account_id, context_iban, "BOOKED", i,
                "transactions.json", issues,
            )
            if sv_tx:
                sv_transactions.append(sv_tx)

        pending = (transactions_data.get("transactions") or {}).get("pending", [])
        for i, raw_tx in enumerate(pending):
            sv_tx = _map_single_transaction(
                raw_tx, account_id, context_iban, "PENDING", i,
                "transactions.json", issues,
            )
            if sv_tx:
                sv_transactions.append(sv_tx)

        sv_accounts.append({
            "account_id": account_id,
            "account_ref": {
                "iban": raw_acct.get("iban"),
                "currency": (raw_acct.get("currency") or "").upper() or None,
            },
            "statement_period": {
                "from_utc": None,
                "to_utc": None,
            },
            "balances": [],
            "transactions": sv_transactions,
            "extensions": {},
        })

    sv_bundle = {
        "sv_schema_version": "1.0.0",
        "run": {
            "run_id": run_id,
            "created_at_utc": created_at_utc,
            "adapter_version": ADAPTER_VERSION,
            "mapping_version": mapping_version,
            "ruleset_version": ruleset_version,
            "source": {
                "source_type": "psd2_json_fixture",
                "source_refs": [
                    {"ref_type": "file", "ref": "data/D1/accounts.json"},
                    {"ref_type": "file", "ref": "data/D1/transactions.json"},
                ],
                "period": {
                    "from_utc": None,
                    "to_utc": None,
                },
            },
        },
        "accounts": sv_accounts,
    }

    return sv_bundle


# ---------------------------------------------------------------------------
# Stage 3: Validate SV schema
# ---------------------------------------------------------------------------

def _validate_sv_schema(sv_bundle: dict, issues: list[Issue]) -> bool:
    schema = _load_schema("S-01_sv_schema.json")
    try:
        jsonschema.validate(sv_bundle, schema)
        return True
    except jsonschema.ValidationError as e:
        issues.append(Issue(
            "SV_SCHEMA_VALIDATION", "ERROR", "VALIDATE_SCHEMA",
            f"SV schema validation failed: {e.message}",
            {"account_id": None, "record_id": None, "field_path": str(e.json_path),
             "source_lineage": None, "source_record_id": None},
        ))
        return False


# ---------------------------------------------------------------------------
# Stage 4: Check invariants (R-01)
# ---------------------------------------------------------------------------

def _check_invariants(sv_bundle: dict, issues: list[Issue]) -> dict:
    """
    Check R-01 invariants on each SVTransaction.
    Returns updated sv_bundle with flagged/dropped transactions.
    """
    for account in sv_bundle.get("accounts", []):
        account_id = account["account_id"]
        valid_txs = []
        seen_record_ids: dict[str, int] = {}

        for tx in account.get("transactions", []):
            record_id = tx["record_id"]
            dropped = False
            refs = {
                "account_id": account_id,
                "record_id": record_id,
                "field_path": None,
                "source_lineage": tx.get("origin", {}).get("source_lineage"),
                "source_record_id": tx.get("origin", {}).get("source_record_id"),
            }

            # INV-01: Required minimum fields
            required = ["record_id", "account_id", "booking_time_utc", "amount",
                        "currency", "direction", "description_norm"]
            origin_required = ["source_record_id", "source_lineage"]
            for field in required:
                if not tx.get(field):
                    issues.append(Issue(
                        "INV-01_REQUIRED_MIN_FIELDS", "ERROR", "CHECK_INVARIANTS",
                        f"Missing required field: {field}",
                        {**refs, "field_path": field},
                    ))
                    dropped = True
                    break
            if not dropped:
                origin = tx.get("origin", {})
                for field in origin_required:
                    if not origin.get(field):
                        issues.append(Issue(
                            "INV-08_ORIGIN_PRESENT", "ERROR", "CHECK_INVARIANTS",
                            f"Missing origin field: origin.{field}",
                            {**refs, "field_path": f"origin.{field}"},
                        ))
                        dropped = True
                        break

            if dropped:
                continue

            # INV-02: booking_time_utc parseable
            if not _is_datetime_utc(tx["booking_time_utc"]):
                issues.append(Issue(
                    "INV-02_BOOKING_TIME_PARSEABLE", "ERROR", "CHECK_INVARIANTS",
                    "booking_time_utc not parseable/UTC.",
                    {**refs, "field_path": "booking_time_utc"},
                ))
                continue

            # INV-03: direction enum
            if tx["direction"] not in ("DEBIT", "CREDIT"):
                issues.append(Issue(
                    "INV-03_DIRECTION_ENUM", "ERROR", "CHECK_INVARIANTS",
                    "direction must be DEBIT or CREDIT.",
                    {**refs, "field_path": "direction"},
                ))
                continue

            # INV-04: amount decimal
            if _parse_decimal(tx["amount"]) is None:
                issues.append(Issue(
                    "INV-04_AMOUNT_DECIMAL", "ERROR", "CHECK_INVARIANTS",
                    "amount must be a decimal string.",
                    {**refs, "field_path": "amount"},
                ))
                continue

            # INV-05: amount sign matches direction (WARN, NORMALIZE_AND_FLAG)
            amt = _parse_decimal(tx["amount"])
            if tx["direction"] == "DEBIT" and amt > 0:
                amt = -amt
                tx["amount"] = _decimal_str(amt)
                tx["flags"].append("INV-05_AMOUNT_SIGN_NORMALIZED")
                issues.append(Issue(
                    "INV-05_AMOUNT_SIGN_MATCHES_DIRECTION", "WARN", "CHECK_INVARIANTS",
                    "amount sign mismatched direction; normalized to match direction.",
                    {**refs, "field_path": "amount"},
                ))
            elif tx["direction"] == "CREDIT" and amt < 0:
                amt = abs(amt)
                tx["amount"] = _decimal_str(amt)
                tx["flags"].append("INV-05_AMOUNT_SIGN_NORMALIZED")
                issues.append(Issue(
                    "INV-05_AMOUNT_SIGN_MATCHES_DIRECTION", "WARN", "CHECK_INVARIANTS",
                    "amount sign mismatched direction; normalized to match direction.",
                    {**refs, "field_path": "amount"},
                ))

            # INV-06: currency ISO4217
            if not re.match(r"^[A-Z]{3}$", tx["currency"]):
                issues.append(Issue(
                    "INV-06_CURRENCY_ISO4217", "ERROR", "CHECK_INVARIANTS",
                    "currency must be ISO4217 uppercase.",
                    {**refs, "field_path": "currency"},
                ))
                continue

            # INV-07: description_norm nonempty (WARN, FLAG_ONLY)
            if not tx["description_norm"]:
                tx["flags"].append("INV-07_DESC_NORM_EMPTY")
                issues.append(Issue(
                    "INV-07_DESC_NORM_NONEMPTY", "WARN", "CHECK_INVARIANTS",
                    "description_norm empty.",
                    {**refs, "field_path": "description_norm"},
                ))

            # INV-09: duplicate record_id (WARN, KEEP_FIRST_DETERMINISTIC)
            if record_id in seen_record_ids:
                tx["flags"].append("INV-09_DUPLICATE_DROPPED")
                issues.append(Issue(
                    "INV-09_DUPLICATE_RECORD_ID", "WARN", "CHECK_INVARIANTS",
                    "Duplicate record_id within account; keeping first deterministically.",
                    {**refs, "field_path": "record_id"},
                ))
                continue
            seen_record_ids[record_id] = 1

            # INV-10: counterparty all null (WARN, FLAG_ONLY)
            cp = tx.get("counterparty", {})
            if cp.get("name") is None and cp.get("iban") is None and cp.get("bic") is None:
                tx["flags"].append("INV-10_COUNTERPARTY_ALL_NULL")
                issues.append(Issue(
                    "INV-10_COUNTERPARTY_ALL_NULL", "WARN", "CHECK_INVARIANTS",
                    "counterparty present but all fields null.",
                    {**refs, "field_path": "counterparty"},
                ))

            valid_txs.append(tx)

        account["transactions"] = valid_txs

    return sv_bundle


# ---------------------------------------------------------------------------
# Stage 5a: ML projection (C-02)
# ---------------------------------------------------------------------------

def _project_ml(sv_bundle: dict, issues: list[Issue]) -> list[dict]:
    """Project SV -> ML rows (C-02). Returns list of dicts (one per row)."""
    rows = []
    for account in sv_bundle.get("accounts", []):
        for tx in account.get("transactions", []):
            # Filter: BOOKED only
            if tx.get("status") != "BOOKED":
                continue

            amt = _parse_decimal(tx["amount"])
            if amt is None:
                continue

            booking = tx["booking_time_utc"]
            # Parse month/weekday
            month = None
            weekday = None
            try:
                dt = datetime.fromisoformat(booking.replace("Z", "+00:00"))
                month = dt.month
                weekday = dt.weekday()
            except (ValueError, TypeError):
                pass

            rows.append({
                "row_id": tx["record_id"],
                "account_id": tx["account_id"],
                "booking_time_utc": booking,
                "amount": tx["amount"],
                "amount_abs": _decimal_str(abs(amt)),
                "direction": tx["direction"],
                "currency": tx["currency"],
                "desc_norm": tx["description_norm"],
                "month": month,
                "weekday": weekday,
            })

    # Sort: account_id, booking_time_utc, record_id (row_id)
    rows.sort(key=lambda r: (r["account_id"], r["booking_time_utc"], r["row_id"]))
    return rows


# ---------------------------------------------------------------------------
# Stage 5b: LLM projection (C-03)
# ---------------------------------------------------------------------------

def _project_llm(sv_bundle: dict, issues: list[Issue]) -> list[dict]:
    """
    Project SV -> LLM context objects (C-03).
    Returns one context object per account.
    """
    contract = _load_yaml("contracts/C-03_sv_to_llm.yaml")
    max_n = contract.get("windowing", {}).get("N", 200)
    max_desc = contract.get("truncation", {}).get("max_desc_chars", 160)

    contexts = []
    for account in sv_bundle.get("accounts", []):
        # Filter BOOKED, sort, window
        txs = [t for t in account.get("transactions", []) if t.get("status") == "BOOKED"]
        txs.sort(key=lambda t: (t["booking_time_utc"], t["record_id"]))
        txs = txs[-max_n:]  # LAST_N

        mapped_txs = []
        for tx in txs:
            desc = tx["description_norm"]
            if len(desc) > max_desc:
                desc = desc[:max_desc]

            mapped_txs.append({
                "record_id": tx["record_id"],
                "t": tx["booking_time_utc"],
                "amt": tx["amount"],
                "cur": tx["currency"],
                "direction": tx["direction"],
                "counterparty": tx["counterparty"],
                "desc": desc,
            })

        context = {
            "meta": {
                "run_id": sv_bundle["run"]["run_id"],
                "sv_schema_version": sv_bundle["sv_schema_version"],
                "projection_id": "llm_context",
                "projection_version": "1.0.0",
                "windowing": {
                    "mode": "LAST_N",
                    "N": max_n,
                },
            },
            "account_context": {
                "account_id": account["account_id"],
                "currency": account["account_ref"].get("currency"),
            },
            "transactions": mapped_txs,
        }
        contexts.append(context)

    return contexts


# ---------------------------------------------------------------------------
# Stage 6: Collected report (S-05)
# ---------------------------------------------------------------------------

def _build_report(
    sv_bundle: dict,
    issues: list[Issue],
    total_raw_transactions: int,
    outcome_status: str,
) -> dict:
    """Build collected report (S-05 schema)."""
    run = sv_bundle["run"]

    # Count emitted
    emitted = sum(
        len(a.get("transactions", []))
        for a in sv_bundle.get("accounts", [])
    )
    dropped = total_raw_transactions - emitted

    # by_stage
    stage_counts: dict[str, dict[str, int]] = {s: {"errors": 0, "warnings": 0, "infos": 0} for s in STAGES}
    for iss in issues:
        bucket = stage_counts.get(iss.stage, stage_counts["READ_INPUT"])
        if iss.severity in ("ERROR", "CRITICAL"):
            bucket["errors"] += 1
        elif iss.severity == "WARN":
            bucket["warnings"] += 1
        else:
            bucket["infos"] += 1

    by_stage = [
        {"stage": s, "errors": c["errors"], "warnings": c["warnings"], "infos": c["infos"]}
        for s, c in stage_counts.items()
    ]

    # by_severity
    sev_counts = {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0}
    for iss in issues:
        sev_counts[iss.severity] = sev_counts.get(iss.severity, 0) + 1

    # Metrics
    pass_rate = emitted / total_raw_transactions if total_raw_transactions > 0 else None
    metrics = [
        {
            "id": "SLI4_transaction_pass_rate",
            "value": round(pass_rate, 4) if pass_rate is not None else None,
            "method": {
                "basis": "transactions_emitted_sv / transactions_total",
                "numerator": emitted,
                "denominator": total_raw_transactions,
            },
            "notes": None,
        }
    ]

    return {
        "report_schema_version": "1.0.0",
        "run": {
            "run_id": run["run_id"],
            "created_at_utc": run["created_at_utc"],
            "adapter_version": run["adapter_version"],
            "sv_schema_version": sv_bundle["sv_schema_version"],
            "mapping_version": run["mapping_version"],
            "ruleset_version": run["ruleset_version"],
        },
        "outcome": {
            "status": outcome_status,
            "stop_reason": "completed" if outcome_status != "FAIL" else "critical_invariant_violation",
        },
        "summary": {
            "counts": {
                "accounts_total": len(sv_bundle.get("accounts", [])),
                "transactions_total": total_raw_transactions,
                "transactions_emitted_sv": emitted,
                "transactions_dropped": dropped,
            },
            "by_stage": by_stage,
            "by_severity": sev_counts,
        },
        "issues": [iss.to_dict() for iss in issues],
        "metrics": metrics,
    }


def _determine_outcome(issues: list[Issue]) -> str:
    """Determine outcome status based on partial_success_policy."""
    has_critical = any(i.severity == "CRITICAL" for i in issues)
    has_error = any(i.severity == "ERROR" for i in issues)
    has_warn = any(i.severity == "WARN" for i in issues)

    if has_critical:
        return "FAIL"
    if has_error or has_warn:
        return "PARTIAL_SUCCESS"
    return "SUCCESS"


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    data_dir: str | Path,
    output_dir: str | Path,
    provider_id: str = "fixture",
    run_id: str | None = None,
) -> dict:
    """
    Run the full adapter pipeline: RAW -> SV -> ML/LLM -> report.

    Args:
        data_dir: Directory containing accounts.json and transactions.json
        output_dir: Directory for output files
        provider_id: Provider identifier for account_id composition
        run_id: Optional fixed run_id for reproducibility

    Returns:
        Collected report dict
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if run_id is None:
        run_id = uuid.uuid4().hex[:12]
    created_at_utc = _now_utc()

    issues: list[Issue] = []

    # --- Stage 1: Read & validate RAW ---
    with open(data_dir / "accounts.json", encoding="utf-8") as f:
        accounts_data = json.load(f)
    with open(data_dir / "transactions.json", encoding="utf-8") as f:
        transactions_data = json.load(f)

    raw_valid = _validate_raw_input(accounts_data, transactions_data, issues)

    # Count total raw transactions
    booked = (transactions_data.get("transactions") or {}).get("booked", [])
    pending = (transactions_data.get("transactions") or {}).get("pending", [])
    total_raw = len(booked) + len(pending)

    # --- Stage 2: Map to SV (C-01) ---
    sv_bundle = _map_to_sv(
        accounts_data, transactions_data,
        run_id, created_at_utc, provider_id, issues,
    )

    # --- Stage 3: Validate SV schema ---
    _validate_sv_schema(sv_bundle, issues)

    # --- Stage 4: Check invariants (R-01) ---
    sv_bundle = _check_invariants(sv_bundle, issues)

    # --- Stage 5a: ML projection (C-02) ---
    ml_rows = _project_ml(sv_bundle, issues)

    # --- Stage 5b: LLM projection (C-03) ---
    llm_contexts = _project_llm(sv_bundle, issues)

    # --- Stage 6: Report ---
    outcome = _determine_outcome(issues)
    report = _build_report(sv_bundle, issues, total_raw, outcome)

    # --- Write outputs ---
    # SVBundle
    with open(output_dir / "sv_bundle.json", "w", encoding="utf-8") as f:
        json.dump(sv_bundle, f, indent=2, ensure_ascii=False)

    # ML CSV
    if ml_rows:
        csv_path = output_dir / "ml_projection.csv"
        fieldnames = [
            "row_id", "account_id", "booking_time_utc",
            "amount", "amount_abs", "direction", "currency",
            "desc_norm", "month", "weekday",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ml_rows)

    # LLM context(s)
    for ctx in llm_contexts:
        acct_id = ctx["account_context"]["account_id"].replace(":", "_")
        with open(output_dir / f"llm_context_{acct_id}.json", "w", encoding="utf-8") as f:
            json.dump(ctx, f, indent=2, ensure_ascii=False)

    # Report
    with open(output_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report
