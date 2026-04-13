"""Load, merge, and persist EXIF via piexif (JPEG and WebP)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Mapping

import piexif
import piexif.helper

WRITABLE_EXIF_SUFFIXES = frozenset({".jpg", ".jpeg", ".webp"})

_ALLOWED_IFDS = frozenset({"0th", "Exif", "GPS", "Interop", "1st"})


def _empty_exif_template() -> dict[str, Any]:
    return {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}


def _load_exif_dict(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    try:
        return piexif.load(str(path))
    except (ValueError, OSError) as exc:
        if suffix == ".webp":
            return _empty_exif_template()
        raise RuntimeError(f"Could not read EXIF from {path}: {exc}") from exc


def _tag_id_for_name(ifd: str, tag_name: str) -> int:
    if ifd not in _ALLOWED_IFDS:
        raise ValueError(
            f"IFD {ifd!r} is not editable here; use one of: {', '.join(sorted(_ALLOWED_IFDS))}"
        )
    table = piexif.TAGS.get(ifd)
    if table is None:
        raise ValueError(f"Unknown IFD {ifd!r}")
    if tag_name.isdigit():
        return int(tag_name)
    for tag_id, meta in table.items():
        if meta.get("name") == tag_name:
            return int(tag_id)
    raise ValueError(f"Unknown tag {tag_name!r} in IFD {ifd!r}")


def _normalize_tag_value(ifd: str, tag_id: int, value: Any) -> Any:
    if value is None:
        raise ValueError("Tag values must not be null; omit the key or use remove_tags")
    if ifd == "Exif" and tag_id == piexif.ExifIFD.UserComment and isinstance(value, str):
        return piexif.helper.UserComment.dump(value, "unicode")
    if isinstance(value, str):
        return value.encode("utf-8", errors="surrogateescape")
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, (tuple, list)) and len(value) == 2:
        a, b = value[0], value[1]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return (int(a), int(b))
    return value


def update_image_exif(
    path: Path,
    *,
    set_tags: Mapping[str, Mapping[str, Any]],
    remove_tags: Mapping[str, list[str]],
) -> dict[str, Any]:
    """Merge *set_tags* / *remove_tags* into *path* (JPEG/WebP) and write the file in place.

    *set_tags* maps IFD name (``0th``, ``Exif``, ``GPS``, ``Interop``, ``1st``) to
    ``{tag_name: value}`` where *tag_name* is the piexif human-readable name (or numeric id string).

    *remove_tags* maps IFD name to a list of tag names (or numeric id strings) to delete.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    suffix = path.suffix.lower()
    if suffix not in WRITABLE_EXIF_SUFFIXES:
        raise ValueError(
            f"EXIF write is only supported for {', '.join(sorted(WRITABLE_EXIF_SUFFIXES))}; "
            f"got {suffix!r} ({path.name})"
        )

    if not set_tags and not remove_tags:
        return {
            "path": str(path.resolve()),
            "suffix": suffix,
            "tags_updated": [],
            "tags_removed": [],
            "unchanged": True,
        }

    exif = _load_exif_dict(path)
    removed: list[str] = []
    updated: list[str] = []

    for ifd_name, names in remove_tags.items():
        if ifd_name not in _ALLOWED_IFDS:
            raise ValueError(f"IFD {ifd_name!r} is not allowed in remove_tags")
        bucket = exif.get(ifd_name)
        if not isinstance(bucket, dict):
            continue
        for tag_name in names:
            tag_id = _tag_id_for_name(ifd_name, tag_name)
            if tag_id in bucket:
                bucket.pop(tag_id, None)
                removed.append(f"{ifd_name}.{tag_name}")

    for ifd_name, pairs in set_tags.items():
        if ifd_name not in _ALLOWED_IFDS:
            raise ValueError(f"IFD {ifd_name!r} is not allowed in set_tags")
        bucket = exif.setdefault(ifd_name, {})
        if not isinstance(bucket, dict):
            raise ValueError(f"IFD {ifd_name!r} is not a tag dictionary in this file")
        for tag_name, raw in pairs.items():
            tag_id = _tag_id_for_name(ifd_name, tag_name)
            bucket[tag_id] = _normalize_tag_value(ifd_name, tag_id, raw)
            updated.append(f"{ifd_name}.{tag_name}")

    exif_bytes = piexif.dump(exif)
    image_bytes = path.read_bytes()
    buf = io.BytesIO()
    piexif.insert(exif_bytes, image_bytes, buf)
    path.write_bytes(buf.getvalue())
    return {
        "path": str(path.resolve()),
        "suffix": path.suffix.lower(),
        "tags_updated": updated,
        "tags_removed": removed,
    }
