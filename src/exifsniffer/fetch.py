"""Download remote media with redirect handling and size limits."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import httpx

from exifsniffer.security import assert_url_safe_for_fetch
from exifsniffer.settings import Settings


async def download_url_to_path(
    url: str,
    dest: Path,
    settings: Settings,
) -> dict[str, object]:
    assert_url_safe_for_fetch(
        url,
        allow_private_hosts=settings.allow_private_hosts,
        allowed_suffixes=settings.allowed_host_suffixes,
        blocked_suffixes=settings.blocked_host_suffixes,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)

    current = url
    redirects = 0
    timeout = httpx.Timeout(
        connect=settings.connect_timeout_seconds,
        read=settings.read_timeout_seconds,
        write=settings.read_timeout_seconds,
        pool=settings.connect_timeout_seconds,
    )

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, http2=True) as client:
        while True:
            assert_url_safe_for_fetch(
                current,
                allow_private_hosts=settings.allow_private_hosts,
                allowed_suffixes=settings.allowed_host_suffixes,
                blocked_suffixes=settings.blocked_host_suffixes,
            )
            async with client.stream("GET", current, headers={"User-Agent": "ExifSniffer-MCP/0.1"}) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    redirects += 1
                    if redirects > settings.max_redirects:
                        raise ValueError("Too many HTTP redirects")
                    loc = resp.headers.get("location")
                    if not loc:
                        raise ValueError("Redirect without Location header")
                    current = urljoin(str(resp.url), loc.strip())
                    continue

                resp.raise_for_status()
                total = 0
                with dest.open("wb") as fh:
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > settings.max_download_bytes:
                            dest.unlink(missing_ok=True)
                            raise ValueError(
                                f"Download exceeded MAX_DOWNLOAD_BYTES ({settings.max_download_bytes})"
                            )
                        fh.write(chunk)

                return {
                    "final_url": str(resp.url),
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("content-type"),
                    "bytes_written": total,
                    "redirects_followed": redirects,
                }
