"""Path-traversal containment for FsSpecAdapter._resolve_path.

A profile YAML lives inside ``spec/profiles/`` and lists relative paths to
schemas / contracts / rulesets. Those paths must stay inside the repository
root — otherwise a malicious or buggy profile could read arbitrary files
on disk (e.g. ``../../../etc/passwd``).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from adapters.fs.spec_fs import FsSpecAdapter


@pytest.fixture()
def adapter(tmp_path: Path) -> FsSpecAdapter:
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    # FsSpecAdapter treats spec_dir.parent as the repo root.
    return FsSpecAdapter(spec_dir=spec_dir)


def test_rejects_parent_traversal(adapter: FsSpecAdapter) -> None:
    with pytest.raises(ValueError, match="escapes repository root"):
        adapter._resolve_path("../../../etc/passwd")


def test_rejects_absolute_escape(tmp_path: Path, adapter: FsSpecAdapter) -> None:
    # An absolute path under tmp_path/.. is also outside the repo root.
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(ValueError, match="escapes repository root"):
        adapter._resolve_path(str(outside))


def test_allows_path_inside_repo(tmp_path: Path, adapter: FsSpecAdapter) -> None:
    inside = tmp_path / "inside.json"
    inside.write_text("{}")
    # FsSpecAdapter's repo root is tmp_path (spec_dir.parent).
    resolved = adapter._resolve_path("inside.json")
    assert resolved == inside.resolve()


def test_missing_file_raises_filenotfound(adapter: FsSpecAdapter) -> None:
    with pytest.raises(FileNotFoundError):
        adapter._resolve_path("does_not_exist.json")
