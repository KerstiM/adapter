"""Shared pure-value helpers for the domain layer.

Small parsing / validation primitives that appear in more than one bounded
context (e.g. both ``domain.mapping`` and ``domain.rules``).  Centralising
them here prevents silent divergence of semantics.

No I/O, no pathlib/os — only stdlib.
"""
from __future__ import annotations

from datetime import datetime  # NB: strptime only — datetime.now() / .utcnow() MUST NOT be used in domain layer
from decimal import Decimal, InvalidOperation


def parse_decimal(s: str | None) -> Decimal | None:
    """Parse a string to :class:`~decimal.Decimal`; return ``None`` on failure.

    Accepts ``None`` directly (returns ``None``) so callers can pass through
    optional fields without an extra guard.
    """
    if s is None:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def is_iso_date(s: str | None) -> bool:
    """Return ``True`` iff *s* is a valid ``YYYY-MM-DD`` calendar date."""
    if not s:
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False
