"""OutputPort — abstract interface for writing pipeline artefacts.

Application layer uses this port to persist the four stable artefacts of a
run without knowing the underlying storage mechanism.  No filesystem paths
appear in the signatures; path resolution is the responsibility of the
concrete adapter (adapters/fs/output_fs).
"""

from __future__ import annotations

from typing import Any, Protocol


class OutputPort(Protocol):
    """Write-only access to a single run's output artefacts."""

    def init_run_folder(self, run_id: str, created_at_utc: str) -> None:
        """Prepare the output destination for a new run.

        Must be called once before any ``write_*`` method.

        *run_id*         — opaque identifier string (e.g. 12-hex chars).
        *created_at_utc* — ISO-8601 UTC timestamp string
                           (e.g. ``"2024-06-01T12:00:00Z"``).

        For a filesystem adapter this creates the run folder and any required
        sub-directories; other adapters may perform equivalent initialisation.
        """
        ...

    def write_sv(self, bundle: dict[str, Any]) -> None:
        """Persist the SVBundle artefact (``sv.json``).

        *bundle* is the fully-built SV dict produced by the mapping stage.
        The adapter is responsible for serialisation and deterministic key
        ordering.
        """
        ...

    def write_ml(self, rows: list[dict[str, Any]]) -> None:
        """Persist the ML projection artefact (``projections/ml_v1.csv``).

        *rows* is the ordered list of ML projection row dicts produced by
        the C-02 projection stage.
        """
        ...

    def write_llm(self, context: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Persist the LLM context artefact (``projections/llm_context_v1.json``).

        *context* is either a single context dict (single-account datasets)
        or a list of context dicts (multi-account datasets), as produced by
        the C-03 projection stage.
        """
        ...

    def write_report(self, report: dict[str, Any]) -> None:
        """Persist the collected run report artefact (``report.json``).

        *report* is the fully-built report dict produced by the report
        builder.  The adapter is responsible for serialisation and
        deterministic key ordering.
        """
        ...

    def write_ml_model(self, output: dict[str, Any], model_suffix: str) -> None:
        """Persist a model-specific ML projection artefact.

        Written to ``projections/ml_v1_{model_suffix}.json``.
        Only called when *target_models.ml* is configured in the profile.
        """
        ...

    def write_llm_model(self, output: list[dict[str, Any]], model_suffix: str) -> None:
        """Persist a model-specific LLM projection artefact.

        Written to ``projections/llm_context_v1_{model_suffix}.json``.
        Only called when *target_models.llm* is configured in the profile.
        """
        ...
