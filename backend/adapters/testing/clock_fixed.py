"""FixedClock — deterministic ClockPort for tests.

Returns the same timestamp and run-ID on every call, making pipeline output
fully deterministic.  Use this adapter in integration tests that need
reproducible, byte-identical output files.

Usage::

    clock = FixedClock("2026-01-01T00:00:00Z", "test-run-001")
    assert clock.now_utc()    == "2026-01-01T00:00:00Z"
    assert clock.new_run_id() == "test-run-001"
"""

from __future__ import annotations


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
