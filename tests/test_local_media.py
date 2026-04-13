"""Tests for local media root parsing and listing."""

from __future__ import annotations

import pytest

from exifsniffer.local_media import list_image_relative_paths, parse_local_media_root
from exifsniffer.paths import resolve_under_root


def test_list_images_non_recursive(tmp_path) -> None:
    root = tmp_path / "scope"
    root.mkdir()
    (root / "a.jpg").touch()
    (root / "b.txt").touch()
    (root / "sub").mkdir()
    (root / "sub" / "c.jpg").touch()
    found = list_image_relative_paths(root, "", recursive=False, max_files=50)
    assert sorted(found) == ["a.jpg"]


def test_list_images_recursive(tmp_path) -> None:
    root = tmp_path / "scope"
    root.mkdir()
    (root / "a.jpg").touch()
    (root / "d").mkdir()
    (root / "d" / "b.png").touch()
    found = list_image_relative_paths(root, "", recursive=True, max_files=50)
    assert sorted(found) == ["a.jpg", "d/b.png"]


def test_list_respects_max_files(tmp_path) -> None:
    root = tmp_path / "scope"
    root.mkdir()
    for i in range(5):
        (root / f"f{i}.jpg").touch()
    found = list_image_relative_paths(root, "", recursive=False, max_files=3)
    assert len(found) == 3


def test_resolve_rejects_escape(tmp_path) -> None:
    root = tmp_path / "scope"
    root.mkdir()
    with pytest.raises(ValueError, match="Path escapes"):
        resolve_under_root(root, "../outside")


def test_parse_local_media_root_requires_absolute() -> None:
    with pytest.raises(ValueError, match="absolute"):
        parse_local_media_root("photos/library")


def test_parse_local_media_root_ok(tmp_path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    assert parse_local_media_root(str(root)) == root.resolve()


def test_parse_local_media_root_rejects_missing(tmp_path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="does not exist"):
        parse_local_media_root(str(missing))


def test_parse_local_media_root_rejects_file(tmp_path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory"):
        parse_local_media_root(str(f))
