"""
Shared helpers for SV projections (C-02, C-03, C-05, C-06).

No I/O, no jsonschema/pathlib/os imports.
"""
from __future__ import annotations

from typing import Iterator


PROJECTABLE_STATUSES: tuple[str, ...] = ("BOOKED", "PENDING")


def iter_projectable(sv_bundle: dict) -> Iterator[dict]:
    """Yield transactions eligible for downstream projection.

    A transaction is *projectable* when its ``status`` is one of
    :data:`PROJECTABLE_STATUSES` (``BOOKED`` or ``PENDING``). All other
    statuses (e.g. ``INFORMATION``) are skipped.
    """
    for tx in sv_bundle.get("transactions", []):
        if tx["status"] in PROJECTABLE_STATUSES:
            yield tx
