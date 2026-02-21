"""In-memory fake of SpecPort — no filesystem access."""

from __future__ import annotations

from typing import Any


def _default_profile() -> dict[str, Any]:
    """Return a minimal profile that lets the pipeline run without errors.

    Schemas are permissive (empty JSON Schema ``{}`` matches anything) so that
    unit tests can focus on pipeline logic rather than schema validation.
    """
    return {
        "id": "default",
        "version": "1.0.0",
        "schemas": {
            "S-00A": {},   # accepts any accounts payload
            "S-00B": {},   # accepts any transactions payload
            "S-00C": {},   # accepts any standing-orders payload
            "S-01": {},    # accepts any SV bundle
            "S-02": {},
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
        "rulesets": {
            "R-01": {"version": "1.0.0"},
        },
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
