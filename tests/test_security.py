"""Tests for URL safety checks."""

from __future__ import annotations

import pytest

from exifsniffer.security import assert_url_safe_for_fetch


def test_blocks_localhost() -> None:
    with pytest.raises(ValueError, match="not allowed|forbidden"):
        assert_url_safe_for_fetch(
            "http://localhost/foo.jpg",
            allow_private_hosts=False,
            allowed_suffixes=None,
            blocked_suffixes=None,
        )


def test_allows_public_https() -> None:
    assert_url_safe_for_fetch(
        "https://example.com/image.jpg",
        allow_private_hosts=False,
        allowed_suffixes=None,
        blocked_suffixes=None,
    )
