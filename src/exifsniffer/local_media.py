"""Browse image files under a user-supplied absolute root with traversal checks."""

from __future__ import annotations

from pathlib import Path

from exifsniffer.extract import IMAGE_SUFFIXES
from exifsniffer.paths import resolve_under_root


def parse_local_media_root(path_str: str) -> Path:
    """Resolve *path_str* to an existing directory (absolute path required)."""
    raw = path_str.strip()
    if not raw:
        raise ValueError("local_media_root must be a non-empty path.")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ValueError(
            "local_media_root must be an absolute path (e.g. /media/photos on Linux or "
            "C:\\\\Photos on Windows)."
        )
    if not candidate.exists():
        raise ValueError(f"local_media_root does not exist: {candidate}")
    resolved = candidate.resolve()
    if not resolved.is_dir():
        raise ValueError(f"local_media_root is not a directory: {resolved}")
    return resolved


def list_image_relative_paths(
    root: Path,
    relative_directory: str,
    *,
    recursive: bool,
    max_files: int,
) -> list[str]:
    """List image-like files under *root* / *relative_directory*; return POSIX paths relative to *root*."""
    if max_files < 1:
        raise ValueError("max_files must be at least 1")
    if max_files > 5000:
        raise ValueError("max_files cannot exceed 5000")

    base = resolve_under_root(root, relative_directory)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory under local_media_root: {relative_directory!r}")

    root_resolved = root.resolve()
    out: list[str] = []

    if recursive:
        candidates = base.rglob("*")
    else:
        candidates = sorted(base.iterdir(), key=lambda x: str(x).lower())

    for p in candidates:
        if len(out) >= max_files:
            break
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        if p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            resolved = p.resolve()
            rel = resolved.relative_to(root_resolved)
        except ValueError:
            continue
        out.append(rel.as_posix())

    return out
