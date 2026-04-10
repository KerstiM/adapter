"""
C-06: SV -> monthly cashflow timeline projection — pure function.

No I/O, no jsonschema/pathlib/os imports.

This module is a UK3 evolution artifact that extends the projection
extensibility evidence beyond C-05.  Unlike C-02 (flat rows), C-03
(per-account context window) and C-05 (flat per-account aggregates),
C-06 produces a *structurally novel* output shape: an ordered temporal
series of monthly buckets, each carrying an accumulating running
balance.  It follows the same pure-function pattern as the other
``project_*`` projections and lives on top of the SV intermediate
representation without requiring any pipeline, port or adapter change.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


def project_monthly_balance(sv_bundle: dict) -> list[dict]:
    """Project SV -> per-account monthly cashflow timeline (C-06).

    For every account, group BOOKED + PENDING transactions by calendar
    month (``YYYY-MM`` prefix of ``value_date``), aggregate inflow /
    outflow totals and counts per bucket, then walk the buckets in
    chronological order producing a running balance starting at zero.

    Filter: BOOKED + PENDING (same as C-02 / C-03 / C-05).

    Parameters
    ----------
    sv_bundle : dict
        The validated SV bundle produced by the pipeline.

    Returns
    -------
    list[dict]
        One entry per account, each containing an ordered ``timeline``
        of monthly bucket dicts with inflow/outflow/net/running_balance.
    """
    # account_id -> month -> accumulator
    by_account: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(_empty_bucket),
    )

    for tx in sv_bundle.get("transactions", []):
        if tx["status"] not in ("BOOKED", "PENDING"):
            continue

        account_id = tx["account_id"]
        month = tx["value_date"][:7]
        signed = Decimal(tx["amount"]["signed"])

        bucket = by_account[account_id][month]
        if signed >= 0:
            bucket["inflow_count"] += 1
            bucket["inflow_total"] += signed
        else:
            bucket["outflow_count"] += 1
            bucket["outflow_total"] += signed

    results: list[dict] = []
    for sv_acct in sv_bundle.get("accounts", []):
        account_id = sv_acct["account_id"]
        month_buckets = by_account.get(account_id, {})

        timeline: list[dict] = []
        running = Decimal("0")
        for month in sorted(month_buckets.keys()):
            bucket = month_buckets[month]
            net = bucket["inflow_total"] + bucket["outflow_total"]
            running += net
            timeline.append({
                "month": month,
                "inflow_count": bucket["inflow_count"],
                "inflow_total": str(bucket["inflow_total"]),
                "outflow_count": bucket["outflow_count"],
                "outflow_total": str(bucket["outflow_total"]),
                "net": str(net),
                "running_balance": str(running),
            })

        results.append({
            "account_id": account_id,
            "iban": sv_acct.get("iban", ""),
            "currency": sv_acct.get("currency", ""),
            "timeline": timeline,
        })

    return results


def _empty_bucket() -> dict:
    return {
        "inflow_count": 0,
        "inflow_total": Decimal("0"),
        "outflow_count": 0,
        "outflow_total": Decimal("0"),
    }
