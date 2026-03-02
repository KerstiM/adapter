"""Deterministic clock for unit tests — no external dependencies."""

from __future__ import annotations


class FixedClock:
    """Implements :class:`ports.clock_port.ClockPort` with fixed values.

    Returns the same timestamp and run-ID on every call, making pipeline
    output fully deterministic.

    Parameters
    ----------
    fixed_utc:
        ISO-8601 UTC timestamp to return from :meth:`now_utc`.
    fixed_run_id:
        Run-ID string to return from :meth:`new_run_id`.
    """

    def __init__(
        self,
        fixed_utc: str = "2026-01-01T00:00:00Z",
        fixed_run_id: str = "fake-run-001",
    ) -> None:
        self._utc = fixed_utc
        self._run_id = fixed_run_id

    def now_utc(self) -> str:
        return self._utc

    def new_run_id(self) -> str:
        return self._run_id
