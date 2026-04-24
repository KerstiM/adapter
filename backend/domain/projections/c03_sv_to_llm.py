"""
C-03: SV -> LLM context projection — pure functions.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

from domain.projections._shared import iter_projectable


def project_llm(sv_bundle: dict, profile: dict) -> list[dict]:
    """Project SV -> LLM context JSON (C-03), one per account.

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
    for tx in iter_projectable(sv_bundle):
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
