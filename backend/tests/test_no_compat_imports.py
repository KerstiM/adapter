"""
Guard test: the legacy compatibility layer ``backend/adapter/`` must not exist.

Checks two things:
1. The directory ``backend/adapter/`` must not be present on disk.
2. No ``.py`` file in the repository may contain the import token
   ``adapter.pipeline`` (the old compat-layer entry-point).

This test does NOT shell out to ripgrep or any external tool — it walks the
file tree with ``pathlib`` and does plain string matching.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/tests/ -> backend -> repo
BACKEND_DIR = REPO_ROOT / "backend"
LEGACY_DIR = BACKEND_DIR / "adapter"

# Strings that must not appear in any .py source file.
FORBIDDEN_TOKENS = [
    "adapter.pipeline",
]

# This file itself contains the forbidden tokens as string literals for the
# check — exclude it from scanning.
_SELF = Path(__file__).resolve()


def _python_files() -> list[Path]:
    """Collect all .py files under the repository root."""
    return sorted(p for p in REPO_ROOT.rglob("*.py") if p.resolve() != _SELF)


class TestNoLegacyCompatLayer:

    def test_adapter_directory_does_not_exist(self) -> None:
        assert not LEGACY_DIR.exists(), (
            f"Legacy compat directory still exists: {LEGACY_DIR.relative_to(REPO_ROOT)}"
        )

    def test_no_compat_import_tokens(self) -> None:
        hits: list[str] = []
        for py_file in _python_files():
            try:
                source = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = py_file.relative_to(REPO_ROOT)
            for token in FORBIDDEN_TOKENS:
                if token in source:
                    hits.append(f"  {rel}  contains '{token}'")
        if hits:
            pytest.fail(
                "Legacy compat-layer references found:\n" + "\n".join(hits)
            )
