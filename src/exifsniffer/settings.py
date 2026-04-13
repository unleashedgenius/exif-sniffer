"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    data_dir: str
    # Optional base for filesystem MCP tools (LM Studio plugin "Base Directory" equivalent).
    local_media_base: str | None
    max_download_bytes: int
    connect_timeout_seconds: float
    read_timeout_seconds: float
    max_redirects: int
    allow_private_hosts: bool
    allowed_host_suffixes: frozenset[str] | None
    blocked_host_suffixes: frozenset[str] | None


def load_settings() -> Settings:
    data_dir = os.environ.get("DATA_DIR", "/data")
    base = os.environ.get("LOCAL_MEDIA_BASE")
    base_norm = base.strip() if base else ""
    allowed = os.environ.get("FETCH_ALLOWED_HOST_SUFFIXES")
    blocked = os.environ.get("FETCH_BLOCKED_HOST_SUFFIXES")
    return Settings(
        data_dir=data_dir,
        local_media_base=base_norm if base_norm else None,
        max_download_bytes=_env_int("MAX_DOWNLOAD_BYTES", 100_000_000),
        connect_timeout_seconds=_env_float("FETCH_CONNECT_TIMEOUT_S", 10.0),
        read_timeout_seconds=_env_float("FETCH_READ_TIMEOUT_S", 120.0),
        max_redirects=_env_int("FETCH_MAX_REDIRECTS", 8),
        allow_private_hosts=os.environ.get("FETCH_ALLOW_PRIVATE_HOSTS", "").lower() in ("1", "true", "yes"),
        allowed_host_suffixes=frozenset(s.strip() for s in allowed.split(",")) if allowed else None,
        blocked_host_suffixes=frozenset(s.strip() for s in blocked.split(",")) if blocked else None,
    )
