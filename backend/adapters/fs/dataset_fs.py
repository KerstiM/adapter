"""FsDatasetAdapter — filesystem implementation of DatasetPort.

Reads Berlin AIS input files from a single dataset directory:
  - ``accounts.json``          (required)
  - ``transactions.json``      (required, or ``transactions_*.json`` for multi-report)
  - ``transactions_*.json``    (multi-report, sorted lexicographically)
  - ``transactions_download.json`` (included in listing; caller decides handling)
  - ``standing_orders.json``   (optional)

The list of transaction reports is always in deterministic (sorted) order so
that identical datasets always produce the same run output.

Usage::

    from adapters.fs.dataset_fs import FsDatasetAdapter
    ds = FsDatasetAdapter(data_dir=Path("datasets/D1_public_valid_small"))
    accounts = ds.read_accounts()
    for name in ds.list_transaction_reports():
        report = ds.read_transactions_report(name)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FsDatasetAdapter:
    """Filesystem adapter for :class:`ports.dataset_port.DatasetPort`.

    Parameters
    ----------
    data_dir:
        Path to the dataset directory that contains ``accounts.json`` and one
        or more ``transactions*.json`` files.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir).resolve()

    # ------------------------------------------------------------------
    # DatasetPort interface
    # ------------------------------------------------------------------

    def read_accounts(self) -> dict[str, Any]:
        """Return the parsed accounts payload (Berlin AIS ``accounts.json``).

        Raises ``FileNotFoundError`` when the file does not exist.
        """
        path = self._data_dir / "accounts.json"
        return self._load_json(path)

    def list_transaction_reports(self) -> list[str]:
        """Return a deterministically-ordered list of transaction-report names.

        Matches all files whose names match ``transactions*.json`` inside the
        dataset directory, **including** ``transactions_download.json`` (the
        caller decides how to handle download-only payloads).

        The list is sorted lexicographically so that multi-report datasets
        (``transactions_1.json``, ``transactions_2.json``, …) are always
        processed in the same order.
        """
        return sorted(p.name for p in self._data_dir.glob("transactions*.json"))

    def read_transactions_report(self, name: str) -> dict[str, Any]:
        """Return the parsed payload for *name* (one of :meth:`list_transaction_reports`).

        Raises ``FileNotFoundError`` when the file does not exist.
        Raises ``json.JSONDecodeError`` when the file is not valid JSON.
        """
        path = self._data_dir / name
        return self._load_json(path)

    def read_standing_orders_optional(self) -> dict[str, Any] | None:
        """Return the parsed standing-orders payload, or ``None`` if absent."""
        path = self._data_dir / "standing_orders.json"
        if not path.exists():
            return None
        return self._load_json(path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
