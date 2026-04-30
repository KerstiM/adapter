"""Unit tests for the LLM preview view builder + the api.py thin I/O wrapper."""
from __future__ import annotations

import json
from pathlib import Path

from entrypoints._llm_preview_view import build_llm_preview_view
from entrypoints.api import _read_llm_preview


# ---------------------------------------------------------------------------
# build_llm_preview_view — pure function, no I/O
# ---------------------------------------------------------------------------

def _ctx(tx: list[dict], *, iban: str = "EE001", currency: str = "EUR") -> dict:
    return {"meta": {"iban": iban, "currency": currency}, "tx": tx}


class TestBuildLlmPreviewView:
    def test_empty_tx_returns_none(self) -> None:
        assert build_llm_preview_view(_ctx(tx=[])) is None

    def test_missing_tx_key_returns_none(self) -> None:
        assert build_llm_preview_view({"meta": {}}) is None

    def test_income_expenses_netflow_and_period(self) -> None:
        view = build_llm_preview_view(_ctx(tx=[
            {"d": "2025-01-05", "a": 1000.0, "dir": "IN",  "r": "Salary January"},
            {"d": "2025-01-10", "a": -200.0, "dir": "OUT", "r": "Groceries Coop"},
            {"d": "2025-01-15", "a": -50.0,  "dir": "OUT", "r": "Cafe Latte"},
        ]))
        assert view is not None
        summary = view["accountSummary"]
        assert summary["totalIncome"] == 1000.0
        assert summary["totalExpenses"] == 250.0
        assert summary["netFlow"] == 750.0
        assert summary["periodStart"] == "2025-01-05"
        assert summary["periodEnd"] == "2025-01-15"

    def test_top_categories_sorted_by_abs_total(self) -> None:
        view = build_llm_preview_view(_ctx(tx=[
            {"d": "2025-01-01", "a": 10.0,   "dir": "IN",  "r": "Refund X"},
            {"d": "2025-01-02", "a": -500.0, "dir": "OUT", "r": "Rent April"},
            {"d": "2025-01-03", "a": -100.0, "dir": "OUT", "r": "Groceries"},
        ]))
        assert view is not None
        order = [c["category"] for c in view["topCategories"]]
        assert order == ["Rent", "Groceries", "Refund"]

    def test_whitespace_only_reason_falls_back_to_other(self) -> None:
        view = build_llm_preview_view(_ctx(tx=[
            {"d": "2025-01-01", "a": -10.0, "dir": "OUT", "r": "   "},
        ]))
        assert view is not None
        cats = view["topCategories"]
        assert [c["category"] for c in cats] == ["Other"]

    def test_narrative_includes_iban_currency_and_counts(self) -> None:
        view = build_llm_preview_view(_ctx(
            tx=[{"d": "2025-01-01", "a": 100.0, "dir": "IN", "r": "X"}],
            iban="EE123",
            currency="USD",
        ))
        assert view is not None
        assert "EE123" in view["narrative"]
        assert "USD" in view["narrative"]
        assert "1 transactions" in view["narrative"]


# ---------------------------------------------------------------------------
# _read_llm_preview — thin I/O wrapper around build_llm_preview_view
# ---------------------------------------------------------------------------

def _write_ctx(run_folder: Path, payload: object) -> None:
    proj = run_folder / "projections"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "llm_context_v1.json").write_text(json.dumps(payload))


class TestReadLlmPreview:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _read_llm_preview(tmp_path) is None

    def test_empty_list_returns_none(self, tmp_path: Path) -> None:
        _write_ctx(tmp_path, [])
        assert _read_llm_preview(tmp_path) is None

    def test_first_context_null_returns_none(self, tmp_path: Path) -> None:
        # Regression: pre-refactor code returned None when the first context
        # was None; the slimmed wrapper must keep that guard so a malformed
        # [null] payload does not propagate to build_llm_preview_view.
        _write_ctx(tmp_path, [None])
        assert _read_llm_preview(tmp_path) is None

    def test_default_omits_raw_contexts(self, tmp_path: Path) -> None:
        ctx = _ctx(tx=[{"d": "2025-01-01", "a": 10.0, "dir": "IN", "r": "X"}])
        _write_ctx(tmp_path, ctx)
        result = _read_llm_preview(tmp_path)
        assert result is not None
        assert result["rawContexts"] == []

    def test_include_raw_returns_original_context(self, tmp_path: Path) -> None:
        ctx = _ctx(tx=[{"d": "2025-01-01", "a": 10.0, "dir": "IN", "r": "X"}])
        _write_ctx(tmp_path, ctx)
        result = _read_llm_preview(tmp_path, include_raw=True)
        assert result is not None
        assert result["rawContexts"] == [ctx]

    def test_multi_account_summary_uses_first_context(self, tmp_path: Path) -> None:
        first = _ctx(
            tx=[{"d": "2025-01-01", "a": 100.0, "dir": "IN", "r": "X"}],
            iban="EE_FIRST",
        )
        second = _ctx(
            tx=[{"d": "2025-02-02", "a": 999.0, "dir": "IN", "r": "Y"}],
            iban="EE_SECOND",
        )
        _write_ctx(tmp_path, [first, second])
        result = _read_llm_preview(tmp_path, include_raw=True)
        assert result is not None
        assert "EE_FIRST" in result["narrative"]
        assert "EE_SECOND" not in result["narrative"]
        assert result["rawContexts"] == [first, second]
