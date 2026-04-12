"""FsOutputAdapter — filesystem implementation of OutputPort.

Writes the four stable pipeline artefacts to a per-run folder under a
configurable base output directory:

    <output_dir>/<ts>_<run_id>/
        sv.json
        report.json
        projections/
            ml_v1.csv
            llm_context_v1.json

All JSON files are serialised with ``json.dumps(sort_keys=True, indent=2,
ensure_ascii=False)`` (identical to the existing pipeline's ``_stable_json``)
and terminated with a trailing newline so that golden SHA-256 hashes remain
unchanged.

Usage::

    from adapters.fs.output_fs import FsOutputAdapter
    out = FsOutputAdapter(output_dir=Path("out"))
    out.init_run_folder(run_id="abc123", created_at_utc="2024-06-01T12:00:00Z")
    out.write_sv(sv_bundle)
    out.write_ml(ml_rows)
    out.write_llm(llm_context)
    out.write_report(report)
    print(out.run_folder)   # Path to the created run folder
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# CSV column order — must match the existing pipeline exactly so that golden
# SHA-256 hashes are unchanged.
# ---------------------------------------------------------------------------
_ML_FIELDNAMES: list[str] = [
    "row_id",
    "account_id",
    "record_id",
    "status",
    "booking_date",
    "value_date",
    "direction",
    "currency",
    "signed_amount",
    "abs_amount",
    "counterparty_name",
    "remittance",
]


def _stable_json(obj: Any) -> str:
    """Deterministic JSON serialisation — identical to ``application.pipeline._stable_json``."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def _ts_prefix(created_at_utc: str) -> str:
    """Derive a filesystem-safe timestamp prefix from an ISO-8601 UTC string.

    Replicates ``application.pipeline._ts_prefix`` exactly so that run-folder
    names produced by this adapter are identical to those produced by the
    existing pipeline.

    Example::

        _ts_prefix("2000-01-01T00:00:00Z") == "20000101T000000Z"
    """
    return (
        created_at_utc
        .replace("-", "")
        .replace(":", "")
        .replace("T", "T")   # no-op; preserved for parity with original
        .split(".")[0]
    )


class FsOutputAdapter:
    """Filesystem adapter for :class:`ports.output_port.OutputPort`.

    Parameters
    ----------
    output_dir:
        Base directory under which per-run folders are created.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir).resolve()
        self._run_folder: Path | None = None
        self._proj_folder: Path | None = None

    # ------------------------------------------------------------------
    # OutputPort interface
    # ------------------------------------------------------------------

    def init_run_folder(self, run_id: str, created_at_utc: str) -> None:
        """Create the run folder ``<output_dir>/<ts>_<run_id>/projections/``.

        Must be called once before any ``write_*`` method.
        """
        ts = _ts_prefix(created_at_utc)
        self._run_folder = self._output_dir / f"{ts}_{run_id}"
        self._run_folder.mkdir(parents=True, exist_ok=True)
        self._proj_folder = self._run_folder / "projections"
        self._proj_folder.mkdir(exist_ok=True)

    def write_sv(self, bundle: dict[str, Any]) -> None:
        """Write *bundle* to ``sv.json`` (stable JSON, trailing newline)."""
        self._require_init()
        path = self._run_folder / "sv.json"  # type: ignore[operator]
        with open(path, "w", encoding="utf-8") as f:
            f.write(_stable_json(bundle))
            f.write("\n")

    def write_ml(self, rows: list[dict[str, Any]]) -> None:
        """Write *rows* to ``projections/ml_v1.csv`` (DictWriter, fixed column order)."""
        self._require_init()
        path = self._proj_folder / "ml_v1.csv"  # type: ignore[operator]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_ML_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

    def write_llm(self, context: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Write *context* to ``projections/llm_context_v1.json`` (stable JSON, trailing newline)."""
        self._require_init()
        path = self._proj_folder / "llm_context_v1.json"  # type: ignore[operator]
        with open(path, "w", encoding="utf-8") as f:
            f.write(_stable_json(context))
            f.write("\n")

    def write_report(self, report: dict[str, Any]) -> None:
        """Write *report* to ``report.json`` (stable JSON, trailing newline)."""
        self._require_init()
        path = self._run_folder / "report.json"  # type: ignore[operator]
        with open(path, "w", encoding="utf-8") as f:
            f.write(_stable_json(report))
            f.write("\n")

    def write_ml_model(self, output: dict[str, Any], model_suffix: str) -> None:
        """Write model-specific ML projection to ``projections/ml_v1_{suffix}.json``."""
        self._require_init()
        path = self._proj_folder / f"ml_v1_{model_suffix}.json"  # type: ignore[operator]
        with open(path, "w", encoding="utf-8") as f:
            f.write(_stable_json(output))
            f.write("\n")

    def write_llm_model(self, output: list[dict[str, Any]], model_suffix: str) -> None:
        """Write model-specific LLM projection to ``projections/llm_context_v1_{suffix}.json``."""
        self._require_init()
        path = self._proj_folder / f"llm_context_v1_{model_suffix}.json"  # type: ignore[operator]
        with open(path, "w", encoding="utf-8") as f:
            f.write(_stable_json(output))
            f.write("\n")

    def write_extra_projection(self, data: list[dict[str, Any]], filename: str) -> None:
        """Write extra projection to ``projections/<filename>`` (stable JSON, trailing newline)."""
        self._require_init()
        path = self._proj_folder / filename  # type: ignore[operator]
        with open(path, "w", encoding="utf-8") as f:
            f.write(_stable_json(data))
            f.write("\n")

    # ------------------------------------------------------------------
    # Extra helpers (not part of the port but useful for callers)
    # ------------------------------------------------------------------

    @property
    def run_folder(self) -> Path | None:
        """The path of the current run folder, or ``None`` before :meth:`init_run_folder`."""
        return self._run_folder

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _require_init(self) -> None:
        if self._run_folder is None:
            raise RuntimeError(
                "init_run_folder() must be called before any write_* method."
            )
