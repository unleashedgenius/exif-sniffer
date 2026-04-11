"""Safe path resolution under DATA_DIR."""

from __future__ import annotations

from pathlib import Path


def resolve_under_root(root: Path, relative: str) -> Path:
    """Resolve *relative* under *root*, rejecting traversal outside *root*."""
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError(f"Path escapes data directory: {relative!r}") from e
    return candidate
