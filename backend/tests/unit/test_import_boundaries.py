"""
Architecture import-boundary test for the domain layer.

The domain layer (backend/domain/) must contain only pure business logic.
It must NOT import:
  - I/O or platform modules: pathlib, os, sys
  - External libraries:      requests, pandas
  - Internal adapter/entrypoints: backend.adapters, backend.entrypoints, adapters, entrypoints

Any violation means the domain layer has acquired an I/O or infrastructure
dependency, which breaks the hexagonal-architecture contract.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]          # backend/
DOMAIN_DIR = BACKEND_DIR / "domain"

# Top-level module names that domain code must never import.
# Rationale: I/O layer (pathlib, os, sys) belongs in adapters; non-deterministic
# sources (uuid, random, secrets, time) violate the determinism guarantee —
# any clock or id generation must go through ClockPort / explicit run_id input.
# `datetime` is intentionally allowed because domain parses ISO date strings
# via `datetime.strptime`; `datetime.now()` / `.utcnow()` must not be used
# (convention; not automatically enforced here).
FORBIDDEN_STDLIB = {
    "pathlib", "os", "sys",
    "uuid", "random", "secrets", "time",
}
FORBIDDEN_EXTERNAL = {"requests", "pandas"}

# Internal packages that domain must never reach into.
FORBIDDEN_INTERNAL = {
    "adapters", "backend.adapters",
    "ports", "application", "entrypoints",
    "backend.ports", "backend.application", "backend.entrypoints",
}

FORBIDDEN_ALL = FORBIDDEN_STDLIB | FORBIDDEN_EXTERNAL | FORBIDDEN_INTERNAL


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _collect_imports(source: str) -> list[tuple[int, str]]:
    """Return (line_number, top_level_module) for every import in *source*."""
    tree = ast.parse(source)
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                results.append((node.lineno, top))
                # Also check the full dotted path for internal packages
                if alias.name in FORBIDDEN_INTERNAL:
                    results.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                results.append((node.lineno, top))
                # Also check the full dotted path for internal packages
                if node.module in FORBIDDEN_INTERNAL:
                    results.append((node.lineno, node.module))
    return results


def find_boundary_violations() -> list[str]:
    """Scan every .py file under backend/domain/ for forbidden imports.

    Returns a list of human-readable violation strings (empty == clean).
    """
    violations: list[str] = []
    for py_file in sorted(DOMAIN_DIR.rglob("*.py")):
        rel = py_file.relative_to(BACKEND_DIR)
        source = py_file.read_text(encoding="utf-8")
        for lineno, module in _collect_imports(source):
            if module in FORBIDDEN_ALL:
                violations.append(f"{rel}:{lineno}  imports '{module}'")
    return violations


# ---------------------------------------------------------------------------
# Pytest entry-point
# ---------------------------------------------------------------------------

class TestImportBoundaries:
    """Domain layer must not import forbidden modules."""

    def test_no_forbidden_imports_in_domain(self) -> None:
        violations = find_boundary_violations()
        if violations:
            msg = (
                "Domain import-boundary violations detected:\n"
                + "\n".join(f"  {v}" for v in violations)
            )
            pytest.fail(msg)


# ---------------------------------------------------------------------------
# Standalone runner (used by scripts/qa/run_full_qa.py)
# ---------------------------------------------------------------------------

def check_import_boundaries() -> tuple[bool, list[str]]:
    """Return (passed, messages) for QA integration."""
    violations = find_boundary_violations()
    if violations:
        msgs = ["Domain import-boundary violations:"]
        for v in violations:
            msgs.append(f"  {v}")
        return False, msgs
    return True, [f"  scanned {len(list(DOMAIN_DIR.rglob('*.py')))} domain files — no violations"]
