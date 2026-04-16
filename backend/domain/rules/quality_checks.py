"""Data-completeness quality checks — predicates registered against YAML rule IDs.

Rule metadata (id, severity, message) lives in
``spec/rulesets/QC_quality_checks.yaml``.  This module only provides the
Python predicate per rule.  ``check_quality`` reads the YAML ruleset and
emits flags using the metadata declared there.

These are not invariants (validity constraints that must hold for all legal
inputs).  They flag observable data gaps that may or may not indicate a
problem, depending on the source system.

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

from typing import Callable

from domain.rules._registry import assert_registry_matches_yaml, flag_from_rule


QC_PREDICATES: dict[str, Callable[[dict], bool]] = {}


def _register(rule_id: str):
    def deco(fn: Callable[[dict], bool]) -> Callable[[dict], bool]:
        QC_PREDICATES[rule_id] = fn
        return fn
    return deco


@_register("QC-1_COUNTERPARTY_MISSING")
def _qc1(tx: dict) -> bool:
    cp = tx.get("counterparty", {}) or {}
    return cp.get("name") is None and cp.get("iban") is None


def check_quality(transactions: list[dict], ruleset: dict) -> None:
    """Append quality flags to transactions in-place.

    Iterates rules in YAML order; for each transaction, fires each rule whose
    predicate returns True and appends a flag built from the rule's YAML
    metadata.
    """
    rules = ruleset["rules"]
    rules_by_id = {r["id"]: r for r in rules}
    assert_registry_matches_yaml(
        set(QC_PREDICATES.keys()), set(rules_by_id.keys()), "QC",
    )

    for tx in transactions:
        for rule in rules:
            if QC_PREDICATES[rule["id"]](tx):
                tx["flags"].append(flag_from_rule(rule))
