"""Shared registry helper for spec-driven rule modules.

Each rule module (R-01 invariants, QC quality checks) registers a Python
predicate per rule ID.  The metadata (id, severity, message, action) lives
exclusively in the YAML ruleset; the registry only maps rule ID -> predicate.

``assert_registry_matches_yaml`` enforces at runtime that the YAML and the
code agree on the set of rule IDs.  A new rule added to YAML without a
matching predicate (or vice versa) makes the pipeline fail loudly at startup
instead of silently dropping a check.
"""
from __future__ import annotations


def assert_registry_matches_yaml(
    code_rule_ids: set[str],
    yaml_rule_ids: set[str],
    ruleset_label: str,
) -> None:
    missing_in_code = yaml_rule_ids - code_rule_ids
    missing_in_yaml = code_rule_ids - yaml_rule_ids
    if missing_in_code or missing_in_yaml:
        raise RuntimeError(
            f"{ruleset_label}: YAML/code mismatch. "
            f"missing in code: {sorted(missing_in_code)}; "
            f"missing in YAML: {sorted(missing_in_yaml)}"
        )


def flag_from_rule(rule: dict) -> dict:
    """Build a transaction flag dict using metadata from a YAML rule entry."""
    return {
        "id": rule["id"],
        "severity": rule["severity"],
        "message": rule["message"],
    }
