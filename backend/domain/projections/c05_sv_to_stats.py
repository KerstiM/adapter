"""
C-05: SV -> Statistics projection — pure rule-based aggregation.

No I/O, no jsonschema/pathlib/os imports.

This module is a UK3 evolution artifact: it demonstrates that a new projection
can be added on top of the SV intermediate representation without modifying
the pipeline, ports, or adapters.  It follows the same pure-function pattern
as C-02 (project_ml) and C-03 (project_llm).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


def project_stats(sv_bundle: dict) -> list[dict]:
    """Project SV -> per-account aggregated statistics (C-05).

    Aggregates rule-based statistics from the SV bundle:
    - Transaction counts by status (booked / pending)
    - Inflow / outflow totals, counts, and averages
    - Period boundaries (earliest and latest value_date)
    - Top counterparties sorted by absolute total amount

    Filter: BOOKED + PENDING (same as C-02 / C-03).

    Parameters
    ----------
    sv_bundle : dict
        The validated SV bundle produced by the pipeline.

    Returns
    -------
    list[dict]
        One statistics dict per account.
    """
    by_account: dict[str, list[dict]] = defaultdict(list)
    for tx in sv_bundle.get("transactions", []):
        if tx["status"] not in ("BOOKED", "PENDING"):
            continue
        by_account[tx["account_id"]].append(tx)

    results: list[dict] = []
    for sv_acct in sv_bundle.get("accounts", []):
        account_id = sv_acct["account_id"]
        txs = by_account.get(account_id, [])
        results.append(_build_account_stats(account_id, sv_acct, txs))

    return results


def _build_account_stats(
    account_id: str, sv_acct: dict, txs: list[dict],
) -> dict:
    """Build aggregated statistics for a single account."""
    booked_count = sum(1 for t in txs if t["status"] == "BOOKED")
    pending_count = sum(1 for t in txs if t["status"] == "PENDING")

    inflow_count = 0
    inflow_total = Decimal("0")
    outflow_count = 0
    outflow_total = Decimal("0")

    dates: list[str] = []
    cp_totals: dict[str, Decimal] = defaultdict(Decimal)

    for tx in txs:
        signed = Decimal(tx["amount"]["signed"])
        if signed >= 0:
            inflow_count += 1
            inflow_total += signed
        else:
            outflow_count += 1
            outflow_total += signed

        dates.append(tx["value_date"])

        cp_name = (tx.get("counterparty") or {}).get("name") or ""
        if cp_name:
            cp_totals[cp_name] += abs(signed)

    top_counterparties = sorted(
        [{"name": n, "total": str(t)} for n, t in cp_totals.items()],
        key=lambda c: Decimal(c["total"]),
        reverse=True,
    )

    period = {}
    if dates:
        dates_sorted = sorted(dates)
        period = {"from": dates_sorted[0], "to": dates_sorted[-1]}

    return {
        "account_id": account_id,
        "iban": sv_acct.get("iban", ""),
        "currency": sv_acct.get("currency", ""),
        "period": period,
        "transaction_count": {
            "booked": booked_count,
            "pending": pending_count,
            "total": booked_count + pending_count,
        },
        "inflow": {
            "count": inflow_count,
            "total": str(inflow_total),
            "avg": str(
                (inflow_total / inflow_count).quantize(Decimal("0.01"))
            ) if inflow_count > 0 else "0",
        },
        "outflow": {
            "count": outflow_count,
            "total": str(outflow_total),
            "avg": str(
                (outflow_total / outflow_count).quantize(Decimal("0.01"))
            ) if outflow_count > 0 else "0",
        },
        "top_counterparties": top_counterparties,
    }
