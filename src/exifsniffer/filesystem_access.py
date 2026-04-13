"""Filesystem tools scoped to a configured base directory (LM Studio filesystem-access style).

Mirrors taderich73/filesystem-access: join base + relative path, reject ``..`` segments in the
relative string, and confine targets with :func:`exifsniffer.paths.resolve_under_root` (resolve +
``relative_to`` guard).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from exifsniffer.paths import resolve_under_root

# Same character class as the reference plugin's zod regex: ^[\w./-]+$
# Match JS ``\w`` (ASCII) plus ``.``, ``/``, ``-`` — same intent as the reference zod regex.
_RELATIVE_NAME_PATTERN = re.compile(r"^[\w./-]+$", re.ASCII)


def validate_relative_name(name: str, *, label: str) -> None:
    if not name or not name.strip():
        raise ValueError(f"{label} cannot be empty")
    if not _RELATIVE_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"{label} may only contain letters, numbers, underscores, hyphens, dots, and slashes"
        )
    for part in Path(name).parts:
        if part == "..":
            raise ValueError(f"{label} must not contain parent directory segments")


def configured_base_or_error(base: Path | None) -> Path:
    if base is None:
        raise ValueError(
            "Error: Directory not set. Set environment variable LOCAL_MEDIA_BASE to an absolute "
            "path (equivalent to the LM Studio plugin 'Base Directory' / folderName field)."
        )
    resolved = base.expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Error: Directory not set or does not exist ({resolved})")
    return resolved


def fs_list_files(base: Path | None) -> list[dict[str, Any]]:
    try:
        root = configured_base_or_error(base)
    except ValueError as exc:
        return [{"path": "list_files.error", "value": str(exc)}]
    try:
        names = sorted(p.name for p in root.iterdir())
    except OSError as exc:
        return [{"path": "list_files.error", "value": f"Error: cannot list directory: {exc}"}]
    if not names:
        return [{"path": "list_files.message", "value": "Directory is empty"}]
    rows: list[dict[str, Any]] = []
    for i, name in enumerate(names):
        rows.append({"path": f"list_files.entries[{i}]", "value": name})
    return rows


def fs_read_file(base: Path | None, file_name: str) -> list[dict[str, Any]]:
    try:
        validate_relative_name(file_name, label="file_name")
    except ValueError as exc:
        return [{"path": "read_file.error", "value": str(exc)}]
    try:
        root = configured_base_or_error(base)
    except ValueError as exc:
        return [{"path": "read_file.error", "value": str(exc)}]
    try:
        full_path = resolve_under_root(root, file_name)
    except ValueError as exc:
        return [{"path": "read_file.error", "value": f"Error: File path is outside the configured directory: {exc}"}]
    if not full_path.is_file():
        return [{"path": "read_file.error", "value": "Error: File does not exist"}]
    try:
        text = full_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [{"path": "read_file.error", "value": f"Error: cannot read file: {exc}"}]
    return [{"path": "read_file.content", "value": text}]


def fs_write_file(base: Path | None, file_name: str, content: str) -> list[dict[str, Any]]:
    try:
        validate_relative_name(file_name, label="file_name")
    except ValueError as exc:
        return [{"path": "write_file.error", "value": str(exc)}]
    try:
        root = configured_base_or_error(base)
    except ValueError as exc:
        return [{"path": "write_file.error", "value": str(exc)}]
    try:
        full_path = resolve_under_root(root, file_name)
    except ValueError as exc:
        return [{"path": "write_file.error", "value": f"Error: File path is outside the configured directory: {exc}"}]
    full_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        full_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return [{"path": "write_file.error", "value": f"Error: cannot write file: {exc}"}]
    return [{"path": "write_file.message", "value": "File created or updated successfully"}]


def fs_create_directory(base: Path | None, directory_name: str) -> list[dict[str, Any]]:
    try:
        validate_relative_name(directory_name, label="directory_name")
    except ValueError as exc:
        return [{"path": "create_directory.error", "value": str(exc)}]
    try:
        root = configured_base_or_error(base)
    except ValueError as exc:
        return [{"path": "create_directory.error", "value": str(exc)}]
    try:
        full_path = resolve_under_root(root, directory_name)
    except ValueError as exc:
        return [
            {
                "path": "create_directory.error",
                "value": f"Error: Directory path is outside the configured directory: {exc}",
            }
        ]
    try:
        full_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [{"path": "create_directory.error", "value": f"Error: cannot create directory: {exc}"}]
    return [{"path": "create_directory.message", "value": f"Directory '{directory_name}' created successfully"}]
