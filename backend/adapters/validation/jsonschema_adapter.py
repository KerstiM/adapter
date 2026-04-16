"""JsonSchemaValidationAdapter — jsonschema-backed implementation of ValidationPort."""

from __future__ import annotations

from typing import Any

import jsonschema


class JsonSchemaValidationAdapter:
    """Validates data against JSON Schema using the ``jsonschema`` library.

    Implements :class:`ports.validation_port.ValidationPort`.
    """

    def validate(self, data: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as e:
            errors.append({
                "message": e.message,
                "field_path": ".".join(str(p) for p in e.absolute_path) or None,
            })
        return errors
