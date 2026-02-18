"""ClockPort — abstract interface for time and run-ID generation.

Injecting this port instead of calling ``datetime.now()`` or ``uuid.uuid4()``
directly makes the pipeline fully deterministic in tests: a fake clock can
return a fixed timestamp and a fixed run ID, guaranteeing identical output
hashes across runs.
"""

from __future__ import annotations

from typing import Protocol


class ClockPort(Protocol):
    """Source of wall-clock time and unique run identifiers."""

    def now_utc(self) -> str:
        """Return the current UTC time as an ISO-8601 string.

        Format: ``"YYYY-MM-DDTHH:MM:SSZ"`` (seconds precision, Z suffix).

        Example: ``"2024-06-01T12:00:00Z"``
        """
        ...

    def new_run_id(self) -> str:
        """Return a new, unique run identifier string.

        The identifier MUST be URL-safe and filesystem-safe (alphanumeric
        characters only are recommended).  Length and entropy are left to
        the concrete implementation; the default adapter uses the first
        12 hex characters of a random UUID4.

        Example: ``"3f8a1c2b9d04"``
        """
        ...
