"""In-memory fake of OutputPort — captures written artefacts without I/O."""

from __future__ import annotations

from typing import Any


class FakeOutputPort:
    """Implements :class:`ports.output_port.OutputPort` by storing artefacts
    in plain Python attributes.

    After ``run_pipeline`` completes, inspect:

    * ``sv``      — the SV bundle dict (or ``None`` before write)
    * ``ml``      — list of ML row dicts
    * ``llm``     — LLM context dict or list
    * ``report``  — the collected run report dict
    * ``run_id``  — the run ID passed to :meth:`init_run_folder`
    * ``created_at_utc`` — the timestamp passed to :meth:`init_run_folder`
    """

    def __init__(self) -> None:
        self.run_id: str | None = None
        self.created_at_utc: str | None = None
        self.sv: dict[str, Any] | None = None
        self.ml: list[dict[str, Any]] | None = None
        self.llm: dict[str, Any] | list[dict[str, Any]] | None = None
        self.report: dict[str, Any] | None = None
        self.ml_models: dict[str, dict[str, Any]] = {}
        self.llm_models: dict[str, list[dict[str, Any]]] = {}

    def init_run_folder(self, run_id: str, created_at_utc: str) -> None:
        self.run_id = run_id
        self.created_at_utc = created_at_utc

    def write_sv(self, bundle: dict[str, Any]) -> None:
        self.sv = bundle

    def write_ml(self, rows: list[dict[str, Any]]) -> None:
        self.ml = rows

    def write_llm(self, context: dict[str, Any] | list[dict[str, Any]]) -> None:
        self.llm = context

    def write_report(self, report: dict[str, Any]) -> None:
        self.report = report

    def write_ml_model(self, output: dict[str, Any], model_suffix: str) -> None:
        self.ml_models[model_suffix] = output

    def write_llm_model(self, output: list[dict[str, Any]], model_suffix: str) -> None:
        self.llm_models[model_suffix] = output
