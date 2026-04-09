"""
C-04 LLM formatter for Google Gemma 2 — UK3 evolution artifact.

This module is a UK3 evolution artifact: it demonstrates that a new LLM
formatter can be added as a standalone module following the same pattern
as existing formatters (llama3, mistral, chatml) without modifying the
pipeline, ports, or dispatcher logic.

In production, registering this formatter requires adding one import and
one dict entry to model_formatters/__init__.py.  The test suite verifies
the mechanism by temporarily registering this formatter in the dispatch
table.

Pure function, no I/O.
"""
from __future__ import annotations

import json


def _context_to_json(ctx: dict) -> str:
    """Serialize a single LLM context dict to compact JSON."""
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":"))


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
        ctx_json = _context_to_json(ctx)
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
