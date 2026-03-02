"""In-memory fake of DatasetPort — no filesystem access."""

from __future__ import annotations

from typing import Any


class FakeDatasetPort:
    """Implements :class:`ports.dataset_port.DatasetPort` using plain dicts.

    Pass pre-built payloads at construction time; the fake simply returns them.

    Parameters
    ----------
    accounts:
        The accounts payload (same shape as ``accounts.json``).
    transaction_reports:
        Ordered mapping of report filename -> parsed payload.
        Example: ``{"transactions.json": {...}}``
    standing_orders:
        Optional standing-orders payload, or ``None``.
    """

    def __init__(
        self,
        accounts: dict[str, Any],
        transaction_reports: dict[str, dict[str, Any]] | None = None,
        standing_orders: dict[str, Any] | None = None,
    ) -> None:
        self._accounts = accounts
        self._transaction_reports = transaction_reports or {}
        self._standing_orders = standing_orders

    def read_accounts(self) -> dict[str, Any]:
        return self._accounts

    def list_transaction_reports(self) -> list[str]:
        return sorted(self._transaction_reports.keys())

    def read_transactions_report(self, name: str) -> dict[str, Any]:
        if name not in self._transaction_reports:
            raise KeyError(f"Transaction report {name!r} not found in fake")
        return self._transaction_reports[name]

    def read_standing_orders_optional(self) -> dict[str, Any] | None:
        return self._standing_orders
