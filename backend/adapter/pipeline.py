"""
Backwards-compatibility shim.

Canonical location: backend/application/pipeline.py

Old import paths (run_adapter.py, QA scripts) use ``adapter.pipeline``; this
module re-exports everything so those imports continue to work unchanged.
"""
from application.pipeline import run_pipeline  # noqa: F401

__all__ = ["run_pipeline"]
