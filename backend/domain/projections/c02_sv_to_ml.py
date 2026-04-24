"""
C-02: SV -> ML projection — pure functions.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

from domain.projections._shared import iter_projectable


def project_ml(sv_bundle: dict) -> list[dict]:
    """Project SV -> ML CSV rows (C-02).

    Filter: BOOKED + PENDING.
    Sort: account_id, value_date, record_id.
    """
    rows = []
    for tx in iter_projectable(sv_bundle):
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
