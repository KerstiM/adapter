"""Presentation-facing helper for the HTTP API's LLM preview response.

Builds the frontend-shaped view (English narrative, ``accountSummary``,
``topCategories``) from a single already-loaded LLM context dict.  Lives in
``entrypoints/`` because the output shape is a UI contract (camelCase keys,
dash placeholders, English text), not a domain concept.

No file I/O, no HTTP, no Path — pure transform so it can be unit-tested
without spinning up the API server.
"""
from __future__ import annotations


def build_llm_preview_view(raw_context: dict) -> dict | None:
    """Build the frontend-shaped LLM preview view from one LLM context.

    Returns ``None`` when the context has no transactions.
    """
    meta = raw_context.get("meta", {})
    txs = raw_context.get("tx", [])
    if not txs:
        return None

    dates = [t["d"] for t in txs if t.get("d")]
    total_income = 0.0
    total_expenses = 0.0
    category_map: dict[str, dict] = {}

    for tx in txs:
        amount = float(tx.get("a", 0))
        direction = tx.get("dir", "")
        reason = tx.get("r", "Other") or "Other"

        if direction == "IN" or amount > 0:
            total_income += abs(amount)
        else:
            total_expenses += abs(amount)

        reason_parts = reason.split()
        cat = reason_parts[0] if reason_parts else "Other"
        if cat not in category_map:
            category_map[cat] = {"category": cat, "total": 0.0, "count": 0}
        category_map[cat]["total"] += amount
        category_map[cat]["count"] += 1

    net_flow = total_income - total_expenses
    period_start = min(dates) if dates else "—"
    period_end = max(dates) if dates else "—"

    top_categories = sorted(
        category_map.values(), key=lambda c: abs(c["total"]), reverse=True,
    )

    iban = meta.get("iban", "")
    currency = meta.get("currency", "EUR")
    narrative = (
        f"Account {iban}: {len(txs)} transactions "
        f"from {period_start} to {period_end}. "
        f"Total income {total_income:.2f} {currency}, "
        f"expenses {total_expenses:.2f} {currency}, "
        f"net flow {net_flow:+.2f} {currency}."
    )

    return {
        "narrative": narrative,
        "accountSummary": {
            "periodStart": period_start,
            "periodEnd": period_end,
            "totalIncome": total_income,
            "totalExpenses": total_expenses,
            "netFlow": net_flow,
        },
        "topCategories": top_categories,
    }
