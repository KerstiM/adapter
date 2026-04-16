"""R-01 invariant checks — predicates registered against YAML rule IDs.

Rule metadata (id, severity, message, action) lives in
``spec/rulesets/R-01_sv_invariants.yaml``.  This module only provides the
Python predicate per rule.  ``check_invariants`` reads the YAML ruleset and
emits flags using the metadata declared there.

INV-09 (duplicate detection) is group-level rather than per-transaction,
so it lives in ``deduplicate_transactions`` and is registered as
externally-handled.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Callable

from domain._shared.values import is_iso_date, parse_decimal
from domain.rules._registry import assert_registry_matches_yaml, flag_from_rule


# ---------------------------------------------------------------------------
# Per-transaction predicates (return True when the rule should fire)
# ---------------------------------------------------------------------------

TX_PREDICATES: dict[str, Callable[[dict], bool]] = {}


def _register(rule_id: str):
    def deco(fn: Callable[[dict], bool]) -> Callable[[dict], bool]:
        TX_PREDICATES[rule_id] = fn
        return fn
    return deco


@_register("INV-01_CURRENCY_FORMAT")
def _inv01(tx: dict) -> bool:
    currency = tx.get("amount", {}).get("currency", "") or ""
    return not re.match(r"^[A-Z]{3}$", currency)


@_register("INV-02_VALUE_DATE_REQUIRED")
def _inv02(tx: dict) -> bool:
    return not tx.get("value_date")


@_register("INV-03_AMOUNT_PARSEABLE")
def _inv03(tx: dict) -> bool:
    amount = tx.get("amount", {})
    for key in ("raw", "signed", "abs"):
        if parse_decimal(amount.get(key)) is None:
            return True
    return False


@_register("INV-04_BOOKING_DATE_OPTIONAL")
def _inv04(tx: dict) -> bool:
    bd = tx.get("booking_date")
    return bd is not None and not is_iso_date(bd)


@_register("INV-05_AMOUNT_SIGN_MATCHES_DIRECTION")
def _inv05(tx: dict) -> bool:
    amount = tx.get("amount", {})
    raw = (amount.get("raw") or "").strip()
    parsed = parse_decimal(raw)
    if parsed is None or parsed == 0:
        return False
    raw_is_negative = raw.startswith("-")
    direction = tx.get("direction")
    if direction == "OUT" and not raw_is_negative:
        return True
    if direction == "IN" and raw_is_negative:
        return True
    return False


# Group-level rule whose metadata is read from YAML in deduplicate_transactions.
EXTERNALLY_HANDLED = {"INV-09_DUPLICATE_RECORD_ID"}


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------

def check_invariants(
    sv_bundle: dict, ruleset: dict,
) -> tuple[list[dict], list[dict]]:
    """Apply R-01 per-transaction invariants. Returns (valid, dropped).

    DROP_RECORD rules run first; if any fire the record is dropped without
    evaluating FLAG_ONLY rules.  This preserves the historical semantics where
    a record failing a hard validity rule does not also accumulate soft
    diagnostic flags.
    """
    rules = ruleset["rules"]
    rules_by_id = {r["id"]: r for r in rules}
    handled_ids = set(TX_PREDICATES.keys()) | EXTERNALLY_HANDLED
    assert_registry_matches_yaml(handled_ids, set(rules_by_id.keys()), "R-01")

    drop_rules = [
        r for r in rules
        if r["id"] in TX_PREDICATES and r.get("action") == "DROP_RECORD"
    ]
    flag_rules = [
        r for r in rules
        if r["id"] in TX_PREDICATES and r.get("action") == "FLAG_ONLY"
    ]

    valid: list[dict] = []
    dropped: list[dict] = []
    for tx in sv_bundle.get("transactions", []):
        drop = False
        for rule in drop_rules:
            if TX_PREDICATES[rule["id"]](tx):
                tx["flags"].append(flag_from_rule(rule))
                drop = True
        if drop:
            dropped.append(tx)
            continue
        for rule in flag_rules:
            if TX_PREDICATES[rule["id"]](tx):
                tx["flags"].append(flag_from_rule(rule))
        valid.append(tx)

    return valid, dropped


def deduplicate_transactions(
    transactions: list[dict], ruleset: dict,
) -> tuple[list[dict], list[dict]]:
    """Deduplicate SV transactions by (account_id, record_id) -- INV-09.

    Within each duplicate group the survivor is selected deterministically by
    sorting on (source.input_file, source.input_path, status, value_date,
    booking_date, transaction_id).  Losers receive the INV-09 flag (metadata
    read from the R-01 ruleset) and are returned as dedupe drops.
    """
    inv09 = next(
        (r for r in ruleset["rules"] if r["id"] == "INV-09_DUPLICATE_RECORD_ID"),
        None,
    )
    if inv09 is None:
        raise RuntimeError("R-01 ruleset missing INV-09_DUPLICATE_RECORD_ID")

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
        group.sort(key=_sort_key)
        kept.append(group[0])
        for dup in group[1:]:
            dup["flags"].append(flag_from_rule(inv09))
            dedupe_drops.append(dup)

    return kept, dedupe_drops
