"""
C-04 LLM formatters — wrap base LLM context in model-specific chat templates.

Pure functions, no I/O.  Each formatter receives:
  - llm_contexts: list[dict]  (output from C-03 project_llm)
  - sv_bundle: dict            (full SV bundle for additional data if needed)
  - config: dict               (model config from C-04 contract)
  - preamble: str              (system preamble from profile)

Returns a list of dicts, one per account, each containing the formatted prompt.
"""
from __future__ import annotations

import json


def _context_to_json(ctx: dict) -> str:
    """Serialize a single LLM context dict to compact JSON."""
    return json.dumps(ctx, ensure_ascii=False, separators=(",", ":"))


def format_llama3(
    llm_contexts: list[dict],
    sv_bundle: dict,
    config: dict,
    *,
    preamble: str = "",
) -> list[dict]:
    """Format LLM contexts for Meta Llama 3.1 8B Instruct.

    Template::

        <|begin_of_text|><|start_header_id|>system<|end_header_id|>

        {preamble}<|eot_id|><|start_header_id|>user<|end_header_id|>

        {context_json}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

    """
    tokens = config.get("template_tokens", {})
    bos = tokens.get("bos", "<|begin_of_text|>")
    sys_start = tokens.get("system_start", "<|start_header_id|>system<|end_header_id|>\n\n")
    sys_end = tokens.get("system_end", "<|eot_id|>")
    usr_start = tokens.get("user_start", "<|start_header_id|>user<|end_header_id|>\n\n")
    usr_end = tokens.get("user_end", "<|eot_id|>")
    asst_start = tokens.get("assistant_start", "<|start_header_id|>assistant<|end_header_id|>\n\n")

    results = []
    for ctx in llm_contexts:
        ctx_json = _context_to_json(ctx)
        prompt = (
            f"{bos}{sys_start}{preamble}{sys_end}"
            f"{usr_start}{ctx_json}{usr_end}"
            f"{asst_start}"
        )
        results.append({
            "model_id": "llama3.1-8b-instruct",
            "account_id": ctx.get("meta", {}).get("account_id", ""),
            "prompt": prompt,
        })
    return results


def format_mistral(
    llm_contexts: list[dict],
    sv_bundle: dict,
    config: dict,
    *,
    preamble: str = "",
) -> list[dict]:
    """Format LLM contexts for Mistral 7B Instruct v0.3.

    Template::

        <s>[INST] {preamble}

        {context_json} [/INST]
    """
    tokens = config.get("template_tokens", {})
    bos = tokens.get("bos", "<s>")
    inst_start = tokens.get("inst_start", "[INST] ")
    inst_end = tokens.get("inst_end", " [/INST]")

    results = []
    for ctx in llm_contexts:
        ctx_json = _context_to_json(ctx)
        prompt = f"{bos}{inst_start}{preamble}\n\n{ctx_json}{inst_end}"
        results.append({
            "model_id": "mistral-7b-instruct-v0.3",
            "account_id": ctx.get("meta", {}).get("account_id", ""),
            "prompt": prompt,
        })
    return results


def format_chatml(
    llm_contexts: list[dict],
    sv_bundle: dict,
    config: dict,
    *,
    preamble: str = "",
) -> list[dict]:
    """Format LLM contexts for Qwen2.5 7B Instruct (ChatML).

    Template::

        <|im_start|>system
        {preamble}<|im_end|>
        <|im_start|>user
        {context_json}<|im_end|>
        <|im_start|>assistant
    """
    tokens = config.get("template_tokens", {})
    im_start = tokens.get("im_start", "<|im_start|>")
    im_end = tokens.get("im_end", "<|im_end|>")

    results = []
    for ctx in llm_contexts:
        ctx_json = _context_to_json(ctx)
        prompt = (
            f"{im_start}system\n{preamble}{im_end}\n"
            f"{im_start}user\n{ctx_json}{im_end}\n"
            f"{im_start}assistant\n"
        )
        results.append({
            "model_id": "qwen2.5-7b-instruct",
            "account_id": ctx.get("meta", {}).get("account_id", ""),
            "prompt": prompt,
        })
    return results
