"""
Filesystem-wiring adapter for the pipeline.

Provides the old filesystem-based signature:
    run_pipeline(data_dir, output_dir, run_id=None, created_at_utc=None) -> dict

This wrapper:
1. Constructs the four port adapters (FsDatasetAdapter, FsOutputAdapter,
   FsSpecAdapter, SystemClock / FixedClock).
2. Computes dataset_id and input_dir from data_dir for the run report.
3. Delegates to application.pipeline.run_pipeline (port-based).
4. Appends run_folder to the returned summary so callers are unaffected.

Old import paths (run_adapter.py, QA scripts, tests) use ``adapter.pipeline``;
this module keeps those imports working without change.
"""

from __future__ import annotations

from pathlib import Path

from adapters.fs.clock_impl import FixedClock, SystemClock
from adapters.fs.dataset_fs import FsDatasetAdapter
from adapters.fs.output_fs import FsOutputAdapter
from adapters.fs.spec_fs import FsSpecAdapter
from application.pipeline import run_pipeline as _port_run_pipeline

# Repository root: backend/adapter/pipeline.py -> backend/adapter -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]


def run_pipeline(
    data_dir: str | Path,
    output_dir: str | Path,
    run_id: str | None = None,
    created_at_utc: str | None = None,
) -> dict:
    """
    Run the full adapter pipeline with filesystem adapters.

    Backwards-compatible wrapper around ``application.pipeline.run_pipeline``.
    Accepts filesystem paths, wires up the four port adapters, then delegates
    to the port-based orchestrator.

    Parameters
    ----------
    data_dir:        Path to the dataset directory (must contain accounts.json).
    output_dir:      Base directory for output; a per-run sub-folder is created.
    run_id:          Optional fixed run ID (for deterministic / test runs).
    created_at_utc:  Optional fixed UTC timestamp (for deterministic / test runs).

    Returns
    -------
    Summary dict with outcome, run_id, run_folder, counts, flags, issues,
    dropped_details.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

    # Build adapters
    dataset = FsDatasetAdapter(data_dir)
    out = FsOutputAdapter(output_dir)
    spec = FsSpecAdapter(_REPO_ROOT / "spec")

    # Clock: use FixedClock when caller supplies deterministic values
    if run_id is not None or created_at_utc is not None:
        _sys = SystemClock()
        _run_id = run_id if run_id is not None else _sys.new_run_id()
        _ts = created_at_utc if created_at_utc is not None else _sys.now_utc()
        clock = FixedClock(fixed_utc=_ts, fixed_run_id=_run_id)
    else:
        clock = SystemClock()

    # Compute filesystem-specific report fields
    _dataset_id = data_dir.name
    try:
        _input_dir = str(data_dir.resolve().relative_to(_REPO_ROOT).as_posix())
    except ValueError:
        _input_dir = str(data_dir.resolve().as_posix())

    # Delegate to the port-based orchestrator
    summary = _port_run_pipeline(
        dataset=dataset,
        out=out,
        spec=spec,
        clock=clock,
        dataset_id=_dataset_id,
        input_dir=_input_dir,
    )

    # Append run_folder so existing callers (CLI, tests, QA) are unaffected
    summary["run_folder"] = str(out.run_folder)
    return summary


__all__ = ["run_pipeline"]
