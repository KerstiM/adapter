"""Clock implementations for ClockPort.

Two concrete implementations are provided:

* :class:`SystemClock` — production default; uses ``datetime.now(utc)`` and
  ``uuid.uuid4()`` so every run gets a unique, wall-clock-based identifier.

* :class:`FixedClock` — deterministic override for tests; returns the same
  timestamp and run-ID every time it is called, guaranteeing byte-identical
  output files across test runs.

Usage::

    # Production
    from adapters.fs.clock_impl import SystemClock
    clock = SystemClock()
    run_id       = clock.new_run_id()        # e.g. "3f8a1c2b9d04"
    created_at   = clock.now_utc()           # e.g. "2024-06-01T12:00:00Z"

    # Tests
    from adapters.fs.clock_impl import FixedClock
    clock = FixedClock("2000-01-01T00:00:00Z", "golden_D1_test")
    assert clock.now_utc()    == "2000-01-01T00:00:00Z"
    assert clock.new_run_id() == "golden_D1_test"
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


class SystemClock:
    """Production :class:`ports.clock_port.ClockPort` implementation.

    * :meth:`now_utc` — current UTC time formatted as ``"YYYY-MM-DDTHH:MM:SSZ"``.
    * :meth:`new_run_id` — first 12 hex characters of a random UUID4.
    """

    def now_utc(self) -> str:
        """Return the current UTC time as an ISO-8601 string (seconds precision, Z suffix)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def new_run_id(self) -> str:
        """Return the first 12 hex characters of a random UUID4 as the run identifier."""
        return uuid.uuid4().hex[:12]


class FixedClock:
    """Deterministic :class:`ports.clock_port.ClockPort` for tests.

    Both methods always return the values supplied at construction time,
    making it possible to produce byte-identical output files across test runs.

    Parameters
    ----------
    fixed_utc:
        The timestamp string to return from :meth:`now_utc`.
    fixed_run_id:
        The run-ID string to return from :meth:`new_run_id`.
    """

    def __init__(self, fixed_utc: str, fixed_run_id: str) -> None:
        self._utc = fixed_utc
        self._run_id = fixed_run_id

    def now_utc(self) -> str:
        """Return the fixed UTC timestamp supplied at construction."""
        return self._utc

    def new_run_id(self) -> str:
        """Return the fixed run-ID supplied at construction."""
        return self._run_id
