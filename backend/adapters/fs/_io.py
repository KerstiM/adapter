"""Shared filesystem I/O helpers for the ``adapters.fs`` package.

Private to the adapter subsystem — other layers must not import these.
Consolidating here prevents each ``Fs*Adapter`` from growing its own
private ``_load_json`` / ``_load_yaml`` clone.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Read *path* as UTF-8 JSON and return the decoded mapping.

    Raises ``FileNotFoundError`` when the file does not exist and
    ``json.JSONDecodeError`` when the payload is malformed.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)
