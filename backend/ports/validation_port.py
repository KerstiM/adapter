"""ValidationPort — abstract interface for schema validation.

Application layer uses this port to validate data against JSON schemas.
The concrete validation library (e.g. jsonschema) is an infrastructure
concern and stays in the adapter layer.
"""

from __future__ import annotations

from typing import Any, Protocol


class ValidationPort(Protocol):
    """Validate data against a JSON Schema.

    Returns an empty list on success. On failure, returns a list of dicts
    each containing at minimum:

      - ``message`` (str) — human-readable validation error
      - ``field_path`` (str | None) — dotted path to the offending field
    """

    def validate(self, data: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
        ...
