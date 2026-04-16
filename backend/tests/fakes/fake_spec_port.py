"""In-memory fake of SpecPort.

Schemas and contracts are inlined as permissive stubs.  Rulesets are loaded
from the canonical YAML files (R-01, QC) so the fake stays in lockstep with
the spec — there is one source of truth for rule metadata, and registry
mismatches surface in tests just as they would in production.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_SPEC_DIR = Path(__file__).resolve().parents[3] / "spec"


def _load_ruleset(filename: str) -> dict[str, Any]:
    with open(_SPEC_DIR / "rulesets" / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_spec_rulesets() -> dict[str, dict[str, Any]]:
    """Return the {R-01, QC} rulesets loaded from canonical YAML.

    Tests that build their own profile dict (rather than using the fake's
    default profile) can drop this into the ``rulesets`` slot to keep one
    source of truth for rule metadata.
    """
    return {
        "R-01": _load_ruleset("R-01_sv_invariants.yaml"),
        "QC": _load_ruleset("QC_quality_checks.yaml"),
    }


def _default_profile() -> dict[str, Any]:
    """Return a minimal profile that lets the pipeline run without errors.

    Schemas are permissive (empty JSON Schema ``{}`` matches anything) so that
    unit tests can focus on pipeline logic rather than schema validation.
    Rulesets are real spec content so the registry/YAML consistency check
    behaves identically to production.
    """
    return {
        "id": "default",
        "version": "1.0.0",
        "schemas": {
            "S-00A": {},   # accepts any accounts payload
            "S-00B": {},   # accepts any transactions payload
            "S-00C": {},   # accepts any standing-orders payload
            "S-01": {},    # accepts any SV bundle
            "S-02": {},    # accepts any ML projection row
            "S-03": {},
            "S-05": {},
        },
        "contracts": {
            "C-01": {"version": "1.0.0"},
            "C-02": {"version": "1.0.0"},
            "C-03": {
                "version": "1.0.0",
                "window": {"last_n": 200},
                "truncate": {
                    "counterparty_name_max_len": 80,
                    "remittance_max_len": 160,
                },
            },
        },
        "rulesets": load_spec_rulesets(),
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
