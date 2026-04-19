"""Shared helpers for the C-04 model formatters submodule.

Private to ``domain.projections.model_formatters`` — do not import from
other domain packages.  Keeps per-formatter modules free of duplicated
serialisation helpers.
"""
from __future__ import annotations

import json


# Chat-template control tokens that must never appear inside an untrusted
# preamble — otherwise an attacker could close the system turn and inject
# their own user/assistant messages into the downstream model's context.
# Keep one entry per supported LLM family; ``format_<family>`` calls
# ``_strip_chat_control_tokens(preamble, "<family>")`` before interpolation.
_CONTROL_TOKENS: dict[str, tuple[str, ...]] = {
    "llama3": (
        "<|begin_of_text|>",
        "<|end_of_text|>",
        "<|eot_id|>",
        "<|start_header_id|>",
        "<|end_header_id|>",
    ),
    "mistral": ("<s>", "</s>", "[INST]", "[/INST]"),
    "chatml": ("<|im_start|>", "<|im_end|>", "<|endoftext|>"),
    "gemma": ("<start_of_turn>", "<end_of_turn>"),
}


def context_to_json(ctx: dict) -> str:
    """Serialise a single LLM context dict to compact JSON.

    Compact (no whitespace) is intentional: these strings are embedded
    inside chat-template prompts where extra whitespace wastes tokens.
    """
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":"))


def strip_chat_control_tokens(text: str, family: str) -> str:
    """Remove model-family-specific chat control tokens from *text*.

    The preamble is sourced from the profile or the HTTP API, both of which
    can be untrusted in a multi-tenant setup. Stripping the control tokens
    here keeps the chat structure under our control.
    """
    if not text:
        return text
    out = text
    for token in _CONTROL_TOKENS.get(family, ()):
        out = out.replace(token, "")
    return out
