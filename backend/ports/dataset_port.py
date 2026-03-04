"""DatasetPort — abstract interface for reading raw input data.

Application layer uses this port to obtain Berlin AIS input data without
knowing where (or how) it is stored.  No filesystem paths appear in the
signatures; path resolution is the responsibility of the concrete adapter
(adapters/fs/dataset_fs).
"""

from __future__ import annotations

from typing import Any, Protocol


class DatasetPort(Protocol):
    """Read-only access to a single dataset's raw input files."""

    def read_accounts(self) -> dict[str, Any]:
        """Return the parsed accounts payload (Berlin AIS accounts.json).

        Typical top-level key: ``"accounts"`` (list of account objects).

        Raises an error when the accounts file is missing or unreadable.
        """
        ...

    def list_transaction_reports(self) -> list[str]:
        """Return an ordered list of transaction-report names available in
        this dataset (e.g. ``["transactions.json", "transactions_2.json"]``).

        The list MUST be deterministically ordered (e.g. lexicographic) so
        that identical datasets always produce the same run output.

        Download-only variants (e.g. ``transactions_download.json``) SHOULD
        be included so the caller can inspect them; the caller decides how to
        handle them.
        """
        ...

    def read_transactions_report(self, name: str) -> dict[str, Any]:
        """Return the parsed payload for a single transaction-report file.

        *name* is one of the values returned by :meth:`list_transaction_reports`.

        Raises an error when the file does not exist or cannot be parsed.
        """
        ...

    def read_standing_orders_optional(self) -> dict[str, Any] | None:
        """Return the parsed standing-orders payload, or ``None`` if absent.

        Returns ``None`` rather than raising when the file is not present in
        the dataset, because standing orders are optional input.
        """
        ...
