"""
Data-completeness quality checks — INFO-level diagnostics.

These are not invariants (validity constraints that must hold for all
legal inputs).  They flag observable data gaps that may or may not
indicate a problem, depending on the source system.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations


def check_quality(transactions: list[dict]) -> None:
    """Append INFO-level quality flags to transactions in-place."""
    for tx in transactions:
        _qc01_counterparty_missing(tx)


def _qc01_counterparty_missing(tx: dict) -> None:
    """QC-1: counterparty name and IBAN both absent.

    Bank-internal transactions (fees, loan payments, card charges)
    legitimately have no counterparty in PSD2 data.  This is not a
    validity error but a completeness observation.
    """
    cp = tx.get("counterparty", {})
    if cp.get("name") is None and cp.get("iban") is None:
        tx["flags"].append({
            "id": "QC-1_COUNTERPARTY_MISSING",
            "severity": "INFO",
            "message": "counterparty name and IBAN both absent.",
        })
