"""FsSpecAdapter — filesystem implementation of SpecPort.

Reads the run profile from ``spec/profiles/<profile_id>.yaml`` and resolves
all referenced spec files (schemas, contracts, rulesets) relative to the
repository root.

Usage::

    from adapters.fs.spec_fs import FsSpecAdapter
    spec = FsSpecAdapter(spec_dir=Path("spec"))
    profile = spec.load_profile()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from adapters.fs._io import load_json


class FsSpecAdapter:
    """Filesystem adapter for :class:`ports.spec_port.SpecPort`.

    Parameters
    ----------
    spec_dir:
        Path to the ``spec/`` directory.  The repository root is inferred as
        ``spec_dir.parent`` so that profile-relative paths (e.g.
        ``"spec/schemas/S-01_sv_schema.json"``) resolve correctly.
    """

    def __init__(self, spec_dir: str | Path) -> None:
        self._spec_dir = Path(spec_dir).resolve()
        self._repo_root = self._spec_dir.parent
        # Simple in-memory cache keyed by profile_id.
        self._profile_cache: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # SpecPort interface
    # ------------------------------------------------------------------

    def load_profile(self, profile_id: str = "default") -> dict[str, Any]:
        """Return the fully-resolved run profile as a plain dict.

        The result is cached after the first call so that subsequent calls to
        ``load_schema`` / ``load_contract`` / ``load_ruleset`` are cheap.
        """
        if profile_id in self._profile_cache:
            return self._profile_cache[profile_id]

        profile_path = self._spec_dir / "profiles" / f"{profile_id}.yaml"
        if not profile_path.exists():
            raise KeyError(f"Profile {profile_id!r} not found at {profile_path}")

        raw = self._load_yaml(profile_path)

        resolved: dict[str, Any] = {
            "id": raw["id"],
            "version": raw["version"],
        }

        # Load schemas
        resolved["schemas"] = {}
        for key, relpath in raw.get("schemas", {}).items():
            path = self._resolve_path(relpath)
            resolved["schemas"][key] = load_json(path)

        # Load contracts
        resolved["contracts"] = {}
        for key, relpath in raw.get("contracts", {}).items():
            path = self._resolve_path(relpath)
            resolved["contracts"][key] = self._load_yaml(path)

        # Load rulesets
        resolved["rulesets"] = {}
        for key, relpath in raw.get("rulesets", {}).items():
            path = self._resolve_path(relpath)
            resolved["rulesets"][key] = self._load_yaml(path)

        # Preserve run_policy as-is
        if "run_policy" in raw:
            resolved["run_policy"] = raw["run_policy"]

        # Forward optional profile-level keys as-is
        for optional_key in ("report_extensions", "target_models", "projections"):
            if optional_key in raw:
                resolved[optional_key] = raw[optional_key]

        self._profile_cache[profile_id] = resolved
        return resolved

    def load_schema(self, schema_id: str) -> dict[str, Any]:
        """Return the JSON Schema dict for *schema_id* (e.g. ``"S-01"``).

        Raises ``KeyError`` when the schema is not registered in the default
        profile.
        """
        profile = self.load_profile()
        if schema_id not in profile["schemas"]:
            raise KeyError(f"Schema {schema_id!r} not registered in profile")
        return profile["schemas"][schema_id]

    def load_contract(self, contract_id: str) -> dict[str, Any]:
        """Return the contract dict for *contract_id* (e.g. ``"C-01"``).

        Raises ``KeyError`` when the contract is not registered in the default
        profile.
        """
        profile = self.load_profile()
        if contract_id not in profile["contracts"]:
            raise KeyError(f"Contract {contract_id!r} not registered in profile")
        return profile["contracts"][contract_id]

    def load_ruleset(self, ruleset_id: str) -> dict[str, Any]:
        """Return the ruleset dict for *ruleset_id* (e.g. ``"R-01"``).

        Raises ``KeyError`` when the ruleset is not registered in the default
        profile.
        """
        profile = self.load_profile()
        if ruleset_id not in profile["rulesets"]:
            raise KeyError(f"Ruleset {ruleset_id!r} not registered in profile")
        return profile["rulesets"][ruleset_id]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, relpath: str) -> Path:
        """Resolve a profile-relative path to an absolute ``Path``.

        Paths in the profile are written relative to the repository root
        (e.g. ``"spec/schemas/S-01_sv_schema.json"``).

        Raises ``ValueError`` when the resolved path escapes the repository
        root (e.g. via ``../``) and ``FileNotFoundError`` when the file does
        not exist.
        """
        repo_root = self._repo_root.resolve()
        path = (repo_root / relpath).resolve()
        if not path.is_relative_to(repo_root):
            raise ValueError(
                f"Spec path escapes repository root: {relpath!r} -> {path}"
            )
        if not path.exists():
            raise FileNotFoundError(
                f"Spec file missing (profile points to it): {relpath!r} -> {path}"
            )
        return path

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
