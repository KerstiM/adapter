"""Unit tests for the shared dataset resolver used by both CLI and HTTP API."""
from __future__ import annotations

import pytest

from entrypoints._dataset_resolver import (
    AmbiguousDatasetError,
    resolve_dataset_by_name,
)


def _make_dataset(parent, name: str, *, with_accounts: bool = True) -> None:
    folder = parent / name
    folder.mkdir()
    if with_accounts:
        (folder / "accounts.json").write_text("{}")


def test_exact_name_match(tmp_path):
    _make_dataset(tmp_path, "D1_synth_valid_small")
    assert resolve_dataset_by_name("D1_synth_valid_small", [tmp_path]) == \
        tmp_path / "D1_synth_valid_small"


def test_prefix_match(tmp_path):
    _make_dataset(tmp_path, "D1_synth_valid_small")
    assert resolve_dataset_by_name("D1", [tmp_path]) == \
        tmp_path / "D1_synth_valid_small"


def test_case_insensitive(tmp_path):
    _make_dataset(tmp_path, "D1_synth_valid_small")
    assert resolve_dataset_by_name("d1", [tmp_path]) == \
        tmp_path / "D1_synth_valid_small"


def test_underscore_fence_prevents_d1_matching_d10(tmp_path):
    _make_dataset(tmp_path, "D10_real_deid")
    assert resolve_dataset_by_name("D1", [tmp_path]) is None


def test_ambiguous_match_raises(tmp_path):
    _make_dataset(tmp_path, "D1_one")
    _make_dataset(tmp_path, "D1_two")
    with pytest.raises(AmbiguousDatasetError) as exc:
        resolve_dataset_by_name("D1", [tmp_path])
    assert exc.value.matches == ["D1_one", "D1_two"]


def test_exact_match_wins_over_prefix_siblings(tmp_path):
    # A literal "D1" folder must resolve to itself even when "D1_*"
    # siblings exist — otherwise an exact dataset ID would be rejected
    # as ambiguous, which is a regression from the prior CLI/API logic.
    _make_dataset(tmp_path, "D1")
    _make_dataset(tmp_path, "D1_synth_valid_small")
    assert resolve_dataset_by_name("D1", [tmp_path]) == tmp_path / "D1"


def test_unknown_dataset_returns_none(tmp_path):
    _make_dataset(tmp_path, "D1_synth_valid_small")
    assert resolve_dataset_by_name("D99", [tmp_path]) is None


def test_folder_without_accounts_is_skipped(tmp_path):
    _make_dataset(tmp_path, "D1_no_accounts", with_accounts=False)
    assert resolve_dataset_by_name("D1", [tmp_path]) is None


def test_searches_multiple_dirs_in_order(tmp_path):
    primary = tmp_path / "primary"
    secondary = tmp_path / "secondary"
    primary.mkdir()
    secondary.mkdir()
    _make_dataset(secondary, "D2_in_secondary")
    assert resolve_dataset_by_name("D2", [primary, secondary]) == \
        secondary / "D2_in_secondary"


def test_missing_search_dir_is_silently_skipped(tmp_path):
    missing = tmp_path / "does_not_exist"
    _make_dataset(tmp_path, "D1_real")
    assert resolve_dataset_by_name("D1", [missing, tmp_path]) == \
        tmp_path / "D1_real"


def test_absolute_path_in_name_is_rejected(tmp_path):
    # A directory containing accounts.json outside any search_dir must
    # not be reachable by passing its absolute path as the dataset name.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "accounts.json").write_text("{}")
    search_dir = tmp_path / "datasets"
    search_dir.mkdir()
    assert resolve_dataset_by_name(str(outside), [search_dir]) is None


def test_dotdot_traversal_in_name_is_rejected(tmp_path):
    # ".." segments must not escape the search_dir sandbox even if a
    # sibling folder with accounts.json exists.
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    (sibling / "accounts.json").write_text("{}")
    search_dir = tmp_path / "datasets"
    search_dir.mkdir()
    assert resolve_dataset_by_name("../sibling", [search_dir]) is None


def test_backslash_in_name_is_rejected(tmp_path):
    # Windows-style separators must not be treated as a valid name.
    _make_dataset(tmp_path, "D1_real")
    assert resolve_dataset_by_name("..\\D1_real", [tmp_path]) is None


def test_empty_name_returns_none(tmp_path):
    _make_dataset(tmp_path, "D1_real")
    assert resolve_dataset_by_name("", [tmp_path]) is None
