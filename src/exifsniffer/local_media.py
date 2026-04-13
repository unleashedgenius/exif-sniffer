"""Browse image files under LOCAL_MEDIA_ROOT with traversal checks."""

from __future__ import annotations

from pathlib import Path

from exifsniffer.extract import IMAGE_SUFFIXES
from exifsniffer.paths import resolve_under_root
from exifsniffer.settings import Settings


def require_local_media_root(settings: Settings) -> Path:
    """Return resolved LOCAL_MEDIA_ROOT or raise with an actionable message."""
    raw = settings.local_media_root
    if not raw:
        raise ValueError(
            "LOCAL_MEDIA_ROOT is not set. Configure it in the server environment to the host "
            "directory that is bind-mounted into the container (or a local folder when running "
            "bare metal), then use paths relative to that root in the local media tools."
        )
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"LOCAL_MEDIA_ROOT is not a directory: {root}")
    return root


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
        raise NotADirectoryError(f"Not a directory under LOCAL_MEDIA_ROOT: {relative_directory!r}")

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
