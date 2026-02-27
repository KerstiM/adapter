"""
R-01 invariant checks — pure functions that return flags/drop events.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

import re
from collections import OrderedDict
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


def _is_iso_date(s: str | None) -> bool:
    if not s:
        return False
    try:
        from datetime import datetime
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Invariant checks (INV-01 through INV-10)
# ---------------------------------------------------------------------------

def check_invariants(sv_bundle: dict) -> tuple[list[dict], list[dict]]:
    """Check R-01 invariants on each transaction.

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


# ---------------------------------------------------------------------------
# INV-09: Deduplication by (account_id, record_id)
# ---------------------------------------------------------------------------

def deduplicate_transactions(
    transactions: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Deduplicate SV transactions by (account_id, record_id) -- INV-09.

    Within each group of duplicates the "winner" is chosen deterministically
    by sorting on (source.input_file, source.input_path, status, value_date,
    booking_date, transaction_id).  All others are flagged WARN and dropped.

    Returns (kept, dedupe_drops).
    """
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
