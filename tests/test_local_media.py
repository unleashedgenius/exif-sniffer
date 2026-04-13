"""Tests for LOCAL_MEDIA_ROOT listing and settings."""

from __future__ import annotations

import pytest

from exifsniffer.local_media import list_image_relative_paths, require_local_media_root
from exifsniffer.paths import resolve_under_root
from exifsniffer.settings import load_settings


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


def test_require_local_media_root_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCAL_MEDIA_ROOT", raising=False)
    settings = load_settings()
    with pytest.raises(ValueError, match="LOCAL_MEDIA_ROOT"):
        require_local_media_root(settings)


def test_require_local_media_root_ok(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    monkeypatch.setenv("LOCAL_MEDIA_ROOT", str(root))
    settings = load_settings()
    assert require_local_media_root(settings) == root.resolve()
