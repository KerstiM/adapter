"""
C-04: Model-specific formatters — dispatcher.

Routes base projection output to the correct model formatter.
No I/O, no pathlib/os imports.
"""
from __future__ import annotations

from typing import Any

from domain.projections.model_formatters.llm_gemma import format_gemma as _format_gemma
from domain.projections.model_formatters.llm_templates import (
    format_chatml as _format_chatml,
    format_llama3 as _format_llama3,
    format_mistral as _format_mistral,
)
from domain.projections.model_formatters.ml_encoders import (
    format_catboost as _format_catboost,
    format_xgboost as _format_xgboost,
)

_LLM_FAMILY_DISPATCH: dict[str, Any] = {
    "llama3": _format_llama3,
    "mistral": _format_mistral,
    "chatml": _format_chatml,
    "gemma": _format_gemma,
}

_ML_ENCODING_DISPATCH: dict[str, Any] = {
    "label": _format_xgboost,
    "native": _format_catboost,
}


def format_for_model(
    base_output: list[dict] | dict,
    sv_bundle: dict,
    model_id: str,
    model_config: dict,
    projection_type: str,
    *,
    preamble: str = "",
) -> dict:
    """Dispatch to the appropriate model formatter.

    Parameters
    ----------
    base_output : list[dict] | dict
        Output from the base projection (C-02 ML rows or C-03 LLM contexts).
    sv_bundle : dict
        The full SV bundle for additional data access if needed.
    model_id : str
        Model identifier (e.g. ``"llama3.1-8b-instruct"``).
    model_config : dict
        Model configuration from the C-04 contract.
    projection_type : str
        ``"llm"`` or ``"ml"``.
    preamble : str
        System preamble for LLM formatters (from profile).

    Returns
    -------
    dict
        Formatted output with model-specific structure + metadata.
    """
    if projection_type == "llm":
        family = model_config.get("family", "")
        formatter = _LLM_FAMILY_DISPATCH.get(family)
        if formatter is None:
            raise ValueError(f"Unknown LLM family: {family!r} for model {model_id!r}")
        return formatter(base_output, sv_bundle, model_config, preamble=preamble)

    if projection_type == "ml":
        encoding = model_config.get("encoding", "")
        formatter = _ML_ENCODING_DISPATCH.get(encoding)
        if formatter is None:
            raise ValueError(f"Unknown ML encoding: {encoding!r} for model {model_id!r}")
        return formatter(base_output, sv_bundle, model_config)

    raise ValueError(f"Unknown projection_type: {projection_type!r}")
