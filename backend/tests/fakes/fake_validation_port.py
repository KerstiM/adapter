"""In-memory fake of ValidationPort for unit testing."""

from __future__ import annotations

from typing import Any


class FakeValidationPort:
    """Configurable fake — returns pre-set validation results.

    By default returns no errors (all schemas pass).  Override via
    *results* to inject specific validation failures.
    """

    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = results or []

    def validate(self, data: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
        return list(self._results)
