"""Unit tests for the shared severity-counting kernel and the two public
counters that delegate to it.
"""
from __future__ import annotations

from domain.report.ops import (
    _count_severities,
    count_flags_by_severity,
    count_issues_by_severity,
)


_ZERO = {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0}


# ---------------------------------------------------------------------------
# _count_severities — shared kernel
# ---------------------------------------------------------------------------

def test_count_severities_empty_iterable_returns_zeros():
    assert _count_severities([]) == _ZERO


def test_count_severities_counts_each_known_level():
    items = [
        {"severity": "CRITICAL"},
        {"severity": "ERROR"},
        {"severity": "ERROR"},
        {"severity": "WARN"},
        {"severity": "INFO"},
        {"severity": "INFO"},
        {"severity": "INFO"},
    ]
    assert _count_severities(items) == {
        "CRITICAL": 1, "ERROR": 2, "WARN": 1, "INFO": 3,
    }


def test_count_severities_silently_ignores_unknown_level():
    items = [
        {"severity": "DEBUG"},
        {"severity": "ERROR"},
        {"severity": "TRACE"},
    ]
    assert _count_severities(items) == {**_ZERO, "ERROR": 1}


def test_count_severities_ignores_missing_severity_key():
    items = [{}, {"severity": "ERROR"}, {"other": "field"}]
    assert _count_severities(items) == {**_ZERO, "ERROR": 1}


def test_count_severities_accepts_generator():
    gen = ({"severity": "INFO"} for _ in range(3))
    assert _count_severities(gen) == {**_ZERO, "INFO": 3}


# ---------------------------------------------------------------------------
# count_flags_by_severity — wraps kernel over tx.flags[] from both lists
# ---------------------------------------------------------------------------

def test_count_flags_combines_valid_and_dropped():
    sv_transactions = [
        {"flags": [{"severity": "WARN"}, {"severity": "INFO"}]},
        {"flags": [{"severity": "WARN"}]},
    ]
    dropped = [
        {"flags": [{"severity": "ERROR"}]},
    ]
    assert count_flags_by_severity(sv_transactions, dropped) == {
        "CRITICAL": 0, "ERROR": 1, "WARN": 2, "INFO": 1,
    }


def test_count_flags_handles_transactions_without_flags_key():
    sv_transactions = [{}, {"flags": [{"severity": "WARN"}]}]
    assert count_flags_by_severity(sv_transactions, []) == {**_ZERO, "WARN": 1}


# ---------------------------------------------------------------------------
# count_issues_by_severity — wraps kernel over a flat issues[] list
# ---------------------------------------------------------------------------

def test_count_issues_over_flat_list():
    issues = [
        {"severity": "CRITICAL", "code": "X"},
        {"severity": "ERROR", "code": "Y"},
        {"severity": "ERROR", "code": "Z"},
    ]
    assert count_issues_by_severity(issues) == {
        "CRITICAL": 1, "ERROR": 2, "WARN": 0, "INFO": 0,
    }


def test_count_issues_empty_list_returns_zeros():
    assert count_issues_by_severity([]) == _ZERO
