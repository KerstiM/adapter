"""RealClock — production ClockPort implementation.

Uses ``datetime.now(timezone.utc)`` for wall-clock time and ``uuid.uuid4()``
for unique run identifiers.  Every production run gets a fresh, real timestamp
and a random run ID.

ISO-8601 format
---------------
All timestamps emitted by this adapter use a single, canonical format defined
by :data:`ISO_UTC_FORMAT`:

    ``"YYYY-MM-DDTHH:MM:SSZ"``   (seconds precision, literal ``Z`` suffix)

This constant is the **single source of truth** for timestamp serialisation
across the entire project.  Import it when you need to format or validate
UTC timestamps elsewhere::

    from adapters.system.clock_real import ISO_UTC_FORMAT

Usage::

    clock = RealClock()
    ts     = clock.now_utc()       # e.g. "2026-02-24T14:30:00Z"
    run_id = clock.new_run_id()    # e.g. "3f8a1c2b9d04"
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

# ── Single source of truth for ISO-8601 UTC serialisation ──────────────────
ISO_UTC_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
"""strftime / strptime pattern: seconds precision, literal Z suffix."""


class RealClock:
    """Production :class:`ports.clock_port.ClockPort` implementation.

    * :meth:`now_utc` — current UTC time formatted as ISO-8601 (see
      :data:`ISO_UTC_FORMAT`).
    * :meth:`new_run_id` — first 12 hex characters of a random UUID4.
    """

    def now_utc(self) -> str:
        """Return the current UTC time as an ISO-8601 string (seconds precision, Z suffix)."""
        return datetime.now(timezone.utc).strftime(ISO_UTC_FORMAT)

    def new_run_id(self) -> str:
        """Return the first 12 hex characters of a random UUID4 as the run identifier."""
        return uuid.uuid4().hex[:12]
