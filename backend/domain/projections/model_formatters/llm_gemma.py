"""
C-04 LLM formatter for Google Gemma 2.

Added as UK3 extensibility proof: demonstrates that a new LLM formatter
can be introduced as a standalone module following the same pattern as
existing formatters (llama3, mistral, chatml) without modifying the
pipeline, ports, or dispatcher logic.  Registered in the dispatch table
via one import + one dict entry in ``__init__.py``.

Pure function, no I/O.
"""
from __future__ import annotations

from domain.projections.model_formatters._common import context_to_json


def format_gemma(
    llm_contexts: list[dict],
    sv_bundle: dict,
    config: dict,
    *,
    preamble: str = "",
) -> list[dict]:
    """Format LLM contexts for Google Gemma 2 2B Instruct.

    Template::

        <start_of_turn>user
        {preamble}

        {context_json}<end_of_turn>
        <start_of_turn>model

    Gemma 2 uses a simple turn-based template without a dedicated system
    role.  The preamble is prepended to the user turn.
    """
    tokens = config.get("template_tokens", {})
    turn_start_user = tokens.get("turn_start_user", "<start_of_turn>user\n")
    turn_end = tokens.get("turn_end", "<end_of_turn>\n")
    turn_start_model = tokens.get("turn_start_model", "<start_of_turn>model\n")

    results = []
    for ctx in llm_contexts:
        ctx_json = context_to_json(ctx)
        prompt = (
            f"{turn_start_user}{preamble}\n\n{ctx_json}{turn_end}"
            f"{turn_start_model}"
        )
        results.append({
            "model_id": "gemma-2-2b-it",
            "account_id": ctx.get("meta", {}).get("account_id", ""),
            "prompt": prompt,
        })
    return results
