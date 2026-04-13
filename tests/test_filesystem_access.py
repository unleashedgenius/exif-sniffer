"""Tests for LM Studio filesystem-access-style tools."""

from __future__ import annotations

import pytest

from exifsniffer.filesystem_access import (
    fs_create_directory,
    fs_list_files,
    fs_read_file,
    fs_write_file,
    validate_relative_name,
)


def test_list_files_errors_when_base_unset() -> None:
    rows = fs_list_files(None)
    assert any(r.get("path") == "list_files.error" for r in rows)


def test_list_files_empty_dir(tmp_path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    rows = fs_list_files(base)
    assert rows == [{"path": "list_files.message", "value": "Directory is empty"}]


def test_write_read_roundtrip(tmp_path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    w = fs_write_file(base, "notes/hello.txt", "alpha")
    assert w == [{"path": "write_file.message", "value": "File created or updated successfully"}]
    r = fs_read_file(base, "notes/hello.txt")
    assert r == [{"path": "read_file.content", "value": "alpha"}]


def test_list_files_top_level_only(tmp_path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    (base / "a.txt").touch()
    (base / "sub").mkdir()
    (base / "sub" / "inner.txt").touch()
    rows = fs_list_files(base)
    names = {r["value"] for r in rows if r["path"].startswith("list_files.entries")}
    assert names == {"a.txt", "sub"}


def test_validate_rejects_parent_segments() -> None:
    with pytest.raises(ValueError, match="parent"):
        validate_relative_name("a/../b", label="file_name")


def test_read_rejects_escape(tmp_path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    rows = fs_read_file(base, "../outside")
    assert rows and rows[0].get("path") == "read_file.error"


def test_create_directory(tmp_path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    rows = fs_create_directory(base, "new/nested")
    assert "created successfully" in rows[0]["value"]
    assert (base / "new" / "nested").is_dir()
