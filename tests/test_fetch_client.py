"""Regression: httpx AsyncClient must support http2=True (requires h2 dependency)."""

from __future__ import annotations

import asyncio

import httpx


def test_async_client_http2_constructible() -> None:
    async def _open() -> None:
        async with httpx.AsyncClient(http2=True):
            pass

    asyncio.run(_open())
