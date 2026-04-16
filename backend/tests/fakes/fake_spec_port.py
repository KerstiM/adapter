"""In-memory fake of SpecPort — loads real schemas/contracts/rulesets.

The fake reads JSON Schemas, contract YAMLs and ruleset YAMLs from the repo at
instantiation time so that unit tests validate pipeline output against the
same specs as production. Override via *profile_override* to plug in
permissive dicts where a test intentionally exercises malformed input.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMAS_DIR = _REPO_ROOT / "spec" / "schemas"
_CONTRACTS_DIR = _REPO_ROOT / "spec" / "contracts"
_RULESETS_DIR = _REPO_ROOT / "spec" / "rulesets"

_SCHEMA_FILES: dict[str, str] = {
    "S-00A": "S-00A_berlin_accounts.schema.json",
    "S-00B": "S-00B_berlin_transactions.schema.json",
    "S-00C": "S-00C_berlin_standing_orders.schema.json",
    "S-01":  "S-01_sv_schema.json",
    "S-02":  "S-02_ml_projection_schema.json",
    "S-03":  "S-03_llm_context_schema.json",
    "S-05":  "S-05_collected_report_schema.json",
}

_CONTRACT_FILES: dict[str, str] = {
    "C-01": "C-01_berlin_to_sv.yaml",
    "C-02": "C-02_sv_to_ml.yaml",
    "C-03": "C-03_sv_to_llm.yaml",
}

_RULESET_FILES: dict[str, str] = {
    "R-01": "R-01_sv_invariants.yaml",
}


def _load_real_schemas() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for sid, filename in _SCHEMA_FILES.items():
        path = _SCHEMAS_DIR / filename
        with open(path, encoding="utf-8") as f:
            schemas[sid] = json.load(f)
    return schemas


def _load_real_yaml(base: Path, files: dict[str, str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, filename in files.items():
        path = base / filename
        with open(path, encoding="utf-8") as f:
            out[key] = yaml.safe_load(f)
    return out


def _default_profile() -> dict[str, Any]:
    """Return a profile that mirrors production schemas, contracts and rulesets."""
    return {
        "id": "default",
        "version": "1.0.0",
        "schemas": _load_real_schemas(),
        "contracts": _load_real_yaml(_CONTRACTS_DIR, _CONTRACT_FILES),
        "rulesets": _load_real_yaml(_RULESETS_DIR, _RULESET_FILES),
        "run_policy": {
            "partial_success_policy": {
                "fail_on": {
                    "any_severity": "ERROR",
                    "ratio_over_records": 0.05,
                },
            },
        },
    }


class FakeSpecPort:
    """Implements :class:`ports.spec_port.SpecPort` using in-memory dicts.

    By default a minimal permissive profile is used.  Override via
    *profile_override* to inject custom schemas, contracts, or policies.

    Parameters
    ----------
    profile_override:
        If provided, this dict **replaces** the default profile entirely.
        Callers can use :func:`_default_profile` as a starting point and
        patch individual keys.
    """

    def __init__(
        self,
        profile_override: dict[str, Any] | None = None,
    ) -> None:
        self._profile = profile_override or _default_profile()

    def load_profile(self, profile_id: str = "default") -> dict[str, Any]:
        return self._profile

    def load_schema(self, schema_id: str) -> dict[str, Any]:
        schemas = self._profile.get("schemas", {})
        if schema_id not in schemas:
            raise KeyError(f"Schema {schema_id!r} not in fake profile")
        return schemas[schema_id]

    def load_contract(self, contract_id: str) -> dict[str, Any]:
        contracts = self._profile.get("contracts", {})
        if contract_id not in contracts:
            raise KeyError(f"Contract {contract_id!r} not in fake profile")
        return contracts[contract_id]

    def load_ruleset(self, ruleset_id: str) -> dict[str, Any]:
        rulesets = self._profile.get("rulesets", {})
        if ruleset_id not in rulesets:
            raise KeyError(f"Ruleset {ruleset_id!r} not in fake profile")
        return rulesets[ruleset_id]
