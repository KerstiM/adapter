"""SpecPort — abstract interface for loading specification artefacts.

Application layer uses this port to retrieve schemas, contracts, rulesets
and run-profiles.  No filesystem paths appear in the signatures; path
resolution is the responsibility of the concrete adapter (adapters/fs/spec_fs).
"""

from __future__ import annotations

from typing import Any, Protocol


class SpecPort(Protocol):
    """Read-only access to specification artefacts."""

    def load_profile(self, profile_id: str = "default") -> dict[str, Any]:
        """Return the fully-resolved run profile as a plain dict.

        The returned structure contains at minimum:
          - ``id``         (str)
          - ``version``    (str)
          - ``schemas``    (dict[str, dict])  — keyed by schema ID
          - ``contracts``  (dict[str, dict])  — keyed by contract ID
          - ``rulesets``   (dict[str, dict])  — keyed by ruleset ID
          - ``run_policy`` (dict)             — optional

        Raises ``KeyError`` or a domain-specific error when the profile
        cannot be found or is malformed.
        """
        ...

    def load_schema(self, schema_id: str) -> dict[str, Any]:
        """Return the JSON Schema dict for *schema_id* (e.g. ``"S-01"``).

        Raises ``KeyError`` when the schema is not registered.
        """
        ...

    def load_contract(self, contract_id: str) -> dict[str, Any]:
        """Return the contract dict for *contract_id* (e.g. ``"C-01"``).

        Raises ``KeyError`` when the contract is not registered.
        """
        ...

    def load_ruleset(self, ruleset_id: str) -> dict[str, Any]:
        """Return the ruleset dict for *ruleset_id* (e.g. ``"R-01"``).

        Raises ``KeyError`` when the ruleset is not registered.
        """
        ...
