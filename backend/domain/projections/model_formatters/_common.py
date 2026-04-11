"""Shared helpers for the C-04 model formatters submodule.

Private to ``domain.projections.model_formatters`` — do not import from
other domain packages.  Keeps per-formatter modules free of duplicated
serialisation helpers.
"""
from __future__ import annotations

import json


def context_to_json(ctx: dict) -> str:
    """Serialise a single LLM context dict to compact JSON.

    Compact (no whitespace) is intentional: these strings are embedded
    inside chat-template prompts where extra whitespace wastes tokens.
    """
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":"))
