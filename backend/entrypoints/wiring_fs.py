"""Filesystem wiring — driving adapter that binds fs adapters to ports.

Constructs the four concrete port implementations (dataset, output, spec,
clock) from filesystem paths and delegates to
``application.pipeline.run_pipeline``.

Usage::

    from entrypoints.wiring_fs import run_pipeline_fs

    summary = run_pipeline_fs(
        data_dir="datasets/D1_synth_valid_small",
        output_dir="out",
        spec_dir="spec",
    )
    print(summary["outcome"])          # SUCCESS | PARTIAL_SUCCESS | FAIL
    print(summary["run_folder"])       # filesystem path to the created run folder
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.fs.dataset_fs import FsDatasetAdapter
from adapters.fs.output_fs import FsOutputAdapter
from adapters.fs.spec_fs import FsSpecAdapter
from adapters.system.clock_real import RealClock
from adapters.testing.clock_fixed import FixedClock
from application.pipeline import run_pipeline as _app_run_pipeline


def run_pipeline_fs(
    data_dir: str | Path,
    output_dir: str | Path,
    spec_dir: str | Path,
    *,
    profile_id: str = "default",
    run_id: str | None = None,
    created_at_utc: str | None = None,
    target_models_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the adapter pipeline with filesystem-backed port adapters.

    Parameters
    ----------
    data_dir : str | Path
        Dataset directory (must contain ``accounts.json``).
    output_dir : str | Path
        Base output directory; a per-run sub-folder is created inside it.
    spec_dir : str | Path
        Path to the ``spec/`` directory containing profiles, schemas,
        contracts, and rulesets.
    profile_id : str, default ``"default"``
        Which run profile to load from *spec_dir*.
    run_id : str | None
        Fixed run ID for deterministic / test runs.  When ``None``,
        ``RealClock`` generates a random one.
    created_at_utc : str | None
        Fixed UTC timestamp for deterministic / test runs.  When ``None``,
        ``RealClock`` uses the current wall-clock time.

    Returns
    -------
    dict[str, Any]
        The application-layer summary dict **plus** a ``"run_folder"`` key
        pointing to the created output directory on disk.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)

    # --- Construct port adapters ---
    dataset = FsDatasetAdapter(data_dir)
    out = FsOutputAdapter(output_dir)
    spec = FsSpecAdapter(spec_dir)

    if run_id is not None or created_at_utc is not None:
        _sys = RealClock()
        clock = FixedClock(
            fixed_utc=created_at_utc if created_at_utc is not None else _sys.now_utc(),
            fixed_run_id=run_id if run_id is not None else _sys.new_run_id(),
        )
    else:
        clock = RealClock()

    # --- Derive report metadata from filesystem paths ---
    dataset_id = data_dir.name
    try:
        repo_root = Path(spec_dir).resolve().parent
        input_dir = str(data_dir.resolve().relative_to(repo_root).as_posix())
    except ValueError:
        input_dir = str(data_dir.resolve().as_posix())

    # --- Delegate to the port-based application pipeline ---
    summary = _app_run_pipeline(
        dataset=dataset,
        out=out,
        spec=spec,
        clock=clock,
        profile_id=profile_id,
        dataset_id=dataset_id,
        input_dir=input_dir,
        target_models_override=target_models_override,
    )

    # Expose run_folder for filesystem callers (CLI, tests, QA scripts).
    summary["run_folder"] = str(out.run_folder)
    return summary


__all__ = ["run_pipeline_fs"]
