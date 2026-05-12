"""Named JSON serialisation helpers, one per use case.

Three formats exist in this codebase by design — each with a different
purpose.  Using anonymous ``json.dumps(...)`` calls at each site invites
silent regressions: e.g. accidentally using the compact form for a
golden artefact would change every SHA-256 hash.  Naming the formats
makes the intent (and the cost of mixing them) explicit.
"""
from __future__ import annotations

import json
from typing import Any


def stable_json(obj: Any) -> str:
    """Deterministic JSON for golden artefacts (sorted keys, 2-space indent).

    The exact byte output is part of the determinism contract validated
    by SLI-4 and `frozen/v*/manifest.json` SHA-256 hashes.  Do not change
    the flags here without rebuilding goldens.
    """
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def api_json(obj: Any) -> str:
    """JSON for HTTP API responses — readable, UTF-8 preserved.

    Not sorted: response order mirrors the dict the handler builds, which
    is more useful for humans inspecting the response than alphabetical
    keys.  Not part of the golden contract.
    """
    return json.dumps(obj, ensure_ascii=False)


def compact_json(obj: Any) -> str:
    """Compact JSON for embedding inside LLM chat-template prompts.

    Whitespace costs tokens at inference time, so projections that are
    serialised into prompts use the most compact form possible.
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
