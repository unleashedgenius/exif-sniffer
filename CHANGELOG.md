# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.1] - 2026-04-11

### Fixed

- **Remote downloads (`fetch_remote_media`)**: Declared the `httpx[http2]` extra so the optional `h2` package is installed with `httpx`. Previously `AsyncClient(..., http2=True)` in `fetch.py` failed at runtime with *"the 'h2' package is not installed"* when dependencies were installed only from `pyproject.toml` (local venv and Docker `pip install .`).

### Debug / verification

- Live verification against Streamable HTTP at `http://127.0.0.1:3000/mcp` showed MCP `initialize`, `tools/list`, malformed JSON handling, unknown-tool errors, SSRF blocking for loopback URLs, and parallel `tools/list` requests behaving as expected. `fetch_remote_media` to public HTTPS URLs failed until `h2` was present; aligning dependencies resolves that failure path. See [VERIFICATION_GUIDELINES.md](VERIFICATION_GUIDELINES.md) for reporting format used during checks.
