"""Unit tests for the three named JSON serialisation formats.

Each format is intentionally different — see `domain/_shared/json_format.py`
for the rationale. These tests pin the byte-level output so accidental
changes (e.g. dropping sort_keys from stable_json) are caught immediately.
"""
from __future__ import annotations

from domain._shared.json_format import api_json, compact_json, stable_json


# ---------------------------------------------------------------------------
# stable_json — golden-determinism format
# ---------------------------------------------------------------------------

def test_stable_json_sorts_keys():
    out = stable_json({"b": 1, "a": 2})
    assert out.index('"a"') < out.index('"b"')


def test_stable_json_uses_two_space_indent():
    out = stable_json({"a": 1})
    assert out == '{\n  "a": 1\n}'


def test_stable_json_preserves_non_ascii():
    out = stable_json({"key": "õäü"})
    assert "õäü" in out
    assert "\\u" not in out


def test_stable_json_is_deterministic():
    obj = {"a": 1, "b": [3, 2, 1], "c": {"y": 2, "x": 1}}
    assert stable_json(obj) == stable_json(obj)


# ---------------------------------------------------------------------------
# api_json — HTTP API response format
# ---------------------------------------------------------------------------

def test_api_json_does_not_sort_keys():
    out = api_json({"b": 1, "a": 2})
    assert out.index('"b"') < out.index('"a"')


def test_api_json_has_no_indentation():
    out = api_json({"a": 1, "b": 2})
    assert "\n" not in out


def test_api_json_preserves_non_ascii():
    assert "õäü" in api_json({"key": "õäü"})


# ---------------------------------------------------------------------------
# compact_json — LLM prompt embedding format
# ---------------------------------------------------------------------------

def test_compact_json_has_no_whitespace():
    out = compact_json({"a": 1, "b": [2, 3]})
    assert " " not in out
    assert "\n" not in out


def test_compact_json_uses_minimal_separators():
    assert compact_json({"a": 1, "b": 2}) == '{"a":1,"b":2}'


def test_compact_json_preserves_non_ascii():
    assert "õäü" in compact_json({"key": "õäü"})


# ---------------------------------------------------------------------------
# Cross-format contract: same input, three different byte strings
# ---------------------------------------------------------------------------

def test_three_formats_produce_distinct_output():
    obj = {"b": 1, "a": 2}
    assert stable_json(obj) != api_json(obj)
    assert api_json(obj) != compact_json(obj)
    assert stable_json(obj) != compact_json(obj)
