"""Shared dataset-name resolver for CLI and HTTP API entrypoints.

A single canonical lookup so `--data D1` (CLI) and `{"datasetId": "D1"}`
(HTTP) behave identically: case-insensitive, underscore-fenced prefix
match, and unambiguous (multiple candidates raise instead of silently
picking one).
"""
from __future__ import annotations

from pathlib import Path


class AmbiguousDatasetError(ValueError):
    """Raised when a dataset name matches more than one folder."""

    def __init__(self, name: str, matches: list[str]) -> None:
        self.name = name
        self.matches = matches
        super().__init__(
            f"Ambiguous dataset '{name}', matches: {', '.join(matches)}"
        )


def resolve_dataset_by_name(
    name: str,
    search_dirs: list[Path],
) -> Path | None:
    """Find a dataset folder by short or full name under any *search_dirs*.

    Matching rules (case-insensitive):
      1. Exact folder name (e.g. ``D1_synth_valid_small``).
      2. Prefix match with ``"_"`` fence (``D1`` matches ``D1_*`` but not
         ``D10_*``).

    A folder qualifies only if it contains an ``accounts.json`` file.
    Returns ``None`` when no candidate qualifies; raises
    :class:`AmbiguousDatasetError` when more than one does.
    """
    name_upper = name.upper()
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue

        exact = search_dir / name
        if exact.is_dir() and (exact / "accounts.json").exists():
            return exact

        matches = sorted(
            d for d in search_dir.iterdir()
            if d.is_dir()
            and (d.name.upper() == name_upper
                 or d.name.upper().startswith(name_upper + "_"))
            and (d / "accounts.json").exists()
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise AmbiguousDatasetError(name, [m.name for m in matches])

    return None
